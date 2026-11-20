// REST client and TanStack Query hooks for the VTAgent API (SDD §9).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ConversationDetail,
  ConversationOut,
  DocumentDetail,
  DocumentOut,
  OutlineNode,
  PassageOut,
  ReviewRunOut,
  RuleIn,
  RuleOut,
} from "./types";

export const API = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "content-type": "application/json", "x-vtagent": "1", ...init?.headers },
  });
  if (!res.ok) {
    const problem = await res.json().catch(() => ({}));
    throw new ApiError(res.status, problem.code ?? "error", problem.detail ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Save an export file the API produces (FR-31). */
export async function download(path: string) {
  const res = await fetch(`${API}${path}`, { headers: { "x-vtagent": "1" } });
  if (!res.ok) throw new ApiError(res.status, "error", res.statusText);
  const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "vtagent-export";
  const url = URL.createObjectURL(await res.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  link.click();
  URL.revokeObjectURL(url);
}

interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

// Documents
export const useDocuments = () =>
  useQuery({ queryKey: ["documents"], queryFn: () => api<Page<DocumentOut>>("/documents").then((p) => p.items) });

export const useDocument = (id: string | undefined) =>
  useQuery({
    queryKey: ["documents", id],
    queryFn: () => api<DocumentDetail>(`/documents/${id}`),
    enabled: id !== undefined,
  });

/** The original file, to show cited pages as they look in the source (FR-20). */
export const useDocumentFile = (id: string | undefined) =>
  useQuery({
    queryKey: ["documents", id, "file"],
    queryFn: async () => {
      const res = await fetch(`${API}/documents/${id}/file`, { headers: { "x-vtagent": "1" } });
      if (!res.ok) throw new ApiError(res.status, "error", res.statusText);
      return res.blob();
    },
    enabled: id !== undefined,
    staleTime: Infinity,
  });

export const useOutline = (id: string) =>
  useQuery({ queryKey: ["documents", id, "outline"], queryFn: () => api<OutlineNode>(`/documents/${id}/outline`) });

export function useDeleteDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["documents"] });
      client.invalidateQueries({ queryKey: ["conversations"] }); // answers citing it are gone (BR10)
    },
  });
}

export const usePassage = (chunkId: string | undefined) =>
  useQuery({
    queryKey: ["passages", chunkId],
    queryFn: () => api<PassageOut>(`/passages/${chunkId}`),
    enabled: chunkId !== undefined,
  });

// Reviews
export const useLatestReview = (documentId: string) =>
  useQuery({
    queryKey: ["documents", documentId, "review"],
    queryFn: () =>
      api<ReviewRunOut>(`/documents/${documentId}/reviews/latest`).catch((e) =>
        e instanceof ApiError && e.status === 404 ? null : Promise.reject(e),
      ),
    // Poll while a run is in progress.
    refetchInterval: (query) => (query.state.data?.status === "running" ? 700 : false),
  });

export function useStartReview(documentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<ReviewRunOut>(`/documents/${documentId}/reviews`, { method: "POST" }),
    onSuccess: (run) => client.setQueryData(["documents", documentId, "review"], run),
  });
}

// Rules
export const useRules = () => useQuery({ queryKey: ["rules"], queryFn: () => api<RuleOut[]>("/rules") });

export function useSaveRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...rule }: Partial<RuleIn> & { id?: string }) =>
      id
        ? api<RuleOut>(`/rules/${id}`, { method: "PATCH", body: JSON.stringify(rule) })
        : api<RuleOut>("/rules", { method: "POST", body: JSON.stringify(rule) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["rules"] }),
  });
}

// Conversations
export const useConversations = () =>
  useQuery({
    queryKey: ["conversations"],
    queryFn: () => api<Page<ConversationOut>>("/conversations").then((p) => p.items),
  });

export const useConversation = (id: string) =>
  useQuery({ queryKey: ["conversations", id], queryFn: () => api<ConversationDetail>(`/conversations/${id}`) });

export function useUpdateConversation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: string; pinned?: boolean; title?: string }) =>
      api<ConversationOut>(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["conversations"] }),
  });
}

export function useDeleteConversation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["conversations"] }),
  });
}

export function useCreateConversation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (title: string) =>
      api<ConversationOut>("/conversations", { method: "POST", body: JSON.stringify({ title }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
