import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, CalendarClock, PiggyBank, Wallet, Ticket } from "lucide-react";
import { PageHeading } from "@/components/app/PageHeading";
import { MetricCard } from "@/components/financial/MetricCard";
import { HealthIndicators } from "@/components/financial/HealthIndicators";
import { Milestones } from "@/components/financial/Milestones";
import { Button } from "@/components/ui/button";
import { formatDateOnly } from "@/lib/dateOnly";
import { formatMoney } from "@/lib/formatMoney";
import { rawRemaining, summarizePlan } from "@/lib/budgetMath";
import { snapshotQueryOptions } from "@/services/financial";
import { budgetQueryOptions } from "@/services/budgets";
import { situationQueryOptions, SITUATION_DATA_MODE } from "@/services/situation";
import { baselineQueryOptions } from "@/services/simulation";
import { yearHistoryQueryOptions } from "@/services/history";
export const Route = createFileRoute("/dashboard")({
  loader: async ({ context }) => {
    // The backend customer has no Alex demo plan, baseline or history.
    // Let BackendSituation own loading, errors and retry in remote mode.
    if (SITUATION_DATA_MODE === "remote") return;
    const snap = await context.queryClient.ensureQueryData(snapshotQueryOptions);
    await Promise.all([
      context.queryClient.ensureQueryData(budgetQueryOptions(snap.startDate.slice(0, 7))),
      context.queryClient.ensureQueryData(baselineQueryOptions(snap.snapshotId, snap.startDate)),
      context.queryClient.ensureQueryData(yearHistoryQueryOptions(Number(snap.startDate.slice(0, 4)))),
    ]);
  },
  head: () => ({ meta: [ { title: "Current situation — Plutus" }, { name: "description", content: "Your account snapshot, upcoming income and available planning information." }, { property: "og:title", content: "Current situation — Plutus" }, { property: "og:description", content: "See where you stand right now, one clear number at a time." }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary_large_image" } ] }), component: CurrentSituation,
});
function Situation() {
  const { data: snap } = useSuspenseQuery(snapshotQueryOptions);
  const { data: plan } = useSuspenseQuery(budgetQueryOptions(snap.startDate.slice(0, 7)));
  const { data: baseline } = useSuspenseQuery(baselineQueryOptions(snap.snapshotId, snap.startDate));
  const { data: history } = useSuspenseQuery(yearHistoryQueryOptions(Number(snap.startDate.slice(0, 4))));
  if (!plan) return <p role="alert">Your monthly plan needs review.</p>;
  const summary = summarizePlan(plan);
  const fun = plan.categories.find(c => c.categoryId === "fun");
  const payday = snap.cashFlows.find(e => e.type === "income" && e.date >= snap.startDate);
  const gap = (summary.deficit ?? 0) > 0;
  return <div><PageHeading eyebrow={`Hi, ${snap.customer.displayName} · ${formatDateOnly(snap.startDate)}`} title="Here's where you stand." description="A little clarity for today. Your balance is one part of the picture — your plan matters, too." />
    <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2"><MetricCard icon={Wallet} label="Current checking balance" value={formatMoney(snap.startingBalanceCents)} hint="What's in checking — not all available to spend" /><MetricCard icon={PiggyBank} label="Planned savings this month" value={formatMoney(summary.savings)} hint="Set aside in your plan · not yet transferred" tone={gap ? "caution" : "default"} /><MetricCard icon={Ticket} label="Available flexible spending" value={formatMoney(summary.flexibleRemaining)} hint="Left after spending and upcoming commitments" /><MetricCard icon={CalendarClock} label="Next expected payday" value={payday ? formatMoney(payday.amountCents) : "Needs review"} hint={payday ? `${formatDateOnly(payday.date, "EEE, MMM d")} · assumed income` : "No paycheck in the forecast"} /></section>
    <section className="mt-9 border-y border-border py-8"><span className="rounded-md bg-caution-soft px-3 py-1 text-xs font-semibold text-caution-foreground">{gap ? "Needs attention" : "Watch fun spending"}</span><h2 className="mt-4 font-display text-2xl font-semibold">{gap ? "Your plan needs a little adjustment." : "A little care with fun spending this week."}</h2><p className="mt-3 max-w-2xl text-muted-foreground">{gap ? `${formatMoney(summary.deficit ?? 0)} of your plan isn't covered by expected monthly income and known commitments.` : fun ? `You have ${formatMoney(Math.max(0, rawRemaining(fun)))} left for fun. Your ${formatMoney(summary.savings)} savings plan can stay intact — check a purchase before you commit.` : "Review your monthly categories before making a purchase."}</p></section>
    <HealthIndicators plan={plan} baseline={baseline.results[0] ?? null} />
    <Milestones plan={plan} history={history} />
    <div className="mt-8 flex flex-wrap gap-3"><Button asChild><Link to="/simulator">Try a decision <ArrowRight className="h-4 w-4" /></Link></Button><Button variant="outline" asChild><Link to="/monthly-plan">See my monthly plan</Link></Button></div>
  </div>;
}

function CurrentSituation() {
  return SITUATION_DATA_MODE === "remote" ? <BackendSituation /> : <Situation />;
}
export function BackendSituation() {
  const query = useQuery(situationQueryOptions);
  if (query.isPending) return <p role="status">Loading your current situation…</p>;
  if (query.isError) return <div role="alert"><h1 className="font-display text-2xl">Current situation unavailable</h1><p className="my-4">We couldn't load the backend snapshot. No demo data has been substituted.</p><Button onClick={() => void query.refetch()}>Try again</Button></div>;
  const snap = query.data;
  const payday = snap.cashFlows.filter(t => t.type === "income").sort((a, b) => a.date.localeCompare(b.date))[0];
  return <div><PageHeading eyebrow={`${snap.customer.displayName} · ${formatDateOnly(snap.startDate)}`} title="Here's where you stand." description="Your backend account snapshot and upcoming scheduled events." />
    <p className="mb-6 rounded-md bg-caution-soft p-3 text-sm">Backend data · {snap.backend?.synthetic ? "Synthetic demo dataset" : "Configured backend dataset"} · {snap.backend?.basis} snapshot. {snap.cashFlows.some(t => t.provenance === "assumed") ? "Includes estimated upcoming transactions." : "Upcoming transactions are marked confirmed by the source."} Schedule completeness is not verified.</p>
    <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2">
      <MetricCard icon={Wallet} label="Current checking balance" value={formatMoney(snap.startingBalanceCents)} hint="Snapshot balance · not all available to spend" />
      <MetricCard icon={PiggyBank} label="Planned savings this month" value="Unavailable" hint="Savings records have not been integrated for this customer" />
      <MetricCard icon={Ticket} label="Available flexible spending" value="Unavailable" hint="Budget records have not been integrated for this customer" />
      <MetricCard icon={CalendarClock} label="Next expected payday" value={payday ? formatMoney(payday.amountCents) : "Unavailable"} hint={payday ? `${formatDateOnly(payday.date)} · ${payday.provenance === "assumed" ? "estimated" : "confirmed"} income` : "No upcoming income supplied"} />
    </section>
    <section className="mt-9 border-y border-border py-8"><h2 className="font-display text-2xl font-semibold">Upcoming transactions</h2>{snap.cashFlows.length ? <ul className="mt-4 space-y-3">{snap.cashFlows.map(t => <li key={t.id} className="flex flex-wrap justify-between gap-2"><span>{t.label} · {formatDateOnly(t.date)} · {t.provenance === "assumed" ? "Estimated" : "Confirmed"}</span><span>{formatMoney(t.amountCents)}</span></li>)}</ul> : <p>No upcoming transactions supplied.</p>}{snap.backend?.notes.map((note, i) => <p key={i} className="mt-3 text-sm text-muted-foreground">{note}</p>)}</section>
    <p className="mt-6 text-sm text-muted-foreground">Other pages still use Alex's separate synthetic demo. Budget and savings information from that demo does not apply to this snapshot.</p>
  </div>;
}
