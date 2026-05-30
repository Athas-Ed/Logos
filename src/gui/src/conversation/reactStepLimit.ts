/** ReAct 步数触顶：UI 文案与正文后缀剥离（范式级，非单 Skill）。 */

export type ReactStepLimitTurnMeta = {
  hit: boolean;
};

/** 步数触顶说明（展示于 UI 条，不写入 assistant 正文）。 */
export const REACT_STEP_LIMIT_NOTICE =
  "本次 ReAct 步数已达本轮上限。发送新问题将自动开启新会话继续检索。";

const LEGACY_SUFFIX_MARKERS = [
  "本次 ReAct 步数已达本轮上限。",
  "本次已达到本会话允许的 ReAct 步数总上限（含续跑）。",
] as const;

/** 从 assistant 正文移除历史遗留的内联触顶后缀。 */
export function stripStepLimitSuffix(content: string): string {
  let text = content.trimEnd();
  for (const marker of LEGACY_SUFFIX_MARKERS) {
    const idx = text.indexOf(marker);
    if (idx >= 0) {
      text = text.slice(0, idx).trimEnd();
    }
  }
  return text;
}

export function emptyReactStepLimitTurn(): ReactStepLimitTurnMeta {
  return { hit: false };
}

export function recordReactStepLimitTurn(
  turns: ReactStepLimitTurnMeta[],
  hit: boolean,
): ReactStepLimitTurnMeta[] {
  const copy = [...turns];
  if (copy.length === 0) {
    copy.push(emptyReactStepLimitTurn());
  }
  copy[copy.length - 1] = { hit };
  return copy;
}

/** 最后一轮 QA 是否因步数触顶结束。 */
export function lastQaTurnHitStepLimit(
  turns: ReactStepLimitTurnMeta[],
): boolean {
  if (turns.length === 0) {
    return false;
  }
  return turns[turns.length - 1]?.hit === true;
}

/** 从已归档 messages 推断触顶轮次（无 react_step_limit_turns 字段时）。 */
export function inferReactStepLimitTurns(
  messages: { role: string; content: string }[],
): ReactStepLimitTurnMeta[] {
  const turns: ReactStepLimitTurnMeta[] = [];
  for (let i = 0; i < messages.length; i += 1) {
    if (messages[i]?.role !== "user") {
      continue;
    }
    const assistant = messages[i + 1];
    if (!assistant || assistant.role !== "assistant") {
      turns.push(emptyReactStepLimitTurn());
      continue;
    }
    const content = assistant.content ?? "";
    const hit = LEGACY_SUFFIX_MARKERS.some((mk) => content.includes(mk));
    turns.push(hit ? { hit: true } : emptyReactStepLimitTurn());
  }
  return turns;
}

function dedupeMirroredReasoning(text: string): string {
  const t = text.trim();
  if (t.length < 80) {
    return text;
  }
  const mid = Math.floor(t.length / 2);
  const a = t.slice(0, mid).trim();
  const b = t.slice(mid).trim();
  if (a.length > 0 && a === b) {
    return a;
  }
  return text;
}

export function finalizeStreamAssistantMessage(
  messages: import("../types/chat").ChatMessage[],
  acc: { assistantText: string; reasoningText: string },
  opts: { stripSuffix: boolean },
): import("../types/chat").ChatMessage[] {
  const copy = [...messages];
  const last = copy.length - 1;
  if (last < 0 || copy[last]?.role !== "assistant") {
    return copy;
  }
  let content = acc.assistantText || copy[last].content || "";
  if (opts.stripSuffix) {
    content = stripStepLimitSuffix(content);
  }
  let reasoning = dedupeMirroredReasoning(
    acc.reasoningText || copy[last].reasoning || "",
  );
  copy[last] = {
    ...copy[last],
    content,
    ...(reasoning ? { reasoning } : {}),
  };
  return copy;
}
