import { SyntheticDataAdapter } from "@/mocks/syntheticSimulationAdapter";
import type { FinancialDataAdapter, FinancialSnapshot } from "@/types/financial";
import { requestJson } from "./apiClient";
import { backendFinancialSchema } from "./backendFinancial";

export const SITUATION_DATA_MODE = import.meta.env["VITE_SITUATION_DATA_MODE"] ?? "synthetic_demo";
if (!["remote", "synthetic_demo"].includes(SITUATION_DATA_MODE)) throw new Error("Invalid Current Situation data mode");
export type SituationSnapshot = FinancialSnapshot & { backend?: { notes: string[]; synthetic: boolean; basis: string } };
export class BackendSituationAdapter implements FinancialDataAdapter {
  readonly source = "nessie_sandbox" as const;
  async getSnapshot(signal?: AbortSignal): Promise<SituationSnapshot> {
    const { data } = await requestJson("", "/api/financial-data", backendFinancialSchema, { signal });
    const synthetic = data.customer_id === "synthetic_demo";
    return {
      snapshotId: `backend:${data.customer_id}:${data.as_of_date}`, customer: { displayName: data.customer_id, persona: "Backend customer" },
      currency: data.currency, source: synthetic ? "synthetic_demo" : "nessie_sandbox", startDate: data.as_of_date,
      startingBalanceCents: data.current_balance,
      cashFlows: data.upcoming_transactions.map(t => ({ id: t.id, date: t.date, label: t.description, amountCents: t.amount, type: t.type, provenance: t.source_status === "estimated" ? "assumed" : "scheduled" })),
      backend: { notes: data.source_notes, synthetic, basis: data.snapshot_basis },
    };
  }
}
const adapter: FinancialDataAdapter = SITUATION_DATA_MODE === "remote" ? new BackendSituationAdapter() : new SyntheticDataAdapter();
export const situationQueryOptions = {
  queryKey: ["current-situation", SITUATION_DATA_MODE],
  queryFn: ({ signal }: { signal: AbortSignal }): Promise<SituationSnapshot> => adapter.getSnapshot(signal),
  retry: false, staleTime: 30000,
};
