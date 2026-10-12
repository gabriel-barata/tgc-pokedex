import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client.ts";
import type { components } from "@/api/schema.gen.ts";

export type SyncRunEntry = components["schemas"]["SyncRunEntry"];

const syncKey = ["sync"] as const;
const runningPollMs = 2000;
const conflict = 409;

export function useSyncStatus() {
  return useQuery({
    queryKey: syncKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/sync");
      if (data === undefined) {
        throw new Error(`Reading the sync status failed with HTTP ${String(response.status)}`);
      }
      return data;
    },
    refetchInterval: ({ state }) => (state.data?.running ? runningPollMs : false),
  });
}

export function useSyncNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST("/api/sync");
      if (!response.ok && response.status !== conflict) {
        throw new Error(`Starting a sync failed with HTTP ${String(response.status)}`);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: syncKey }),
  });
}
