import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client.ts";
import type { components } from "@/api/schema.gen.ts";

export type SeriesEntry = components["schemas"]["SeriesEntry"];
export type SetEntry = components["schemas"]["SetEntry"];

const setsKey = ["sets"] as const;
const downloadPollMs = 3000;

function isDownloading(series: SeriesEntry[] | undefined) {
  return series?.some(({ sets }) => sets.some(({ downloading }) => downloading)) ?? false;
}

export function useSets() {
  return useQuery({
    queryKey: setsKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/sets");
      if (data === undefined) {
        throw new Error(`Listing sets failed with HTTP ${String(response.status)}`);
      }
      return data;
    },
    refetchInterval: ({ state }) => (isDownloading(state.data) ? downloadPollMs : false),
  });
}

export function useTrackSet(setId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tracked: boolean) => {
      const path = { params: { path: { set_id: setId } } };
      const { response } = tracked
        ? await api.PUT("/api/sets/{set_id}/tracking", path)
        : await api.DELETE("/api/sets/{set_id}/tracking", path);
      if (!response.ok) {
        throw new Error(`Tracking ${setId} failed with HTTP ${String(response.status)}`);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: setsKey }),
  });
}
