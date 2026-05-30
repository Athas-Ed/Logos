import { REACT_STEP_LIMIT_NOTICE } from "../conversation/reactStepLimit";
import styles from "./ReactStepLimitNotice.module.css";

type Props = {
  /** 输入区顶栏（当前轮触顶） */
  variant?: "inline" | "banner";
};

/** ReAct 范式：步数触顶说明（与 assistant 正文分离展示）。 */
export function ReactStepLimitNotice({ variant = "inline" }: Props) {
  const className = variant === "banner" ? styles.banner : styles.inline;
  return (
    <p
      className={className}
      role="status"
      data-testid="react-step-limit-notice"
    >
      {REACT_STEP_LIMIT_NOTICE}
    </p>
  );
}
