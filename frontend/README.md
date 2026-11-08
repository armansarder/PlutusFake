# Welcome to your Lovable project

## Plutus Stage 1 — simplified multi-page edition

Six focused pages: Home (/), Current Situation (/dashboard), Monthly Plan (/monthly-plan), Simulator (/simulator), Cash Flow (/cash-flow) and Suggestions (/suggestions). Synthetic cash starts at $1,800; November income estimate is $3,200, allocations $3,100 and unallocated money $100. Fun has $40 remaining. A $120 concert exceeds its plan by $80 while checking stays positive; approving an $80 allocation increase preserves $600 planned savings and leaves $20 unallocated.

- Financial contracts: `src/types/financial.ts`, validated with Zod at adapter ingress.
- Temporary budget reads/drafts/approval: `BudgetPlanAdapter` in `src/services/budgets.ts`; synthetic fixture and state in `src/mocks/`. Plan edits reset on reload.
- Last submitted hypothetical requests stay in React memory across client navigation. Cash Flow recalculates through SimulationAdapter against the current approved plan. Suggestions are labeled example prompts, not live AI.
- Deterministic mock simulation: `src/mocks/syntheticSimulationAdapter.ts` and `assessBudget.ts`. Shared results drive category bars, savings, comparisons, explanations and cash charts.
- Shiv's future service replaces adapters through `DATA_MODE` in `src/services/config.ts`. HTTP adapters are defined but not called in demo mode. No silent synthetic fallback after remote errors.
- Arman's future budget proposal enters through `BudgetProposalAdapter` and `budgetProposalSchema`. Proposals are unapproved until the user reviews/edits/confirms; no Nemotron call is implemented.
- December's plan is deliberately unavailable. December comparisons show unknown budget/savings impact; cash forecasts disclose absent December bills and undated earmarks. Goal delay is not estimated without a deadline and confirmed contribution schedule.
- Tests: `bunx vitest run`; accounting uses integer cents and end-of-day date-only aggregation. See `SECURITY_HANDOFF.md` for frontend protections and hosting/backend responsibilities.
- No Phase 2 integrations, account linking, sign-in, database, alerts, historical ledger, investing functionality, or payment execution were added. Investing is only a future-feature note.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Open your project in the [Lovable editor](https://lovable.dev) and keep building.

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: connect the project to GitHub and every change made in Lovable is committed straight to your repository.
- **Full ownership**: this code is yours. Push to your repository and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS
