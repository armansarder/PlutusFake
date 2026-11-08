import { SyntheticDataAdapter } from "@/mocks/syntheticSimulationAdapter";
import { financialSnapshotSchema, type FinancialDataAdapter } from "@/types/financial";
import { requestJson, resolveBaseUrl } from "./apiClient";
import { API_BASE_URL, DATA_MODE } from "./config";

/** Future: GET /api/v1/financial/snapshot — the server identifies the user from its session. */
export class HttpFinancialDataAdapter implements FinancialDataAdapter {
  readonly source = "nessie_sandbox" as const;
  constructor(private baseUrl = resolveBaseUrl(API_BASE_URL, import.meta.env.PROD)) {}
  getSnapshot(signal?: AbortSignal) {
    return requestJson(this.baseUrl, "/api/v1/financial/snapshot", financialSnapshotSchema, { signal });
  }
}

export const financialDataAdapter: FinancialDataAdapter =
  DATA_MODE === "remote" ? new HttpFinancialDataAdapter() : new SyntheticDataAdapter();

export const snapshotQueryOptions = {
  queryKey: ["financial-snapshot"] as const,
  queryFn: ({ signal }: { signal: AbortSignal }) => financialDataAdapter.getSnapshot(signal),
  staleTime: Infinity,
};
