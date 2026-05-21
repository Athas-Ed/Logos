import { HashRouter } from "react-router-dom";
import { ConversationProvider } from "./conversation/ConversationProvider";
import { AppRoutes } from "./routes/AppRoutes";

export function App() {
  return (
    <HashRouter>
      <ConversationProvider>
        <AppRoutes />
      </ConversationProvider>
    </HashRouter>
  );
}
