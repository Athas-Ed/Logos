import type { ChatMessage } from "../types/chat";

/** 将扁平 messages 拆成 (user, assistant?) 轮次 */
export function splitMessageTurns(
  messages: ChatMessage[],
): { user: ChatMessage; assistant?: ChatMessage }[] {
  const turns: { user: ChatMessage; assistant?: ChatMessage }[] = [];
  let i = 0;
  while (i < messages.length) {
    const m = messages[i];
    if (m.role !== "user") {
      i += 1;
      continue;
    }
    const assistant =
      messages[i + 1]?.role === "assistant" ? messages[i + 1] : undefined;
    turns.push({ user: m, assistant });
    i += assistant ? 2 : 1;
  }
  return turns;
}

function oneLineTurnTitle(userText: string, turnIndex: number): string {
  const t = userText.trim().replace(/\s+/g, " ");
  const preview = t.length <= 40 ? t : `${t.slice(0, 40)}…`;
  return `【第${turnIndex + 1}轮】用户问：${preview || "（空）"}`;
}

/** 供 API 发送：最近 N 轮全文，更早轮仅一行 title（assistant 不含 reasoning） */
export function clipHistoryForApi(
  messages: ChatMessage[],
  maxFullRounds: number,
): ChatMessage[] {
  const turns = splitMessageTurns(messages);
  if (turns.length === 0) {
    return [];
  }
  const n = Math.max(1, maxFullRounds);
  const out: ChatMessage[] = [];
  const olderCount = Math.max(0, turns.length - n);
  for (let i = 0; i < olderCount; i += 1) {
    const title = oneLineTurnTitle(turns[i].user.content, i);
    out.push({ role: "user", content: title });
    out.push({
      role: "assistant",
      content: "（该轮详情已省略，见后续轮次或档 B 归档。）",
    });
  }
  for (let i = olderCount; i < turns.length; i += 1) {
    out.push(turns[i].user);
    if (turns[i].assistant) {
      const a = turns[i].assistant!;
      out.push({
        role: "assistant",
        content: a.content,
      });
    }
  }
  return out;
}

/** 当前轮之前的历史（不含最后一组 user/assistant 占位） */
export function priorTurnsForFollowUp(messages: ChatMessage[]): ChatMessage[] {
  if (messages.length <= 2) {
    return [];
  }
  const copy = [...messages];
  const last = copy[copy.length - 1];
  if (last?.role === "assistant" && !last.content.trim()) {
    copy.pop();
  }
  const lastUser = copy[copy.length - 1];
  if (lastUser?.role === "user") {
    copy.pop();
  }
  return copy;
}
