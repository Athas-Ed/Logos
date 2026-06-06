import { useCallback, useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import type { LlmMode } from "../api/bootstrap";
import { fetchBootstrap } from "../api/bootstrap";
import {
  fetchDeveloperUi,
  putPromptEcho,
} from "../api/developer";
import {
  useConversationActions,
} from "../conversation/ConversationProvider";
import type { ParadigmOverride } from "../conversation/storeTypes";
import {
  PRESENTATION_LABELS,
  persistPresentation,
} from "../preferences/chatPrefs";
import {
  OFFLINE_SKILL_NAMES,
  PARADIGM_LABELS,
  getOfflineSkillName,
} from "../skills/catalog";
import { getSkillMeta } from "../skills/registry";
import type { PresentationMode } from "../types/chat";
import styles from "./LabChatControls.module.css";

const PARADIGMS = Object.keys(PARADIGM_LABELS) as ParadigmOverride[];

type Props = {
  conversationId: string;
  skillId: string;
  paradigmOverride?: ParadigmOverride;
  presentation: PresentationMode;
};

export function LabChatControls({
  conversationId,
  skillId,
  paradigmOverride,
  presentation,
}: Props) {
  const baseId = useId();
  const actions = useConversationActions();
  const [llmMode, setLlmMode] = useState<LlmMode | null>(null);
  const [devUi, setDevUi] = useState<{
    show: boolean;
    promptEcho: boolean;
  } | null>(null);
  const [devBusy, setDevBusy] = useState(false);

  const manifestParadigm = getSkillMeta(skillId)?.paradigm ?? "dialogue";
  const effectiveParadigm = paradigmOverride ?? manifestParadigm;
  const canOverrideParadigm = llmMode === "stub" || Boolean(devUi?.show);

  useEffect(() => {
    void (async () => {
      const b = await fetchBootstrap();
      if (b?.llm_mode) {
        setLlmMode(b.llm_mode);
      } else {
        setLlmMode(null);
      }
    })();
    void (async () => {
      const s = await fetchDeveloperUi();
      if (!s?.show_dev_tools_ui) {
        setDevUi(null);
        return;
      }
      setDevUi({ show: true, promptEcho: s.prompt_echo });
    })();
  }, []);

  const patch = useCallback(
    (partial: Parameters<typeof actions.patchConversation>[1]) => {
      actions.patchConversation(conversationId, partial);
    },
    [actions, conversationId],
  );

  const onSkillChange = useCallback(
    (nextSkill: string) => {
      const name = getSkillMeta(nextSkill)?.display_name ?? getOfflineSkillName(nextSkill) ?? nextSkill;
      patch({
        skillId: nextSkill,
        paradigmOverride: undefined,
        title: `试验 · ${name}`,
      });
    },
    [patch],
  );

  const onParadigmChange = useCallback(
    (value: string) => {
      if (value === "manifest") {
        patch({ paradigmOverride: undefined });
        return;
      }
      patch({ paradigmOverride: value as ParadigmOverride });
    },
    [patch],
  );

  return (
    <section
      className={styles.bar}
      aria-label="范式试验台控制"
      data-testid="lab-chat-controls"
    >
      <div className={styles.row}>
        <span
          className={
            llmMode === "stub" ? styles.badgeStub : styles.badgeRemote
          }
          data-testid="lab-llm-mode"
        >
          LLM：{llmMode === "stub" ? "桩模式" : llmMode === "remote" ? "远程 API" : "检测中…"}
        </span>
        <span className={styles.badgeMeta} data-testid="lab-effective-paradigm">
          执行范式：{PARADIGM_LABELS[effectiveParadigm]}
          {paradigmOverride ?
            "（已覆盖 manifest）"
          : `（manifest · ${manifestParadigm}）`}
        </span>
        <Link to="/" className={styles.link}>
          技能面板
        </Link>
        <Link to="/settings" className={styles.link}>
          设置
        </Link>
      </div>
      <div className={styles.grid}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${baseId}-skill`}>
            Skill（Prompt 模板）
          </label>
          <select
            id={`${baseId}-skill`}
            className={styles.select}
            data-testid="lab-skill-select"
            value={skillId}
            onChange={(e) => onSkillChange(e.target.value)}
          >
            {[...OFFLINE_SKILL_NAMES].sort((a, b) => a.skill_id.localeCompare(b.skill_id)).map((c) => (
              <option key={c.skill_id} value={c.skill_id}>
                {c.display_name} · {getSkillMeta(c.skill_id)?.paradigm ?? "dialogue"}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${baseId}-paradigm`}>
            范式（PR 覆盖）
          </label>
          <select
            id={`${baseId}-paradigm`}
            className={styles.select}
            data-testid="lab-paradigm-select"
            value={paradigmOverride ?? "manifest"}
            disabled={!canOverrideParadigm}
            title={
              canOverrideParadigm
                ? undefined
                : "需桩 LLM 或 developer.show_dev_tools_ui"
            }
            onChange={(e) => onParadigmChange(e.target.value)}
          >
            <option value="manifest">
              跟随 manifest（{manifestParadigm}）
            </option>
            {PARADIGMS.map((p) => (
              <option key={p} value={p}>
                {PARADIGM_LABELS[p]}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <span className={styles.label}>运行模式</span>
          <span className={styles.label}>作者模式</span>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${baseId}-pres`}>
            展示档位
          </label>
          <select
            id={`${baseId}-pres`}
            className={styles.select}
            data-testid="lab-presentation"
            value={presentation}
            onChange={(e) => {
              const mode = e.target.value as PresentationMode;
              persistPresentation(mode);
              patch({ presentation: mode });
            }}
          >
            {(Object.keys(PRESENTATION_LABELS) as PresentationMode[]).map(
              (m) => (
                <option key={m} value={m}>
                  {PRESENTATION_LABELS[m]}
                </option>
              ),
            )}
          </select>
        </div>
      </div>
      {devUi?.show ?
        <label className={styles.echoRow}>
          <input
            type="checkbox"
            data-testid="lab-prompt-echo"
            checked={devUi.promptEcho}
            disabled={devBusy}
            onChange={(e) => {
              const on = e.target.checked;
              setDevBusy(true);
              void (async () => {
                const ok = await putPromptEcho(on);
                if (ok) {
                  setDevUi((prev) =>
                    prev ? { ...prev, promptEcho: on } : prev,
                  );
                }
                setDevBusy(false);
              })();
            }}
          />
          Prompt 回显（不调用 LLM，检视 CB 拼装）
        </label>
      : import.meta.env.DEV ?
        <p className={styles.hint}>
          启用 Prompt 回显：在 <code>config/local.yaml</code> 设{" "}
          <code>developer.show_dev_tools_ui: true</code>，或使用{" "}
          <code>LOGOS_FORCE_STUB_LLM=1</code> 启动后端。
        </p>
      : null}
      <p className={styles.hint}>
        本页仅用于 Vite 开发：多轮对话 + 手动切换 Skill / 范式。产品任务请从技能面板进入。
      </p>
    </section>
  );
}
