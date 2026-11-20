// Interface state shared across panels: the question scope and the open source.
import { create } from "zustand";

/** A passage the source panel can show: a citation of an answer, or evidence of a finding. */
export interface SourceRef {
  label: string; // "S1"
  chunkId: string;
}

interface UiState {
  /** Documents the next question is limited to; empty means every document (FR-14). */
  scope: string[];
  toggleScope: (documentId: string) => void;
  addScope: (documentId: string) => void;
  setScope: (documentIds: string[]) => void;
  clearScope: () => void;
  /** Passages of the answer or finding being read, and the one shown in the source panel. */
  sources: SourceRef[];
  activeLabel: string | null;
  openSource: (sources: SourceRef[], label: string) => void;
  closeSource: () => void;
}

export const useUi = create<UiState>((set) => ({
  scope: [],
  toggleScope: (id) =>
    set((s) => ({ scope: s.scope.includes(id) ? s.scope.filter((x) => x !== id) : [...s.scope, id] })),
  addScope: (id) => set((s) => (s.scope.includes(id) ? s : { scope: [...s.scope, id] })),
  setScope: (scope) => set({ scope }),
  clearScope: () => set({ scope: [] }),
  sources: [],
  activeLabel: null,
  openSource: (sources, label) => set({ sources, activeLabel: label }),
  closeSource: () => set({ activeLabel: null }),
}));
