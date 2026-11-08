"""
Transform step: raw Nessie JSON -> clean, analysis-ready outputs.

Reads   pipeline/data/raw/*.json            (written by extract.py)
Writes  pipeline/data/clean/transactions.json      every transaction, cleaned + labeled
        pipeline/data/clean/monthly_summary.json   spending/income by month + category
        pipeline/data/clean/recurring.json         detected paychecks, subscriptions, bills
        calculation_engine/private_data/upcoming.json
                                            future schedule in the engine's FinancialData format

Categories use the frontend's IDs:
    housing, groceries, transport, utilities, fun, subscriptions, other, savings
plus "income" and "transfer" for money that is not spending.

Each transaction also gets a spend_type so prediction code never double-counts:
    income     regular paychecks (already projected in upcoming.json)
    one_time   irregular income such as a bonus (do NOT project forward)
    recurring  bills and detected subscriptions (already projected in upcoming.json)
    everyday   discretionary spending (groceries, gas, fun...) -> what spending prediction models
    transfer   money moved between the customer's own accounts (not spending or income)

Run from the repo root:
    python pipeline/transform.py
    python pipeline/transform.py --as-of 2026-11-07   # testing only; the engine requires today's UTC date
"""
import argparse
import calendar
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

import pandas as pd

RAW = "pipeline/data/raw"
CLEAN = "pipeline/data/clean"
UPCOMING_FILE = "calculation_engine/private_data/upcoming.json"
HORIZON_DAYS = 45
CURRENCY = "USD"

# Raw merchant categories (any casing, string or list) -> frontend category IDs.
CATEGORY_MAP = {
    "groceries": "groceries", "grocery": "groceries", "supermarket": "groceries",
    "food": "fun", "restaurant": "fun", "restaurants": "fun", "dining": "fun",
    "fun": "fun", "entertainment": "fun", "bar": "fun", "nightlife": "fun",
    "transport": "transport", "transportation": "transport", "gas": "transport",
    "fuel": "transport", "transit": "transport",
    "subscriptions": "subscriptions", "subscription": "subscriptions", "streaming": "subscriptions",
    "shopping": "other", "retail": "other", "other": "other", "health": "other",
    "pharmacy": "other", "personal": "other",
    "housing": "housing", "rent": "housing", "utilities": "utilities",
}
# Bills only carry a nickname, so categorize by keyword.
BILL_KEYWORDS = [
    ("rent", "housing"), ("mortgage", "housing"),
    ("utilit", "utilities"), ("electric", "utilities"), ("water", "utilities"),
    ("phone", "utilities"), ("internet", "utilities"), ("energy", "utilities"),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load(name):
    path = os.path.join(RAW, f"{name}.json")
    if not os.path.exists(path):
        print(f"  (missing {path}, treating as empty)")
        return []
    with open(path) as f:
        return json.load(f)


def money(value):
    """Two-decimal string, the format the calculation engine requires."""
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"


def clamp_day(year, month, day):
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def add_months(d, months, day=None):
    """Same day (or a given day) N months later, clamped to month end."""
    index = d.month - 1 + months
    return clamp_day(d.year + index // 12, index % 12 + 1, day or d.day)


def clean_category(raw):
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw:
        return "other"
    return CATEGORY_MAP.get(str(raw).strip().lower(), "other")


def bill_category(nickname):
    name = str(nickname).lower()
    return next((cat for key, cat in BILL_KEYWORDS if key in name), "other")


def base_row(r, *, id_, date_, amount, source, merchant, category):
    return {
        "id": id_,
        "account_id": r.get("_source_account_id"),
        "account_type": r.get("_source_account_type"),
        "date": date_,
        "amount": float(amount),
        "source": source,
        "merchant": merchant,
        "category": category,
        "description": r.get("description") or r.get("nickname") or "",
        "status": r.get("status", "unknown"),
    }


# --------------------------------------------------------------------------- #
# 1. Normalize each source into one shape
# --------------------------------------------------------------------------- #
def norm_deposits(rows):
    return [base_row(r, id_=r["_id"], date_=r["transaction_date"],
                     amount=abs(r["amount"]), source="deposit",
                     merchant=r.get("description") or "Deposit", category="income")
            for r in rows]


def norm_withdrawals(rows):
    return [base_row(r, id_=r["_id"], date_=r["transaction_date"],
                     amount=-abs(r["amount"]), source="withdrawal",
                     merchant=r.get("description") or "Withdrawal", category="other")
            for r in rows]


def norm_purchases(rows, merchants):
    out = []
    for r in rows:
        m = merchants.get(r.get("merchant_id"), {})
        row = base_row(r, id_=r["_id"], date_=r["purchase_date"],      # NOT transaction_date
                       amount=-abs(r["amount"]), source="purchase",
                       merchant=m.get("name", "Unknown merchant"),
                       category=clean_category(m.get("category")))
        row["merchant_id"] = r.get("merchant_id")
        out.append(row)
    return out


def norm_transfers(rows):
    # Nessie quirk: transfers use "id" (not "_id") and carry no direction,
    # so they are treated as leaving the account they were fetched from.
    return [base_row(r, id_=r.get("id") or r.get("_id"), date_=r["transaction_date"],
                     amount=-abs(r["amount"]), source="transfer",
                     merchant=r.get("description") or "Transfer", category="transfer")
            for r in rows]


def norm_bills(rows):
    # Only completed bills are history. "recurring" bills are the future schedule.
    return [base_row(r, id_=r["_id"], date_=r["payment_date"],
                     amount=-abs(r["payment_amount"]), source="bill",
                     merchant=r.get("payee") or r.get("nickname") or "Bill",
                     category=bill_category(r.get("nickname", "")))
            for r in rows if r.get("status") == "completed"]


# --------------------------------------------------------------------------- #
# 2. Transfer matching + flags
# --------------------------------------------------------------------------- #
def match_transfers(df):
    """Pair each outgoing transfer with an incoming 'transfer' deposit (same date + amount)."""
    df["is_transfer"] = df["source"].eq("transfer")
    df["transfer_pair_id"] = None
    incoming = df[(df["source"] == "deposit")
                  & df["description"].str.contains("transfer", case=False, na=False)]
    used, pairs = set(), 0
    for idx, t in df[df["source"] == "transfer"].iterrows():
        match = incoming[(incoming["date"] == t["date"])
                         & (incoming["amount"] == -t["amount"])
                         & (incoming["account_id"] != t["account_id"])
                         & (~incoming.index.isin(used))]
        if not match.empty:
            m_idx = match.index[0]
            used.add(m_idx)
            df.loc[[idx, m_idx], "transfer_pair_id"] = t["id"]
            pairs += 1
    df.loc[incoming.index, "is_transfer"] = True
    # Money moved into savings is the frontend's "savings" category.
    df.loc[df["is_transfer"], "category"] = "transfer"
    into_savings = (df["description"].str.contains("savings", case=False, na=False)
                    | df["account_type"].eq("Savings"))
    df.loc[df["is_transfer"] & into_savings, "category"] = "savings"
    return df, pairs


def add_flags(df):
    counted = df["status"].isin(["completed", "pending", "executed"])
    df["is_spending"] = counted & (df["amount"] < 0) & ~df["is_transfer"]
    df["is_income"] = counted & (df["amount"] > 0) & ~df["is_transfer"]
    df["month"] = df["date"].dt.strftime("%Y-%m")
    return df


# --------------------------------------------------------------------------- #
# 3. Recurring detection
# --------------------------------------------------------------------------- #
def detect_paychecks(df, checking_id):
    """Income that repeats on a steady rhythm.

    Handles both kinds of pay schedule:
      - fixed days of the month (e.g. the 14th and 28th, or the 1st)  -> days_of_month
      - fixed gap (weekly / biweekly)                                 -> every_days
    """
    found = []
    income = df[df["is_income"] & (df["account_id"] == checking_id)]
    for desc, g in income.groupby("description"):
        dates = sorted(g["date"].dt.date)
        if len(dates) < 3:
            continue
        amount = round(float(g.sort_values("date")["amount"].tail(3).median()), 2)
        days = sorted({d.day for d in dates})
        # Days-of-month schedule: every payment lands on one of at most two days
        # (end-of-month clamping, e.g. the 31st -> 30th, counts as the same day).
        is_month_end = all(d.day == calendar.monthrange(d.year, d.month)[1] or d.day >= 28 for d in dates)
        if len(days) <= 2 and len(dates) >= 3:
            found.append({
                "kind": "paycheck", "name": desc, "amount": amount,
                "schedule": "semi-monthly" if len(days) == 2 else "monthly",
                "days_of_month": days, "last_date": dates[-1].isoformat(),
                "occurrences": len(dates), "confidence": "high" if len(dates) >= 6 else "medium",
            })
            continue
        gap = median((b - a).days for a, b in zip(dates, dates[1:]))
        period = next((p for p in (7, 14) if abs(gap - p) <= 2), None)
        if period:
            found.append({
                "kind": "paycheck", "name": desc, "amount": amount,
                "schedule": "weekly" if period == 7 else "biweekly",
                "every_days": period, "last_date": dates[-1].isoformat(),
                "occurrences": len(dates), "confidence": "high" if len(dates) >= 6 else "medium",
            })
        elif is_month_end:
            found.append({
                "kind": "paycheck", "name": desc, "amount": amount, "schedule": "monthly",
                "days_of_month": [31], "last_date": dates[-1].isoformat(),
                "occurrences": len(dates), "confidence": "medium",
            })
    return found


def detect_subscriptions(df, checking_id):
    """Same merchant, about once a month, on about the same day -> subscription.

    Prices may change (e.g. Spotify $12 -> $17); the most recent price is projected.
    """
    found = []
    buys = df[df["is_spending"] & (df["source"] == "purchase") & (df["account_id"] == checking_id)]
    for merchant, g in buys.groupby("merchant"):
        g = g.sort_values("date")
        dates = list(g["date"].dt.date)
        if len(dates) < 2:
            continue
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        days = [d.day for d in dates]
        steady_day = max(days) - min(days) <= 3
        if all(26 <= gap <= 35 for gap in gaps) and steady_day:
            amounts = list(g["amount"])
            found.append({
                "kind": "subscription", "name": merchant, "amount": round(float(amounts[-1]), 2),
                "every_months": 1, "day_of_month": int(round(median(days))),
                "last_date": dates[-1].isoformat(), "occurrences": len(dates),
                "price_changes": [{"from": round(-a, 2), "to": round(-b, 2), "date": d.isoformat()}
                                  for a, b, d in zip(amounts, amounts[1:], dates[1:]) if a != b],
            })
    return found


def scheduled_bills(raw_bills, checking_id):
    """Nessie bills with status 'recurring' are the known future obligations."""
    found = []
    for b in raw_bills:
        if b.get("status") != "recurring" or b.get("_source_account_id") != checking_id:
            continue
        found.append({
            "kind": "bill", "name": b.get("nickname") or b.get("payee"),
            "payee": b.get("payee"), "amount": -abs(b["payment_amount"]),
            "category": bill_category(b.get("nickname", "")),
            "next_date": b.get("payment_date") or b.get("upcoming_payment_date"),
            "day_of_month": b.get("recurring_date"),
        })
    return found


def label_spend_types(df, patterns):
    """Tag every transaction so prediction code knows what is already scheduled."""
    paycheck_names = {p["name"] for p in patterns if p["kind"] == "paycheck"}
    subscription_merchants = {p["name"] for p in patterns if p["kind"] == "subscription"}
    df["spend_type"] = "everyday"
    df.loc[df["is_income"], "spend_type"] = "one_time"
    df.loc[df["is_income"] & df["description"].isin(paycheck_names), "spend_type"] = "income"
    df.loc[df["source"].eq("bill"), "spend_type"] = "recurring"
    df.loc[df["source"].eq("purchase") & df["merchant"].isin(subscription_merchants), "spend_type"] = "recurring"
    df.loc[df["is_transfer"], "spend_type"] = "transfer"
    return df


# --------------------------------------------------------------------------- #
# 4. Monthly summary
# --------------------------------------------------------------------------- #
def monthly_summary(df):
    summary = {}
    for month, g in df.groupby("month"):
        spend = g[g["is_spending"]]
        summary[month] = {
            "spending": round(-spend["amount"].sum(), 2),
            "income": round(g[g["is_income"]]["amount"].sum(), 2),
            "saved": round(g[g["is_transfer"] & g["account_type"].eq("Savings") & (g["amount"] > 0)]["amount"].sum(), 2),
            "by_category": {cat: round(-amt, 2) for cat, amt in
                            spend.groupby("category")["amount"].sum().sort_values().items()},
            "everyday_spending": round(-spend[spend["spend_type"] == "everyday"]["amount"].sum(), 2),
            "transaction_count": int(len(g)),
        }
    return summary


# --------------------------------------------------------------------------- #
# 5. Future schedule in the calculation engine's FinancialData format
# --------------------------------------------------------------------------- #
def project(pattern, as_of, horizon):
    """Yield future dates (strictly after as_of, up to horizon) for one pattern."""
    if pattern["kind"] == "bill":
        d = date.fromisoformat(pattern["next_date"])
        day = pattern.get("day_of_month") or d.day
        while d <= as_of:                       # stale schedule -> roll forward
            d = add_months(d, 1, day)
        while d <= horizon:
            yield d
            d = add_months(d, 1, day)
        return
    last = date.fromisoformat(pattern["last_date"])
    if pattern.get("days_of_month") or pattern.get("day_of_month"):
        days = pattern.get("days_of_month") or [pattern["day_of_month"]]
        month = date(last.year, last.month, 1)
        while month <= horizon:
            for day in days:
                d = clamp_day(month.year, month.month, day)
                if last < d <= horizon and d > as_of:
                    yield d
            month = add_months(month, 1, 1)
        return
    d = last + timedelta(days=pattern["every_days"])
    while d <= horizon:
        if d > as_of:
            yield d
        d += timedelta(days=pattern["every_days"])


def build_upcoming(patterns, customer_id, checking_balance, as_of):
    horizon = as_of + timedelta(days=HORIZON_DAYS)
    events = []
    for p in patterns:
        prefix = {"bill": "bill", "paycheck": "pay", "subscription": "sub"}[p["kind"]]
        for i, d in enumerate(project(p, as_of, horizon)):
            amount = Decimal(str(p["amount"]))
            if amount == 0:
                continue
            confirmed = p["kind"] == "bill" and i == 0   # Nessie-scheduled; the rest is predicted
            events.append({
                "id": f"{prefix}-{slug(p['name'])}-{d.isoformat()}",
                "date": d.isoformat(),
                "description": str(p["name"])[:200],
                "amount": money(amount),
                "type": "income" if amount > 0 else "expense",
                "source_status": "confirmed" if confirmed else "estimated",
            })
    events.sort(key=lambda e: (e["date"], e["id"]))
    return {
        "customer_id": customer_id,
        "currency": CURRENCY,
        "as_of_date": as_of.isoformat(),
        "current_balance": money(checking_balance),
        "upcoming_transactions": events,
        "historical_transactions": [],
        "snapshot_basis": "intraday",
        "source_notes": [
            f"Schedule generated by pipeline/transform.py for {as_of.isoformat()} (UTC).",
            "Bills from Nessie recurring schedule; later months extrapolated.",
            "Paychecks and subscriptions predicted from transaction history.",
            "Everyday spending is not included; it is modeled separately.",
        ],
    }


def validate_with_engine(payload):
    """Check the schedule against the engine's own strict contract, if available."""
    sys.path.insert(0, os.getcwd())
    try:
        from calculation_engine.models import FinancialData
    except ImportError as exc:
        return f"skipped (could not import engine models: {exc})"
    FinancialData.model_validate(payload)
    return "passed FinancialData contract"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str, allow_nan=False)
    print(f"  wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="YYYY-MM-DD (testing only). Default: today in UTC.")
    args = parser.parse_args()
    as_of = (date.fromisoformat(args.as_of) if args.as_of
             else datetime.now(timezone.utc).date())

    customer = load("customer")
    accounts = load("accounts")
    checking = next(a for a in accounts if a["type"] == "Checking")
    merchants = {m["_id"]: m for m in load("merchants")}
    raw_bills = load("bills")

    # 1. normalize + stack
    rows = (norm_deposits(load("deposits")) + norm_withdrawals(load("withdrawals"))
            + norm_purchases(load("purchases"), merchants) + norm_transfers(load("transfers"))
            + norm_bills(raw_bills))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    before = len(df)
    df = df[df["status"] != "cancelled"].drop_duplicates(subset="id")
    df = df[df["date"].dt.date <= as_of]                       # history never includes the future
    df = df.sort_values(["date", "id"]).reset_index(drop=True)

    # 2. transfers + flags
    df, pairs = match_transfers(df)
    df = add_flags(df)

    # 3. recurring patterns + labels
    patterns = (detect_paychecks(df, checking["_id"])
                + detect_subscriptions(df, checking["_id"])
                + scheduled_bills(raw_bills, checking["_id"]))
    df = label_spend_types(df, patterns)

    # 4. summaries + future schedule
    summary = monthly_summary(df)
    upcoming = build_upcoming(patterns, customer["_id"], checking["balance"], as_of)
    validation = validate_with_engine(upcoming)

    # 5. save
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out.astype(object).where(out.notna(), None)            # NaN -> null (valid JSON)
    print("\nWriting outputs...")
    save(f"{CLEAN}/transactions.json", out.to_dict(orient="records"))
    save(f"{CLEAN}/monthly_summary.json", summary)
    save(f"{CLEAN}/recurring.json", patterns)
    save(UPCOMING_FILE, upcoming)

    # 6. report
    print(f"\nCleaning log: {before} raw rows -> {len(df)} clean rows, "
          f"{pairs} transfer pair(s) matched")
    print("\nMonth      Spending    Income   Saved   Everyday")
    for month, s in summary.items():
        print(f"{month}   {s['spending']:>9.2f} {s['income']:>9.2f} {s['saved']:>7.2f} {s['everyday_spending']:>9.2f}")
    print("\nRecurring patterns:")
    for p in patterns:
        when = (p.get("schedule") or (f"day {p.get('day_of_month')}" if p.get("day_of_month") else "")) or ""
        extra = f"  price changes: {len(p['price_changes'])}" if p.get("price_changes") else ""
        print(f"  {p['kind']:<13} {p['name']:<25} {p['amount']:>9.2f}  {when}{extra}")
    print(f"\nUpcoming schedule as of {as_of} (UTC), next {HORIZON_DAYS} days:")
    for e in upcoming["upcoming_transactions"]:
        print(f"  {e['date']}  {e['amount']:>8}  {e['description']:<20} {e['source_status']}")
    print(f"\nEngine contract check: {validation}")


if __name__ == "__main__":
    main()
