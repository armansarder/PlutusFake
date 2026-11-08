import { createFileRoute, Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowRight, TrendingDown, CalendarClock, House } from "lucide-react";
import { PageHeading } from "@/components/app/PageHeading";
import { useDecision } from "@/components/app/DecisionContext";
import { MetricCard } from "@/components/financial/MetricCard";
import { CashFlowChart, ChartLegend } from "@/components/financial/CashFlowChart";
import { CashFlowEvents } from "@/components/financial/CashFlowEvents";
import { toSeries, SCENARIO_META } from "@/components/simulator/scenarioMeta";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { snapshotQueryOptions } from "@/services/financial";
import { budgetQueryOptions } from "@/services/budgets";
import { baselineQueryOptions, simulationAdapter } from "@/services/simulation";
import { formatMoney } from "@/lib/formatMoney";
import { formatDateOnly } from "@/lib/dateOnly";
export const Route = createFileRoute("/cash-flow")({
  loader: async ({ context }) => { const snap = await context.queryClient.ensureQueryData(snapshotQueryOptions); await Promise.all([context.queryClient.ensureQueryData(baselineQueryOptions(snap.snapshotId, snap.startDate)), context.queryClient.ensureQueryData(budgetQueryOptions(snap.startDate.slice(0, 7)))]); },
  head: () => ({ meta: [{ title: "30-day cash flow — Plutus" }, { name: "description", content: "Explore synthetic projected cash, important dates and the impact of your last hypothetical decision." }, { property: "og:title", content: "30-day cash flow — Plutus" }, { property: "og:description", content: "See when money comes in, when bills arrive and where things get tight." }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary_large_image" }] }), component: CashFlow,
});
function CashFlow() {
  const { data: snap } = useSuspenseQuery(snapshotQueryOptions);
  const { data: plan } = useSuspenseQuery(budgetQueryOptions(snap.startDate.slice(0, 7)));
  const { request } = useDecision();
  const { data } = useSuspenseQuery({ queryKey: ["decision-cash-flow", snap.snapshotId, request, plan], queryFn: ({ signal }) => request ? simulationAdapter.compareScenarios(request, signal) : baselineQueryOptions(snap.snapshotId, snap.startDate).queryFn({ signal }), staleTime: Infinity });
  const [visible, setVisible] = useState(["baseline", "buy-now", "buy-later"]);
  const [selectedId, setSelectedId] = useState("baseline");
  const selected = data.results.find(r => r.id === selectedId) ?? data.results[0];
  if (!selected) return <p role="alert">No cash forecast is available.</p>;
  const payday = selected.appliedEvents.find(e => e.amountCents > 0);
  const biggest = [...selected.appliedEvents].filter(e => e.type !== "purchase" && e.amountCents < 0).sort((a, b) => a.amountCents - b.amountCents)[0];
  const series = toSeries(data.results.filter(r => visible.includes(r.id)));
  return <div><PageHeading eyebrow="30-day cash flow" title="A look at what's next." description="Paydays, bills, and the moments in between. These are estimates, not a promise of money to come." /><section className="grid gap-4 md:grid-cols-3"><MetricCard icon={TrendingDown} label="Lowest projected cash" value={formatMoney(selected.lowestBalanceCents)} hint={formatDateOnly(selected.lowestBalanceDate)} tone={selected.liquidityConcern ? "caution" : "default"} /><MetricCard icon={CalendarClock} label="Next expected paycheck" value={payday ? formatMoney(payday.amountCents) : "Unknown"} hint={payday ? `${formatDateOnly(payday.date)} · assumed income` : undefined} /><MetricCard icon={House} label="Largest upcoming expense" value={biggest ? formatMoney(-biggest.amountCents) : "Unknown"} hint={biggest ? `${biggest.label} · ${formatDateOnly(biggest.date)}` : undefined} /></section>
    <section className="mt-8 border-y border-border py-7"><div className="mb-5 flex flex-wrap items-center justify-between gap-4"><h2 className="font-display text-2xl font-semibold">Your next 30 days</h2><div className="flex flex-wrap gap-4">{data.results.map(r => <label key={r.id} className="flex cursor-pointer items-center gap-2 text-sm"><Checkbox checked={visible.includes(r.id)} onCheckedChange={checked => setVisible(prev => checked ? [...prev, r.id] : prev.filter(id => id !== r.id))} />{SCENARIO_META[r.id]?.shortName ?? r.name}</label>)}</div></div><p className="mb-4 text-xs text-muted-foreground">{formatDateOnly(data.startDate)} – {formatDateOnly(data.endDate)} · end-of-day estimates</p>{series.length ? <div className="bg-card"><CashFlowChart series={series} events={selected.appliedEvents} bufferCents={request?.bufferCents ?? 20000} selectedId={selected.id} height={340} /></div> : <p className="py-20 text-center text-muted-foreground">No scenarios selected.</p>}<ChartLegend series={series} /><p className="mt-5 rounded-md bg-caution-soft p-4 text-sm text-caution-foreground">December's plan and bills are missing. This forecast is incomplete beyond November; a positive balance alone doesn't mean a purchase fits your plan.</p></section>
    <section className="mt-8"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="font-display text-2xl font-semibold">Important dates</h2><div className="flex flex-wrap gap-2">{data.results.map(r => <Button key={r.id} size="sm" variant={selected.id === r.id ? "default" : "outline"} onClick={() => setSelectedId(r.id)}>{SCENARIO_META[r.id]?.shortName ?? r.name}</Button>)}</div></div><CashFlowEvents events={selected.appliedEvents} balances={new Map(selected.dailyBalances.map(d => [d.date, d.endOfDayBalanceCents]))} /><details className="mt-5 text-sm"><summary className="cursor-pointer text-primary">Forecast assumptions</summary><ul className="mt-3 list-disc space-y-2 pl-5 text-muted-foreground">{selected.assumptions.map(a => <li key={a}>{a}</li>)}</ul></details></section><Button asChild variant="outline" className="mt-8"><Link to="/simulator">{request ? "Change my decision" : "Compare a purchase"}<ArrowRight className="h-4 w-4" /></Link></Button>
  </div>;
}
