"""F5-01：产品 Skill manifest 注册表。"""

from __future__ import annotations

import pytest

from logos.platform.skills_registry import (
    SkillManifestError,
    SkillManifestNotFoundError,
    get_skill_manifest,
    list_bootstrap_skill_summaries,
    list_builtin_skill_ids,
    manifests_dir,
)


def test_manifests_dir_exists() -> None:
    root = manifests_dir()
    assert root.is_dir()
    assert (root / "lint_zh.yaml").is_file()
    assert (root / "chat_inspire.yaml").is_file()


def test_load_lint_zh_dialogue_p2() -> None:
    m = get_skill_manifest("lint_zh")
    assert m.skill_id == "lint_zh"
    assert m.paradigm == "dialogue"
    assert m.persistence_tier == "p2"
    assert m.turn_policy == "single"
    assert m.allowed_tools == ()
    assert m.prompt_runtime_key == "skills/lint_zh"
    assert "text" in m.input_schema.get("properties", {})
    assert "语病" in m.ui_instructions


def test_load_chat_inspire_multi() -> None:
    m = get_skill_manifest("chat_inspire")
    assert m.paradigm == "react"
    assert m.persistence_tier == "p2"
    assert m.turn_policy == "multi"


def test_list_bootstrap_skill_summaries() -> None:
    summaries = list_bootstrap_skill_summaries()
    ids = {s.skill_id for s in summaries}
    assert "lint_zh" in ids
    assert "retrieve_qa" in ids
    assert "outline_plan" in ids
    rq = next(s for s in summaries if s.skill_id == "retrieve_qa")
    assert rq.paradigm == "react"
    assert rq.display_name
    op = next(s for s in summaries if s.skill_id == "outline_plan")
    assert op.paradigm == "plan"


def test_unknown_skill_id_raises() -> None:
    with pytest.raises(SkillManifestNotFoundError):
        get_skill_manifest("no_such_skill_xyz")


def test_list_builtin_includes_samples() -> None:
    ids = list_builtin_skill_ids()
    assert "lint_zh" in ids
    assert "chat_inspire" in ids
    assert "retrieve_qa" in ids
    assert "outline_plan" in ids


def test_dialogue_manifest_rejects_stray_pipeline_profile() -> None:
    from logos.platform.skills_registry import _validate_manifest_dict

    raw = {
        "skill_id": "x",
        "display_name": "x",
        "persistence_tier": "p2",
        "paradigm": "dialogue",
        "turn_policy": "single",
        "allowed_tools": [],
        "prompt_runtime_key": "skills/lint_zh",
        "input_schema": {"type": "object", "properties": {}},
        "pipeline_profile": "default_import_v0",
    }
    with pytest.raises(SkillManifestError, match="only allowed when paradigm is pipeline"):
        _validate_manifest_dict(raw, source="test")
