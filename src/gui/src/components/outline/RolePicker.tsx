import { useState } from "react";
import styles from "./RolePicker.module.css";

export interface RolePickerProps {
  label: string;
  description?: string;
  items: { name: string; path: string }[];
  selected: string[];
  tempItems: string[];
  required?: boolean;
  tempLabel: string;
  tempPlaceholder: string;
  tempPrefix: string;
  streaming: boolean;
  queued: boolean;
  onSelectedChange: (selected: string[]) => void;
  onTempItemsChange: (temp: string[]) => void;
}

export function RolePicker({
  label,
  description,
  items,
  selected,
  tempItems,
  required,
  tempLabel,
  tempPlaceholder,
  tempPrefix,
  streaming,
  queued,
  onSelectedChange,
  onTempItemsChange,
}: RolePickerProps) {
  const [search, setSearch] = useState("");
  const [tempInput, setTempInput] = useState("");
  const [showTempInput, setShowTempInput] = useState(false);

  const allItems = [
    ...items.map((r) => ({ name: r.name, type: "ksfs" as const })),
    ...tempItems.map((n) => ({ name: `${tempPrefix}-${n}`, type: "temp" as const })),
  ];
  const filtered = search ? allItems.filter((r) => r.name.includes(search)) : allItems;
  const hasSelection = selected.length + tempItems.length > 0;

  const toggleItem = (name: string, isKsfs: boolean) => {
    if (isKsfs) {
      onSelectedChange(
        selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name],
      );
    } else {
      const raw = name.replace(`${tempPrefix}-`, "");
      onTempItemsChange(
        tempItems.includes(raw) ? tempItems.filter((n) => n !== raw) : [...tempItems, raw],
      );
    }
  };

  const addTemp = () => {
    const v = tempInput.trim();
    if (v) {
      onTempItemsChange([...tempItems, v]);
      setTempInput("");
      setShowTempInput(false);
    }
  };

  return (
    <div className={styles.field}>
      <label className={styles.label}>
        {label}
        {required ? " *" : ""}
      </label>
      {description ? <span className={styles.muted}>{description}</span> : null}
      <input
        type="text"
        className={styles.search}
        placeholder={`搜索${label}…`}
        value={search}
        disabled={streaming || queued}
        onChange={(e) => setSearch(e.target.value)}
      />
      {filtered.length > 0 ?
        <div className={styles.chips}>
          {filtered.map((item) => {
            const isKsfs = item.type === "ksfs";
            const isSelected = isKsfs
              ? selected.includes(item.name)
              : tempItems.includes(item.name.replace(`${tempPrefix}-`, ""));
            return (
              <button
                key={item.name}
                type="button"
                className={`${styles.chip} ${isSelected ? styles.chipSelected : ""}`}
                data-testid={`chip-${item.name}`}
                disabled={streaming || queued}
                onClick={() => toggleItem(item.name, isKsfs)}
              >
                {item.name}
                {isSelected ? " ✓" : ""}
              </button>
            );
          })}
        </div>
      : items.length === 0 && tempItems.length === 0 ?
        <span className={styles.muted}>暂无可用条目</span>
      : null}
      <div className={styles.actions}>
        {showTempInput ?
          <div className={styles.tempRow}>
            <input
              type="text"
              className={styles.tempInput}
              placeholder={tempPlaceholder}
              value={tempInput}
              autoFocus
              disabled={streaming || queued}
              onChange={(e) => setTempInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") addTemp();
                if (e.key === "Escape") {
                  setTempInput("");
                  setShowTempInput(false);
                }
              }}
            />
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={!tempInput.trim()}
              onClick={addTemp}
            >
              添加
            </button>
          </div>
        :
          <button
            type="button"
            className={styles.secondaryBtn}
            disabled={streaming || queued}
            onClick={() => setShowTempInput(true)}
          >
            + {tempLabel}
          </button>
        }
      </div>
      {hasSelection ?
        <span className={styles.muted}>
          已选 {selected.length + tempItems.length} 个：
          {[
            ...selected,
            ...tempItems.map((n) => `${tempPrefix}-${n}`),
          ].join("、")}
        </span>
      : null}
    </div>
  );
}
