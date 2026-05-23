import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchBootstrap } from "../api/bootstrap";
import { totalConversationBytesIpc, isConversationIpcAvailable } from "../conversation/ipc";
import { formatByteSize } from "../pages/cacheFormat";
import {
  isCacheWarnSnoozed,
  readCacheWarnThresholdBytes,
  snoozeCacheWarnForSevenDays,
} from "../preferences/cacheWarnPrefs";
import { resolveBootstrapUi } from "../types/bootstrap";
import styles from "./CacheStartupBanner.module.css";

export function CacheStartupBanner() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [totalBytes, setTotalBytes] = useState(0);
  const [thresholdBytes, setThresholdBytes] = useState(0);

  useEffect(() => {
    void (async () => {
      if (!isConversationIpcAvailable()) {
        return;
      }
      if (isCacheWarnSnoozed()) {
        return;
      }
      const bootstrap = await fetchBootstrap();
      const ui = resolveBootstrapUi(bootstrap?.ui);
      const threshold = readCacheWarnThresholdBytes(ui.cache_warn_bytes);
      const total = await totalConversationBytesIpc();
      if (total >= threshold) {
        setTotalBytes(total);
        setThresholdBytes(threshold);
        setOpen(true);
      }
    })();
  }, []);

  const dismissLater = useCallback(() => {
    setOpen(false);
  }, []);

  const dismissWeek = useCallback(() => {
    snoozeCacheWarnForSevenDays();
    setOpen(false);
  }, []);

  const goSettings = useCallback(() => {
    setOpen(false);
    navigate("/settings");
  }, [navigate]);

  const goCache = useCallback(() => {
    setOpen(false);
    navigate("/cache");
  }, [navigate]);

  if (!open) {
    return null;
  }

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cache-warn-title"
      data-testid="cache-startup-warn"
    >
      <div className={styles.panel}>
        <h2 id="cache-warn-title" className={styles.title}>
          会话缓存占用较高
        </h2>
        <p className={styles.body}>
          当前归档与会话 JSON 合计约{" "}
          <strong>{formatByteSize(totalBytes)}</strong>，已超过告警阈值{" "}
          <strong>{formatByteSize(thresholdBytes)}</strong>。可在设置中调整阈值，或在「已归档会话」页恢复或销毁。
        </p>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.primaryBtn}
            data-testid="cache-warn-go-cache"
            onClick={goCache}
          >
            已归档会话
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="cache-warn-go-settings"
            onClick={goSettings}
          >
            设置
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="cache-warn-later"
            onClick={dismissLater}
          >
            稍后提醒
          </button>
          <button
            type="button"
            className={styles.ghostBtn}
            data-testid="cache-warn-snooze-7d"
            onClick={dismissWeek}
          >
            7 天内不再提醒
          </button>
        </div>
      </div>
    </div>
  );
}
