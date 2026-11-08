# Welcome to your Lovable project

## Plutus Stage 2/3 — shared customer data

Eight focused pages: Home (/), Current Situation (/dashboard), Monthly Plan (/monthly-plan), Simulator (/simulator), Cash Flow (/cash-flow), Suggestions (/suggestions), Alerts (/alerts) and Talk to Plutus (/talk). In Alex demo mode, synthetic cash starts at $1,800; November income estimate is $3,200, allocations $3,100 and unallocated money $100. Fun has $40 remaining. A $120 concert exceeds its plan by $80 while checking stays positive; approving an $80 allocation increase preserves $600 planned savings and leaves $20 unallocated. Backend-connected mode uses only the configured backend customer's records, with unavailable states for missing data and unconnected capabilities.

- Financial contracts: `src/types/financial.ts`, validated with Zod at adapter ingress.
- Temporary budget reads/drafts/approval: `BudgetPlanAdapter` in `src/services/budgets.ts`; synthetic fixture and state in `src/mocks/`. Plan edits reset on reload.
- Last submitted hypothetical requests stay in React memory across client navigation. Cash Flow recalculates through SimulationAdapter against the current approved plan. Suggestions are labeled example prompts, not live AI.
- Deterministic mock simulation: `src/mocks/syntheticSimulationAdapter.ts` and `assessBudget.ts`. Shared results drive category bars, savings, comparisons, explanations and cash charts.
- `VITE_DATA_MODE` selects the source through `src/services/config.ts`. Backend-connected snapshots use the existing secure FastAPI proxy; proposed simulator/history/budget/agent endpoints remain unconnected. No silent synthetic fallback after remote errors.
- Arman's future budget proposal enters through `BudgetProposalAdapter` and `budgetProposalSchema`. Proposals are unapproved until the user reviews/edits/confirms; no Nemotron call is implemented.
- December's plan is deliberately unavailable. December comparisons show unknown budget/savings impact; cash forecasts disclose absent December bills and undated earmarks. Goal delay is not estimated without a deadline and confirmed contribution schedule.
- Tests: `bunx vitest run`; accounting uses integer cents and end-of-day date-only aggregation. See `SECURITY_HANDOFF.md` for frontend protections and hosting/backend responsibilities.
- No Python simulator, Nemotron, Photon, account linking, sign-in, database, investing functionality, or payment execution is connected in this phase. Demo alerts and generated history remain confined to Alex mode.

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

## Application-wide customer data modes (Phase 1)

`VITE_DATA_MODE` selects one customer source for the entire application. It is
`synthetic_demo` by default (Alex's existing $1,800 frontend dataset), or `remote`
(the customer configured in FastAPI, currently the $800 `synthetic_demo` customer).
The old `VITE_SITUATION_DATA_MODE` variable remains an application-wide alias;
conflicting values fail explicitly. This is a startup/build setting, not a browser
customer selector. Restart Vite or rebuild to change modes.

All seven financial pages share the same snapshot adapter and mode-scoped query
cache through `services/financial.ts` and `CustomerFinancialData`. In remote mode,
Current Situation shows the supplied balance and upcoming income; Current Situation,
Cash Flow and Alerts show supplied upcoming transactions with provenance. Missing
category budgets, savings allocations and historical transactions are unavailable.
Alerts do not claim an all-clear. Forecasts, purchase comparisons, personalized
suggestions and chat are unavailable until later integrations. No Python simulator,
Nemotron or Photon connection is added. Alex's calculations, approved demo budgets,
history and assistant remain available only in `synthetic_demo` mode.

From `frontend/`, set these in the PowerShell session that starts Vite:

```powershell
$env:VITE_DATA_MODE = 'remote'
# Use the same privately configured token as the running backend:
$env:FINPILOT_API_TOKEN = '<backend service token>'
$env:FINPILOT_BACKEND_URL = 'http://127.0.0.1:8000' # optional; this is the default
npm run dev -- --port 8080
```

Use `VITE_DATA_MODE=synthetic_demo` (the default) for Alex on every page. Remove any
conflicting legacy `VITE_SITUATION_DATA_MODE` setting. Invalid mode values fail explicitly. Restart Vite after changing its
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

Visit `/monthly-plan`, `/simulator`, `/cash-flow`, `/alerts`, `/suggestions` and
`/talk`: every page must keep the backend customer identity, with honest unavailable
states and no Alex budget or transactions. Cash Flow and Alerts list only supplied
upcoming records. Stop the backend and refresh any financial page: it must show a
retryable error, never Alex's data. Restore the backend and choose Try again.

For Alex mode, set `$env:VITE_DATA_MODE = 'synthetic_demo'` and restart Vite. No
FastAPI service is needed. Confirm the $1,800 balance, $600 planned savings, monthly
plan editor, demo comparisons, alerts, suggestions and demo assistant still work.

Checks from `frontend/`: `npm test`, `npx tsc --noEmit`, `npm run build`.
Build a second time with `VITE_DATA_MODE=remote` to check backend-connected bundling.

```powershell
npm test
npx tsc --noEmit
npm run build
```
