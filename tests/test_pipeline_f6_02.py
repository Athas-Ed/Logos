"""F6-02：PipelineRunner、schema 校验、render_spec 落盘、Shell 不走 ReAct。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from logos.agent import pipeline as pipeline_mod
from logos.agent import pr as pr_mod
from logos.agent import react as react_mod
from logos.agent.pipeline import PipelineRunner, PipelineStreamDone
from logos.agent.task import TaskDone, TaskPipelineStep, TaskSession
from logos.agent.tool_registry import ToolRegistry
from logos.platform.mcp_stdio import resolve_repo_root
from logos.platform.skills_registry import (
    SkillManifestError,
    get_skill_manifest,
)
from logos.persistence.setting_import import (
    PipelineValidationError,
    validate_import_batch,
)
from logos.persistence.setting_import.profile import load_entity_template_profile
from logos.persistence.setting_import.render import render_batch_to_setting_entry
from logos.persistence.setting_import.pipeline_spec import load_pipeline_spec


def _examples_dir() -> Path:
    return (
        resolve_repo_root()
        / "resources"
        / "entity_template"
        / "your_profile_v1"
        / "examples"
    )


def _load_batch(name: str) -> dict:
    return json.loads((_examples_dir() / name).read_text(encoding="utf-8"))


def _normalize_md(text: str) -> str:
    return text.replace("\r\n", "\n").strip() + "\n"


@pytest.fixture
def profile():
    return load_entity_template_profile("your_profile_v1")


def test_pipeline_spec_loads_your_profile_v1() -> None:
    spec = load_pipeline_spec("your_profile_v1")
    assert spec.profile_id == "your_profile_v1"
    types = [s.type for s in spec.steps if s.enabled]
    assert "json_schema" in types
    assert "render" in types


def test_manifest_pipeline_requires_profile_field() -> None:
    from logos.platform.skills_registry import _validate_manifest_dict

    base = {
        "skill_id": "bad_pipe",
        "display_name": "x",
        "persistence_tier": "p0",
        "paradigm": "pipeline",
        "turn_policy": "single",
        "allowed_tools": [],
        "prompt_runtime_key": "skills/lint_zh",
        "input_schema": {"type": "object", "properties": {}},
    }
    with pytest.raises(SkillManifestError, match="pipeline_profile required"):
        _validate_manifest_dict(base, source="test")


def test_validate_and_render_minimal_golden(tmp_path: Path, profile) -> None:
    batch = _load_batch("minimal_batch.json")
    validate_import_batch(batch, profile.schema_path)
    result = PipelineRunner(
        profile_id="your_profile_v1",
        workspace_root=tmp_path,
        llm=None,
    ).run("ignored", batch_json=batch, skip_step_types=frozenset({"llm_json"}))
    expected = _normalize_md(
        (_examples_dir() / "minimal_character_expected.md").read_text(encoding="utf-8")
    )
    out_path = tmp_path / "setting_entry" / "人物" / "lin-dong.md"
    assert out_path.is_file()
    assert _normalize_md(out_path.read_text(encoding="utf-8")) == expected
    assert "setting_entry/人物/lin-dong.md" in result.written_paths


def test_validate_and_render_with_suggestions_golden(tmp_path: Path, profile) -> None:
    batch = _load_batch("with_suggestions_batch.json")
    validate_import_batch(batch, profile.schema_path)
    render_batch_to_setting_entry(
        batch, profile=profile, workspace_root=tmp_path
    )
    expected = _normalize_md(
        (_examples_dir() / "with_suggestions_expected.md").read_text(encoding="utf-8")
    )
    out_path = tmp_path / "setting_entry" / "地点" / "qingyang-town.md"
    assert _normalize_md(out_path.read_text(encoding="utf-8")) == expected


def test_validate_rejects_invalid_slug(profile) -> None:
    batch = _load_batch("minimal_batch.json")
    batch["units"][0]["slug"] = "带空格 slug"
    with pytest.raises(PipelineValidationError):
        validate_import_batch(batch, profile.schema_path)


def test_task_session_pipeline_does_not_call_react_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_stream5_api import _make_ports

    react_called: list[bool] = []

    def _fail_react(*_a, **_k):
        react_called.append(True)
        raise AssertionError("iter_react_loop must not run for pipeline")

    monkeypatch.setattr(react_mod, "iter_react_loop", _fail_react)

    batch = _load_batch("minimal_batch.json")
    llm = MagicMock()
    llm.complete.return_value = json.dumps(batch, ensure_ascii=False)
    ports = _make_ports(tmp_path)
    items = list(
        TaskSession(
            llm=llm,
            tools=ToolRegistry(),
            settings=ports.settings,
            workspace_root=tmp_path,
        ).iter_task("import_setting", "paste")
    )
    assert not react_called
    assert any(isinstance(i, TaskPipelineStep) for i in items)
    done = next(i for i in items if isinstance(i, TaskDone))
    assert done.kind == "pipeline"
    assert done.written_paths


def test_task_session_pipeline_delegates_iter_run_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TaskSession 将 pipeline 委托给 iter_run_pipeline，而非 ReAct。"""
    from tests.test_stream5_api import _make_ports

    seen: list[str] = []

    def fake_iter(*_a, **_k):
        seen.append("pipeline")
        yield PipelineStreamDone(
            pipeline_mod.PipelineResult(batch={}, written_paths=())
        )

    monkeypatch.setattr(pipeline_mod, "iter_run_pipeline", fake_iter)
    ports = _make_ports(tmp_path)
    list(
        TaskSession(
            llm=MagicMock(),
            tools=ToolRegistry(),
            settings=ports.settings,
            workspace_root=tmp_path,
        ).iter_task("import_setting", "x")
    )
    assert seen == ["pipeline"]
