"""PR-1：select_paradigm 读取 manifest。"""

from __future__ import annotations

import pytest

from logos.agent.pr import select_paradigm
from logos.platform.skills_registry import SkillManifestNotFoundError


def test_select_paradigm_lint_zh_dialogue() -> None:
    assert select_paradigm("lint_zh") == "dialogue"


def test_select_paradigm_chat_inspire_dialogue() -> None:
    assert select_paradigm("chat_inspire") == "dialogue"


def test_select_paradigm_retrieve_qa_react() -> None:
    assert select_paradigm("retrieve_qa") == "react"


def test_select_paradigm_outline_plan() -> None:
    assert select_paradigm("outline_plan") == "plan"


def test_select_paradigm_pipeline_dev() -> None:
    assert select_paradigm("pipeline_dev") == "pipeline"


def test_select_paradigm_unknown_raises() -> None:
    with pytest.raises(SkillManifestNotFoundError):
        select_paradigm("no_such_skill_xyz")
