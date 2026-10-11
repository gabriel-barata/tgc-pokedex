import { useQuery } from "@tanstack/react-query";
import { api } from "../api-client.ts";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, response } = await api.GET("/healthz");
      if (!response.ok || data === undefined) {
        throw new Error(`Health check failed with HTTP ${String(response.status)}`);
      }
      return data;
    },
  });
}
