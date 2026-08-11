"""设定一致性检查核心服务（setting_check）。

程序化检索 + 单次 LLM 判定：从待查内容检索相关 KSFS 设定条目，
再由 LLM 判定是否存在事实/概念冲突。供 API 端点与其他 Skill 复用。

权威文档：``original_docs/重要子系统开发文档/非必需可扩展/setting_check.md``。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from logos.ports.llm import ChatMessage, LLMClient
from logos.ports.retrieval import RetrievalService

_log = logging.getLogger("logos.agent.setting_check")

ConflictLevel = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class SettingConflict:
    """单条设定冲突。"""

    item_index: int
    level: ConflictLevel
    ksfs_entry_path: str
    description: str


@dataclass(frozen=True, slots=True)
class SettingCheckResult:
    """检查结果；冲突为空表示通过。"""

    conflicts: list[SettingConflict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts


def _build_check_prompt(items: list[dict[str, Any]], citations: list[Any]) -> str:
    """拼装判定 prompt：待查内容 + 检索到的设定片段。"""
    content_lines = []
    for it in items:
        idx = it.get("index", 0)
        content = str(it.get("content", "")).strip()
        if content:
            content_lines.append(f"- [{idx}] {content}")
    content_block = "\n".join(content_lines) if content_lines else "（无内容）"

    if citations:
        cite_lines = []
        for c in citations:
            snippet = (c.snippet or "").strip()
            cite_lines.append(f"- 条目 {c.path}：{snippet}")
        cite_block = "\n".join(cite_lines)
    else:
        cite_block = "（未检索到相关设定条目）"

    return (
        "你是设定一致性检查器。判断下列创作内容是否与已有 KSFS 设定条目存在事实/概念冲突。\n"
        f"\n【待检查内容】\n{content_block}\n"
        f"\n【检索到的相关设定条目】\n{cite_block}\n"
        "\n判定规则：\n"
        "- 仅报告**事实/概念冲突**（如角色种族/年龄/身份/关系不符、事件顺序矛盾、地点错位）。\n"
        "- `level: \"error\"`：与设定直接矛盾。\n"
        "- `level: \"warning\"`：存疑或明显偏离但未直接矛盾。\n"
        "- 不要报告风格/基调问题。不要编造设定条目——冲突必须能对到检索结果中的某个条目。\n"
        "\n输出 JSON（键名保持英文）：\n"
        '{"conflicts": [{"item_index": 0, "level": "error", "ksfs_entry_path": "人物/张三.md", "description": "..."}]}\n'
        "无冲突时输出 {\"conflicts\": []}。"
    )


def _parse_conflicts(raw: str, valid_indices: set[int]) -> list[SettingConflict]:
    """解析 LLM 输出的冲突 JSON；失败降级为空列表。"""
    text = raw.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        _log.warning("setting_check：LLM 输出非 JSON，降级为空结果：%r", text[:200])
        return []

    conflicts: list[SettingConflict] = []
    raw_conflicts = parsed.get("conflicts") if isinstance(parsed, dict) else None
    if not isinstance(raw_conflicts, list):
        return []

    for item in raw_conflicts:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("item_index"))
        except (TypeError, ValueError):
            idx = -1
        if idx not in valid_indices:
            continue
        level = item.get("level")
        if level not in ("error", "warning"):
            level = "warning"
        path = str(item.get("ksfs_entry_path", "")).strip()
        description = str(item.get("description", "")).strip()
        if not path and not description:
            continue
        conflicts.append(
            SettingConflict(
                item_index=idx,
                level=level,  # type: ignore[arg-type]
                ksfs_entry_path=path,
                description=description,
            )
        )
    return conflicts


def run_setting_check(
    items: list[dict[str, Any]],
    *,
    retrieval: RetrievalService,
    llm: LLMClient,
    top_k: int = 8,
) -> SettingCheckResult:
    """执行设定一致性检查。

    *items* 形如 ``[{"index": int, "content": str}, ...]``。
    对内容做程序化检索后，单次 LLM 判定冲突；解析失败时返回空结果（不阻塞主流程）。
    """
    valid_indices = set()
    for it in items:
        try:
            valid_indices.add(int(it.get("index")))
        except (TypeError, ValueError):
            continue

    # 1) 程序化检索：以全部内容为查询文本取 top-k 相关设定
    combined = " ".join(
        str(it.get("content", "")) for it in items if str(it.get("content", "")).strip()
    ).strip()
    citations: list[Any] = []
    if combined:
        try:
            citations = retrieval.query(text=combined, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 — 检索失败不阻塞检查
            _log.warning("setting_check：检索失败：%s", exc)

    # 2) 单次 LLM 判定
    prompt = _build_check_prompt(items, citations)
    try:
        raw = llm.complete([ChatMessage(role="user", content=prompt)], json_mode=True)
    except Exception as exc:  # noqa: BLE001 — LLM 失败降级空结果
        _log.warning("setting_check：LLM 判定失败：%s", exc)
        return SettingCheckResult()

    conflicts = _parse_conflicts(raw, valid_indices)
    return SettingCheckResult(conflicts=conflicts)
