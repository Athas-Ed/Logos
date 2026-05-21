import { getSkillMeta } from "../skills/registry";
import styles from "./SkillInstructions.module.css";

type Props = {
  skillId: string;
};

/** 按 skill_id 展示 manifest 中的「技能说明」（ui_instructions）。 */
export function SkillInstructions({ skillId }: Props) {
  const text = getSkillMeta(skillId)?.ui_instructions?.trim();
  if (!text) {
    return null;
  }

  return (
    <section
      className={styles.block}
      aria-labelledby="skill-instructions-title"
      data-testid="skill-instructions"
    >
      <h2 id="skill-instructions-title" className={styles.title}>
        技能说明
      </h2>
      <p className={styles.body}>{text}</p>
    </section>
  );
}
