"""Pipeline 范式：按 ``pipeline_profile`` 执行阶段表（CD-3 平台轨）。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logos.ports.llm import ChatMessage, LLMClient
from logos.persistence.setting_import import (
    PipelineValidationError,
    load_entity_template_profile,
    render_batch_to_setting_entry,
    scan_import_overlap,
    validate_import_batch,
)
from logos.persistence.setting_import.pipeline_spec import (
    PipelineSpec,
    PipelineStepSpec,
    load_pipeline_spec,
)
from logos.persistence.setting_import.profile import (
    EntityTemplateProfile,
    read_profile_text,
)


@dataclass(frozen=True, slots=True)
class PipelineStepEvent:
    step_id: str
    status: str
    summary: str = ""


@dataclass(frozen=True, slots=True)
class PipelineWarningEvent:
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PipelineResult:
    batch: dict[str, Any]
    written_paths: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineStreamDone:
    result: PipelineResult


PipelineStreamItem = PipelineStepEvent | PipelineWarningEvent | PipelineStreamDone


class PipelineRunner:
    """按 ``resources/pipelines/<profile>.yaml`` 解释执行；业务规则随 entity_template profile 变。"""

    def __init__(
        self,
        *,
        profile_id: str,
        workspace_root: Path | str,
        ksfs_root: Path | str | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.profile_id = profile_id.strip()
        self.workspace_root = Path(workspace_root)
        self._ksfs_root = (
            Path(ksfs_root) if ksfs_root is not None else self.workspace_root
        )
        self.llm = llm
        self._profile = load_entity_template_profile(self.profile_id)
        self._spec = load_pipeline_spec(self.profile_id)

    @property
    def profile(self) -> EntityTemplateProfile:
        return self._profile

    @property
    def spec(self) -> PipelineSpec:
        return self._spec

    def iter_run(
        self,
        user_text: str,
        *,
        batch_json: dict[str, Any] | None = None,
        extra_system: str | None = None,
        skip_step_types: frozenset[str] | None = None,
    ) -> Iterator[PipelineStreamItem]:
        """执行流水线；*batch_json* 非空时跳过 ``llm_json`` 阶段（单测注入金样）。"""
        skip = skip_step_types or frozenset()
        batch: dict[str, Any] | None = batch_json
        warnings: list[str] = []
        written_paths: list[str] = []

        for step in self._spec.steps:
            if not step.enabled or step.type in skip:
                continue
            yield PipelineStepEvent(step_id=step.id, status="started", summary=step.type)
            try:
                if step.type == "llm_json":
                    if batch is not None:
                        summary = "skipped (injected batch)"
                    else:
                        batch = self._run_llm_json(user_text, extra_system=extra_system)
                        summary = f"units={len(batch.get('units', []))}"
                elif step.type == "json_schema":
                    if batch is None:
                        msg = "json_schema requires batch from llm_json or injection"
                        raise RuntimeError(msg)
                    validate_import_batch(batch, self._profile.schema_path)
                    summary = "ok"
                elif step.type == "overlap_scan":
                    overlap_warnings = scan_import_overlap(
                        batch or {},
                        profile=self._profile,
                        workspace_root=self.workspace_root,
                        ksfs_root=self._ksfs_root,
                    )
                    warnings.extend(overlap_warnings)
                    if overlap_warnings:
                        yield PipelineWarningEvent(warnings=tuple(overlap_warnings))
                    summary = f"warnings={len(overlap_warnings)}"
                elif step.type == "render":
                    if batch is None:
                        msg = "render requires validated batch"
                        raise RuntimeError(msg)
                    rendered = render_batch_to_setting_entry(
                        batch,
                        profile=self._profile,
                        workspace_root=self.workspace_root,
                    )
                    written_paths = [r.rel_path for r in rendered]
                    summary = f"files={len(written_paths)}"
                elif step.type == "promote_gate":
                    summary = "请在 Task 页确认后点击「晋升至 KSFS」"
                else:
                    msg = f"unsupported step type: {step.type!r}"
                    raise RuntimeError(msg)
            except (PipelineValidationError, ValueError, json.JSONDecodeError) as exc:
                yield PipelineStepEvent(
                    step_id=step.id,
                    status="error",
                    summary=str(exc),
                )
                return
            except Exception as exc:
                yield PipelineStepEvent(
                    step_id=step.id,
                    status="error",
                    summary=f"{type(exc).__name__}: {exc}",
                )
                return
            yield PipelineStepEvent(step_id=step.id, status="ok", summary=summary)

        if batch is None:
            return
        yield PipelineStreamDone(
            PipelineResult(
                batch=batch,
                written_paths=tuple(written_paths),
                warnings=tuple(warnings),
            )
        )

    def run(
        self,
        user_text: str,
        *,
        batch_json: dict[str, Any] | None = None,
        extra_system: str | None = None,
        skip_step_types: frozenset[str] | None = None,
    ) -> PipelineResult:
        result: PipelineResult | None = None
        for item in self.iter_run(
            user_text,
            batch_json=batch_json,
            extra_system=extra_system,
            skip_step_types=skip_step_types,
        ):
            if isinstance(item, PipelineStreamDone):
                result = item.result
        if result is None:
            msg = "pipeline did not complete"
            raise RuntimeError(msg)
        return result

    def _run_llm_json(
        self,
        user_text: str,
        *,
        extra_system: str | None = None,
    ) -> dict[str, Any]:
        if self.llm is None:
            msg = "llm_json step requires LLMClient"
            raise RuntimeError(msg)
        system = read_profile_text(self._profile.llm_instructions_path)
        if extra_system:
            system = system + "\n\n" + extra_system.strip()
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user_text.strip()),
        ]
        raw = self.llm.complete(messages, json_mode=True).strip()
        batch = json.loads(raw)
        if not isinstance(batch, dict):
            msg = "LLM output must be a JSON object"
            raise ValueError(msg)
        return batch

def iter_run_pipeline(
    llm: LLMClient | None,
    *,
    profile_id: str,
    workspace_root: Path | str,
    ksfs_root: Path | str | None = None,
    user_text: str,
    batch_json: dict[str, Any] | None = None,
    extra_system: str | None = None,
) -> Iterator[PipelineStreamItem]:
    runner = PipelineRunner(
        profile_id=profile_id,
        workspace_root=workspace_root,
        ksfs_root=ksfs_root,
        llm=llm,
    )
    yield from runner.iter_run(
        user_text,
        batch_json=batch_json,
        extra_system=extra_system,
    )


def run_pipeline(
    llm: LLMClient | None,
    *,
    profile_id: str,
    workspace_root: Path | str,
    ksfs_root: Path | str | None = None,
    user_text: str,
    batch_json: dict[str, Any] | None = None,
    extra_system: str | None = None,
) -> PipelineResult:
    runner = PipelineRunner(
        profile_id=profile_id,
        workspace_root=workspace_root,
        ksfs_root=ksfs_root,
        llm=llm,
    )
    return runner.run(user_text, batch_json=batch_json, extra_system=extra_system)
