import { healthStrings } from "./strings.ts";
import { useHealth } from "./use-health.ts";

const textByQueryStatus = {
  pending: healthStrings.checking,
  error: healthStrings.offline,
  success: healthStrings.online,
} as const;

export function HealthStatus() {
  const { status } = useHealth();
  return <p role="status">{textByQueryStatus[status]}</p>;
}
