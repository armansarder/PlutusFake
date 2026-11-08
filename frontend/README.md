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

## Current Situation backend integration

Only `/dashboard` switches data sources. Other pages retain Alex's independent
synthetic demo. Never treat their plans or simulations as belonging to the backend
customer. Backend mode shows unavailable savings and flexible spending until those
records are integrated.

From `frontend/`, set these in the PowerShell session that starts Vite:

```powershell
$env:VITE_SITUATION_DATA_MODE = 'remote'
# Use the same privately configured token as the running backend:
$env:FINPILOT_API_TOKEN = '<backend service token>'
$env:FINPILOT_BACKEND_URL = 'http://127.0.0.1:8000' # optional; this is the default
npm run dev -- --port 8080
```

Use `VITE_SITUATION_DATA_MODE=synthetic_demo` (the default) to retain the original
Alex page. Invalid mode values fail explicitly. Restart Vite after changing its
environment. For production, set the nonsecret mode at build time and supply the
token and backend URL to the server runtime. Use the full TanStack server build;
a static file host cannot serve this proxy. Never put the token in a `VITE_`
variable, browser storage, URLs, or committed files.

The browser requests only `GET /api/financial-data` on its own origin. The server
adds the bearer token, uses a fixed upstream path, forbids query parameters and
redirects, allows HTTP only on loopback, times out after 12 seconds, and returns
safe errors with no-store caching. JSON is validated at both boundaries, historical
records are omitted, and decimal strings convert exactly to safe integer cents.
Only USD is supported by the current page; other currencies are rejected rather
than mislabeled. Source notes, snapshot basis and individual estimated/confirmed
statuses remain visible. `synthetic_demo` is identified as synthetic; other customer
IDs are labeled configured backend data, without claiming they are live or complete.

The local proxy exposes the backend's configured single customer to callers able
to access the frontend server. Origin checks are not user authentication. Keep the
demo local; a shared deployment must protect the application/proxy with its existing
authenticated access boundary. This change does not add a login system.

Verify at `http://localhost:8080/dashboard`: backend mode should show the current
$800 snapshot for `synthetic_demo`, synthetic/estimated labels, upcoming events and
unavailable budget/savings cards. In browser Network tools, the request should be
same-origin with no service Authorization header. Stop the backend and reload:
an explicit error and Try again button should appear, never Alex's balance.
No backend token or source data is logged or persisted by this integration.

```powershell
npm test
npx tsc --noEmit
npm run build
```
