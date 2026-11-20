import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";

/** Shared so code outside components (the per-conversation chats) can refresh cached data. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A missing or invalid resource stays missing; only server and network errors are retried.
      retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 3,
    },
  },
});
