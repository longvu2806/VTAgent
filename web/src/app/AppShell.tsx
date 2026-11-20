import { Outlet } from "@tanstack/react-router";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { SourcePanel } from "@/features/sources/SourcePanel";
import { useUi } from "@/stores/ui";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const sourceOpen = useUi((s) => s.activeLabel !== null);
  return (
    <div className="flex h-dvh flex-col">
      <TopBar />
      <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
        <ResizablePanel id="sidebar" defaultSize={288} minSize={232} maxSize={420}>
          <Sidebar />
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel id="main" minSize={420}>
          <Outlet />
        </ResizablePanel>
        {sourceOpen && (
          <>
            <ResizableHandle />
            <ResizablePanel id="source" defaultSize="36" minSize={340}>
              <SourcePanel />
            </ResizablePanel>
          </>
        )}
      </ResizablePanelGroup>
    </div>
  );
}
