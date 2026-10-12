const plural = (count: number, one: string, many: string) =>
  `${String(count)} ${count === 1 ? one : many}`;

export const statusStrings = {
  runs: "Sincronizações",
  syncNow: "Sincronizar agora",
  syncing: "Sincronização em andamento",
  syncError: "Não foi possível iniciar a sincronização.",
  loading: "Carregando sincronizações…",
  loadError: "Não foi possível carregar as sincronizações.",
  retry: "Tentar novamente",
  noRuns: "Nenhuma sincronização ainda.",
  failures: "Falhas",
  kind: { catalog: "Catálogo", images: "Imagens" },
  status: {
    running: "Em andamento",
    succeeded: "Concluída",
    partial: "Parcial",
    failed: "Falhou",
  },
  failureKind: (kind: string) =>
    ({ card: "Carta", set: "Coleção", logo: "Logo", symbol: "Símbolo" })[kind] ?? kind,
  counts: (fetched: number, updated: number, failed: number) =>
    [
      plural(fetched, "buscado", "buscados"),
      plural(updated, "alterado", "alterados"),
      plural(failed, "falha", "falhas"),
    ].join(" · "),
  showFailures: (count: number) => `Ver ${plural(count, "falha", "falhas")}`,
  duration: (ms: number) => {
    const seconds = Math.round(ms / 1000);
    if (seconds < 60) return `${String(seconds)} s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${String(minutes)} min ${String(seconds % 60)} s`;
    return `${String(Math.floor(minutes / 60))} h ${String(minutes % 60)} min`;
  },
} as const;
