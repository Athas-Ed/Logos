import { useCallback, useEffect, useState } from "react";

import { useLocation, useNavigate, useParams } from "react-router-dom";

import {

  useConversationActions,

  useConversationMeta,

} from "../conversation/ConversationProvider";

import { fetchHealth } from "../api/health";

import styles from "./AppShellToolbar.module.css";



export function AppShellToolbar() {

  const location = useLocation();

  const navigate = useNavigate();

  const { id: routeId } = useParams<{ id: string }>();

  const actions = useConversationActions();

  const meta = useConversationMeta();

  const [healthOk, setHealthOk] = useState<boolean | null>(null);



  const onTaskRoute =

    location.pathname.startsWith("/chat/") ||

    location.pathname.startsWith("/task/") ||

    location.pathname.startsWith("/lab/") ||

    location.pathname.startsWith("/review/");



  const refreshHealth = useCallback(async () => {

    setHealthOk(await fetchHealth());

  }, []);



  useEffect(() => {

    if (!onTaskRoute) {

      return;

    }

    void refreshHealth();

    const timer = window.setInterval(() => void refreshHealth(), 180_000);

    return () => window.clearInterval(timer);

  }, [onTaskRoute, refreshHealth]);



  if (!onTaskRoute || !meta.ready) {

    return null;

  }



  return (

    <div className={styles.toolbar} data-testid="app-shell-toolbar">

      <button

        type="button"

        className={styles.btn}

        data-testid="back-to-skill-panel"

        onClick={() => navigate("/")}

      >

        返回技能面板

      </button>

      <button

        type="button"

        className={styles.btn}

        data-testid="open-settings"

        onClick={() => navigate("/settings")}

      >

        设置

      </button>

      {routeId ? (

        <button

          type="button"

          className={`${styles.btn} ${styles.btnDanger}`}

          data-testid="archive-current-tab"

          title="归档当前会话（从顶栏移除，JSON 仍保留）"

          onClick={() => actions.archiveTab(routeId)}

        >

          归档当前会话

        </button>

      ) : null}

      <div

        className={styles.health}

        data-testid="health-indicator"

        data-health={healthOk === null ? "unknown" : healthOk ? "ok" : "bad"}

        title={healthOk === null ? "未检测" : healthOk ? "后端正常" : "后端不可用"}

      >

        <span

          className={

            healthOk === null

              ? styles.healthDotUnknown

              : healthOk ? styles.healthDotOk : styles.healthDotBad

          }

        />

        <span>GET /api/v1/health</span>

      </div>

    </div>

  );

}


