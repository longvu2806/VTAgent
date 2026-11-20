import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "next-themes";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "streamdown/styles.css";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { queryClient } from "@/lib/query";
import "./index.css";
import { router } from "./router";

async function enableMocks() {
  if (import.meta.env.VITE_MOCK !== "1") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledFrame: "bypass", quiet: true });
}

enableMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      {/* The theme script only matters for server rendering; as a data block React does not flag it. */}
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
        scriptProps={{ type: "application/json" }}
      >
        <QueryClientProvider client={queryClient}>
          <TooltipProvider delay={300}>
            <RouterProvider router={router} />
            <Toaster />
          </TooltipProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </StrictMode>,
  );
});
