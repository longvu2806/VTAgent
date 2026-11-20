import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { AppShell } from "./app/AppShell";
import { ChatView } from "./features/chat/ChatView";
import { NewChat } from "./features/chat/NewChat";
import { DocumentPage } from "./features/documents/DocumentPage";
import { DocumentsPage } from "./features/documents/DocumentsPage";
import { RulesPage } from "./features/rules/RulesPage";

const rootRoute = createRootRoute({ component: AppShell });
const getParentRoute = () => rootRoute;

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    createRoute({ getParentRoute, path: "/", component: NewChat }),
    createRoute({ getParentRoute, path: "/c/$conversationId", component: ChatView }),
    createRoute({ getParentRoute, path: "/documents", component: DocumentsPage }),
    createRoute({ getParentRoute, path: "/documents/$documentId", component: DocumentPage }),
    createRoute({ getParentRoute, path: "/rules", component: RulesPage }),
  ]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
