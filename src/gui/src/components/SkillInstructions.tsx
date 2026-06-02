import { getSkillMeta } from "../skills/registry";
import styles from "./SkillInstructions.module.css";

type Props = {
  skillId: string;
};

/** 按 skill_id 展示 manifest 中的「技能说明」（ui_instructions），
 *  默认展开，可折叠以节省屏幕空间。 */
export function SkillInstructions({ skillId }: Props) {
  const text = getSkillMeta(skillId)?.ui_instructions?.trim();
  if (!text) {
    return null;
  }

  return (
    <details
      className={styles.block}
      open
      data-testid="skill-instructions"
    >
      <summary className={styles.summary}>
        技能说明
      </summary>
      <p className={styles.body}>{text}</p>
    </details>
  );
}
