import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";

import { ChatPage } from "../components/ChatPage";

import { CachePage } from "../pages/CachePage";

import { SettingsPage } from "../pages/SettingsPage";

import { SkillPanelPage } from "../pages/SkillPanelPage";

import { TaskPage } from "../pages/TaskPage";



export function AppRoutes() {

  return (

    <Routes>

      <Route element={<AppShell />}>

        <Route index element={<SkillPanelPage />} />

        <Route path="task/:id" element={<TaskPage />} />

        <Route path="lab/:id" element={<ChatPage lab />} />

        <Route path="chat/:id" element={<ChatPage />} />

        <Route path="settings" element={<SettingsPage />} />

        <Route path="cache" element={<CachePage />} />

        <Route path="*" element={<Navigate to="/" replace />} />

      </Route>

    </Routes>

  );

}

