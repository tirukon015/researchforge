"use client";

/**
 * Live backend status, reading the real /health endpoint.
 *
 * It reports what the backend actually said - never an optimistic default -
 * because the whole point of the indicator is to distinguish "the analysis is
 * slow" from "nothing is listening".
 */

import { API_BASE_LABEL } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function BackendStatus() {
  const { health, refreshHealth } = useSession();

  const text =
    health.kind === "ok"
      ? `Backend online · v${health.data.version} · ${health.data.environment}`
      : health.kind === "down"
        ? "Backend offline"
        : "Checking backend…";

  const dot =
    health.kind === "ok" ? "dot--ok" : health.kind === "down" ? "dot--err" : "dot--wait";

  return (
    <button
      className="status"
      onClick={refreshHealth}
      disabled={health.kind === "loading"}
      title={`Backend: ${API_BASE_LABEL}. Click to re-check.`}
    >
      <span className={`dot ${dot}`} />
      {text}
    </button>
  );
}
