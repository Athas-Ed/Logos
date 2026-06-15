import { HashRouter } from "react-router-dom";
import { CacheStartupBanner } from "./components/CacheStartupBanner";
import { LlmSetupDialog } from "./components/LlmSetupDialog";
import { ConversationProvider } from "./conversation/ConversationProvider";
import { AppRoutes } from "./routes/AppRoutes";

export function App() {
  return (
    <HashRouter>
      <ConversationProvider>
        <AppRoutes />
        <CacheStartupBanner />
        <LlmSetupDialog />
      </ConversationProvider>
    </HashRouter>
  );
}
