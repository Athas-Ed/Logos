"""AgentShell.run_task：react 分支须与流式入口一致地合并 task_input。"""

from __future__ import annotations

import json


class _EchoLLM:
    """将 messages 中最后一条 user 文本回显为 final_answer，便于断言 CB 拼装。"""

    @staticmethod
    def _last_user_text(messages: list) -> str:
        for m in reversed(messages):
            if m.role == "user":
                return m.content
        return ""

    def complete(self, messages, *, json_mode: bool = False) -> str:
        last = self._last_user_text(messages)
        if json_mode:
            return json.dumps({"final_answer": last}, ensure_ascii=False)
        return last

    def stream_completion(self, messages, *, json_mode: bool = False):
        yield self.complete(messages, json_mode=json_mode)


def test_run_task_react_merges_task_input() -> None:
    from logos.agent.shell import AgentShell
    from logos.agent.tool_registry import ToolRegistry

    shell = AgentShell(llm=_EchoLLM(), tools=ToolRegistry())
    result = shell.run_task(
        "用户正文",
        skill_id="retrieve_qa",
        task_input={"text": "结构化的任务输入"},
    )
    assert "用户正文" in result.answer
    assert "结构化的任务输入" in result.answer
