from logos.agent.cb import clip_turn_history
from logos.ports.llm import ChatMessage


def test_clip_turn_history_keeps_recent_full_text() -> None:
    history: list[ChatMessage] = []
    for i in range(7):
        history.append(ChatMessage(role="user", content=f"问题{i}"))
        history.append(ChatMessage(role="assistant", content=f"答案{i}"))
    clipped = clip_turn_history(history, max_full_rounds=5)
    assert clipped[0].content.startswith("【第1轮】")
    assert clipped[-2].content == "问题6"
    assert clipped[-1].content == "答案6"
