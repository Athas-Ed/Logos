import { Outlet, useLocation } from "react-router-dom";
import { AppShellToolbar } from "./AppShellToolbar";
import { TabBar } from "./TabBar";
import styles from "./AppShell.module.css";

export function AppShell() {
  const location = useLocation();
  const onTaskRoute =
    location.pathname.startsWith("/chat/") ||
    location.pathname.startsWith("/task/") ||
    location.pathname.startsWith("/lab/") ||
    location.pathname.startsWith("/review/");

  return (
    <div className={styles.shell}>
      {onTaskRoute ? (
        <>
          <TabBar />
          <AppShellToolbar />
        </>
      ) : null}
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
