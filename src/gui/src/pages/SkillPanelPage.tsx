import { useEffect, useState } from "react";

import { Link } from "react-router-dom";

import { fetchBootstrap } from "../api/bootstrap";

import { useConversationActions } from "../conversation/ConversationProvider";

import { FALLBACK_PANEL_SKILLS, type SkillCardMeta } from "../skills/catalog";
import { hydrateSkillRegistry } from "../skills/registry";

import { skillUsesTaskWizard } from "../skills/routing";

import { panelSkillsFromBootstrap } from "../types/bootstrap";

import styles from "./SkillPanelPage.module.css";



export function SkillPanelPage() {

  const actions = useConversationActions();

  const [skills, setSkills] = useState<SkillCardMeta[]>([

    ...FALLBACK_PANEL_SKILLS,

  ]);

  const [skillsSource, setSkillsSource] = useState<"bootstrap" | "fallback">(

    "fallback",

  );



  useEffect(() => {

    void (async () => {

      const b = await fetchBootstrap();

      const fromApi = panelSkillsFromBootstrap(b?.skills);

      if (fromApi.length > 0) {
        hydrateSkillRegistry(fromApi);
        setSkills(fromApi);
        setSkillsSource("bootstrap");
      }

    })();

  }, []);



  return (

    <div className={styles.page} data-testid="skill-panel-page">

      <header className={styles.header}>

        <div>

          <h1 className={styles.title}>技能面板</h1>

          <p className={styles.subtitle}>

            选择一项 Skill 开始任务。列表来自{" "}

            <code>GET /api/v1/bootstrap</code>

            {skillsSource === "bootstrap" ? "（已连接）" : "（离线回退）"}。

          </p>

        </div>

        <Link

          to="/settings"

          className={styles.settingsLink}

          data-testid="skill-panel-settings"

        >

          设置

        </Link>

      </header>

      <section className={styles.devSection} aria-label="Vite 开发工具">

        <h2 className={styles.devTitle}>开发 / 手动验收（Vite）</h2>

        <p className={styles.devHint}>

          范式试验台可切换 Skill 与 Prompt 回显；多轮启发请用面板「创作启发对话」。

        </p>

        <div className={styles.devActions}>

          <button

            type="button"

            className={styles.devBtn}

            data-testid="open-lab-chat"

            onClick={() => actions.createLabTab()}

          >

            范式 / Prompt 试验台

          </button>

        </div>

      </section>

      <div className={styles.grid} role="list">

        {skills.map((skill) => (

          <button

            key={skill.skill_id}

            type="button"

            role="listitem"

            className={styles.card}

            data-testid={`skill-card-${skill.skill_id}`}

            onClick={() => {

              if (skillUsesTaskWizard(skill.skill_id)) {

                actions.createTask(skill.skill_id);

              } else {

                actions.createInspireChat(skill.skill_id);

              }

            }}

          >

            <span className={styles.cardName}>{skill.display_name}</span>

            <p className={styles.cardDesc}>{skill.description}</p>

            <span className={styles.cardMeta}>

              {skill.paradigm} · {skill.persistence_tier}

              {skill.turn_policy === "multi" ? " · 多轮" : ""}

            </span>

          </button>

        ))}

      </div>

    </div>

  );

}


