import { useState, useCallback } from "react";
import { RolePicker } from "./RolePicker";
import styles from "./OutlineForm.module.css";

export interface OutlineFormProps {
  inputProperties: Record<string, { title?: string; description?: string; type?: string }>;
  inputRequired: string[];
  ksfsRoles: { name: string; path: string }[];
  ksfsLocations: { name: string; path: string }[];
  streaming: boolean;
  queued: boolean;
  onSubmit: (userText: string, taskFields: Record<string, unknown>) => void;
}

export function OutlineForm({
  inputProperties,
  inputRequired,
  ksfsRoles,
  ksfsLocations,
  streaming,
  queued,
  onSubmit,
}: OutlineFormProps) {
  const [formFields, setFormFields] = useState<Record<string, string>>({});
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [tempRoles, setTempRoles] = useState<string[]>([]);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [tempLocations, setTempLocations] = useState<string[]>([]);

  const handleSubmit = useCallback(() => {
    const allRoles = [...selectedRoles, ...tempRoles.map((n) => `临时角色-${n}`)];
    const allLocations = [...selectedLocations, ...tempLocations.map((n) => `临时地点-${n}`)];
    const charactersStr = allRoles.join("，");
    const locationsStr = allLocations.join("，");

    const lines: string[] = [];
    const topic = formFields.topic?.trim();
    const synopsis = formFields.synopsis?.trim();
    if (topic) lines.push(`主题：${topic}`);
    if (synopsis) lines.push(`主要事件梗概：${synopsis}`);
    if (charactersStr) lines.push(`主要相关角色：${charactersStr}`);
    if (locationsStr) lines.push(`事件地点：${locationsStr}`);
    const userText = lines.join("\n") || "请生成创作大纲";

    const taskFields: Record<string, unknown> = {};
    if (topic) taskFields.topic = topic;
    if (synopsis) taskFields.synopsis = synopsis;
    taskFields.characters = charactersStr;
    if (locationsStr) taskFields.locate = locationsStr;

    onSubmit(userText, taskFields);
  }, [formFields, selectedRoles, tempRoles, selectedLocations, tempLocations, onSubmit]);

  const disabled = streaming || queued;
  const roleFilled = (selectedRoles.length + tempRoles.length) > 0;
  const synopsisFilled = Boolean(formFields.synopsis?.trim());
  const canSubmit = synopsisFilled && roleFilled && !disabled;

  const textFields = Object.entries(inputProperties).filter(
    ([key]) => key !== "characters" && key !== "locate",
  );

  return (
    <div className={styles.form} data-testid="outline-form">
      {textFields.map(([key, prop]) => {
        if (typeof prop !== "object" || !prop) return null;
        const title = (prop as Record<string, unknown>).title as string || key;
        const desc = (prop as Record<string, unknown>).description as string || "";
        const required = inputRequired.includes(key);
        return (
          <div key={key} className={styles.field}>
            <label className={styles.label} htmlFor={`field-${key}`}>
              {title}{required ? " *" : ""}
            </label>
            {desc ? <span className={styles.muted}>{desc}</span> : null}
            <textarea
              id={`field-${key}`}
              className={styles.textarea}
              data-testid={`outline-field-${key}`}
              rows={key === "synopsis" ? 4 : 2}
              placeholder={desc || title}
              value={formFields[key] ?? ""}
              disabled={disabled}
              onChange={(e) => setFormFields((prev) => ({ ...prev, [key]: e.target.value }))}
            />
          </div>
        );
      })}

      {inputProperties.characters ?
        <RolePicker
          label="主要相关角色"
          description={inputRequired.includes("characters") ? undefined : undefined}
          items={ksfsRoles}
          selected={selectedRoles}
          tempItems={tempRoles}
          required
          tempLabel="新增角色"
          tempPlaceholder="输入临时角色名"
          tempPrefix="临时角色"
          streaming={streaming}
          queued={queued}
          onSelectedChange={setSelectedRoles}
          onTempItemsChange={setTempRoles}
        />
      : null}

      {inputProperties.locate ?
        <RolePicker
          label="事件地点"
          description={undefined}
          items={ksfsLocations}
          selected={selectedLocations}
          tempItems={tempLocations}
          tempLabel="新增地点"
          tempPlaceholder="输入临时地点名"
          tempPrefix="临时地点"
          streaming={streaming}
          queued={queued}
          onSelectedChange={setSelectedLocations}
          onTempItemsChange={setTempLocations}
        />
      : null}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primaryBtn}
          data-testid="outline-submit"
          disabled={!canSubmit}
          onClick={handleSubmit}
        >
          生成大纲
        </button>
        <button
          type="button"
          className={styles.secondaryBtn}
          data-testid="outline-reset"
          disabled={disabled}
          onClick={() => {
            setFormFields({});
            setSelectedRoles([]);
            setTempRoles([]);
            setSelectedLocations([]);
            setTempLocations([]);
          }}
        >
          重置
        </button>
      </div>
    </div>
  );
}
