"""
Seed "Alex v2" in Nessie so live data matches the frontend's demo Alex exactly.

Source of truth (frontend/src/mocks/):
  demoFinancialSnapshot.ts  checking $1,800 on 2026-11-07, rent $1,150 on the 11th,
                            utilities $180 on the 17th, $1,600 paychecks on the 14th + 28th
  demoYearHistory.ts        Jan-Oct income / spending / savings by category
  demoBudgetPlan.ts         November spending so far by category

Creates a NEW customer (Alex Morgan); the old Alex Rivera is left untouched.
Safe to re-run: anything already in Nessie is skipped, so a failed run can be resumed.

    python pipeline/seed_alex_v2.py --dry-run   # build + verify the plan, no API calls
    python pipeline/seed_alex_v2.py             # seed Nessie, write pipeline/data/seed_ids.json
"""
import argparse
import calendar
import json
import os
import shutil
import sys
from collections import defaultdict

YEAR = 2026
IDS_FILE = "pipeline/data/seed_ids.json"
CUSTOMER = {"first_name": "Alex", "last_name": "Morgan",
            "address": {"street_number": "800", "street_name": "W Campbell Rd",
                        "city": "Richardson", "state": "TX", "zip": "75080"}}
CHECKING = ("Checking", "Alex Checking", 1800)
SAVINGS = ("Savings", "Alex Savings", 800)

# Monthly targets in whole dollars, copied from frontend/src/mocks/demoYearHistory.ts
HISTORY = {
    #  month: (income, savings, housing, groceries, transport, utilities, fun, subscriptions, other)
    1: (3200, 50, 1150, 410, 230, 190, 260, 70, 470),
    2: (3200, 75, 1150, 390, 220, 180, 210, 70, 420),
    3: (3200, 75, 1150, 400, 240, 180, 240, 70, 430),
    4: (3200, 100, 1150, 380, 220, 170, 190, 70, 410),
    5: (3200, 75, 1150, 430, 250, 180, 280, 70, 470),
    6: (3350, 100, 1150, 410, 230, 190, 220, 70, 450),
    7: (3200, 75, 1150, 400, 240, 200, 200, 70, 420),
    8: (3200, 100, 1150, 440, 260, 210, 300, 70, 480),
    9: (3200, 75, 1150, 390, 220, 180, 210, 70, 400),
    10: (3200, 75, 1150, 380, 210, 170, 180, 70, 390),
}
SPENDING_TOTALS = {1: 2780, 2: 2640, 3: 2710, 4: 2590, 5: 2830, 6: 2720,
                   7: 2680, 8: 2910, 9: 2620, 10: 2550}

# Merchants -> frontend category IDs (housing/utilities come from bills, not merchants)
MERCHANTS = {
    "H-E-B": "groceries", "Trader Joe's": "groceries", "Walmart": "groceries",
    "Shell": "transport", "DART": "transport",
    "Chipotle": "fun", "Torchy's Tacos": "fun", "AMC Theatres": "fun", "Deep Ellum Bar": "fun",
    "Netflix": "subscriptions", "Spotify": "subscriptions", "iCloud": "subscriptions",
    "Planet Fitness": "subscriptions",
    "Amazon": "other", "Target": "other", "CVS Pharmacy": "other", "Great Clips": "other",
}

# How each monthly category total is split into purchases: (day, merchant, share, description)
SPLITS = {
    "groceries": [(3, "H-E-B", .30, "Groceries"), (10, "Trader Joe's", .20, "Groceries"),
                  (18, "Walmart", .25, "Groceries"), (25, "H-E-B", .25, "Groceries")],
    "transport": [(6, "Shell", .35, "Gas"), (16, "Shell", .35, "Gas"), (1, "DART", .30, "Transit pass")],
    "fun": [(7, "Chipotle", .20, "Dinner"), (13, "AMC Theatres", .20, "Movies"),
            (20, "Torchy's Tacos", .25, "Dinner with friends"), (27, "Deep Ellum Bar", .35, "Night out")],
    "other": [(4, "Amazon", .35, "Household items"), (12, "Target", .30, "Household items"),
              (21, "CVS Pharmacy", .15, "Pharmacy"), (24, "Great Clips", .20, "Haircut")],
}
# Fixed subscriptions: $70/month total, matching the frontend
SUBSCRIPTIONS = [(2, "iCloud", 3, "iCloud storage"), (5, "Spotify", 17, "Spotify Premium"),
                 (9, "Netflix", 15, "Netflix"), (15, "Planet Fitness", 35, "Gym membership")]

# November 1-7 so far, matching demoBudgetPlan.ts spentCents
NOVEMBER = [
    ("2026-11-01", "DART", 25, "Transit pass"), ("2026-11-01", "Deep Ellum Bar", 60, "Night out"),
    ("2026-11-02", "iCloud", 3, "iCloud storage"), ("2026-11-03", "H-E-B", 110, "Groceries"),
    ("2026-11-04", "CVS Pharmacy", 40, "Pharmacy"), ("2026-11-05", "Spotify", 17, "Spotify Premium"),
    ("2026-11-05", "Torchy's Tacos", 45, "Dinner with friends"), ("2026-11-06", "Shell", 45, "Gas"),
    ("2026-11-06", "Trader Joe's", 70, "Groceries"), ("2026-11-06", "AMC Theatres", 35, "Movies"),
    ("2026-11-07", "Chipotle", 40, "Dinner"),
]


def d(month, day):
    return f"{YEAR}-{month:02d}-{min(day, calendar.monthrange(YEAR, month)[1]):02d}"


def split(total, parts):
    """Split whole dollars by shares; the last part absorbs rounding so the sum is exact."""
    amounts = [round(total * share) for _, _, share, _ in parts[:-1]]
    return amounts + [total - sum(amounts)]


def build_plan():
    plan = {"checking_deposits": [], "savings_deposits": [], "purchases": [],
            "bills": [], "transfers": []}
    for m, (income, saved, housing, groceries, transport, utilities, fun, subs, other) in HISTORY.items():
        for day in (14, 28):
            plan["checking_deposits"].append({"date": d(m, day), "amount": 1600, "description": "Payroll deposit"})
        if income > 3200:  # June bonus: irregular income the forecast must NOT repeat
            plan["checking_deposits"].append({"date": d(m, 28), "amount": income - 3200,
                                              "description": "Performance bonus"})
        plan["bills"].append({"date": d(m, 11), "payee": "Campus View Apartments", "nickname": "Rent",
                              "amount": housing, "day": 11, "status": "completed"})
        plan["bills"].append({"date": d(m, 17), "payee": "TXU Energy", "nickname": "Utilities",
                              "amount": utilities, "day": 17, "status": "completed"})
        for category, total in (("groceries", groceries), ("transport", transport),
                                ("fun", fun), ("other", other)):
            parts = SPLITS[category]
            for (day, merchant, _, desc), amount in zip(parts, split(total, parts)):
                plan["purchases"].append({"date": d(m, day), "merchant": merchant,
                                          "amount": amount, "description": desc})
        assert sum(a for _, _, a, _ in SUBSCRIPTIONS) == subs
        for day, merchant, amount, desc in SUBSCRIPTIONS:
            plan["purchases"].append({"date": d(m, day), "merchant": merchant,
                                      "amount": amount, "description": desc})
        plan["transfers"].append({"date": d(m, 15), "amount": saved, "description": "Transfer to savings"})
        plan["savings_deposits"].append({"date": d(m, 15), "amount": saved,
                                         "description": "Transfer from checking"})
    for date, merchant, amount, desc in NOVEMBER:
        plan["purchases"].append({"date": date, "merchant": merchant, "amount": amount, "description": desc})
    # Future schedule: Nessie "recurring" bills (the pipeline turns these into upcoming events)
    plan["bills"].append({"date": "2026-11-11", "payee": "Campus View Apartments", "nickname": "Rent",
                          "amount": 1150, "day": 11, "status": "recurring"})
    plan["bills"].append({"date": "2026-11-17", "payee": "TXU Energy", "nickname": "Utilities",
                          "amount": 180, "day": 17, "status": "recurring"})
    return plan


def verify(plan):
    """Recompute monthly totals from the plan and compare with the frontend's numbers."""
    spend = defaultdict(lambda: defaultdict(int))
    income = defaultdict(int)
    for p in plan["purchases"]:
        spend[p["date"][:7]][MERCHANTS[p["merchant"]]] += p["amount"]
    for b in plan["bills"]:
        if b["status"] == "completed":
            spend[b["date"][:7]]["housing" if b["nickname"] == "Rent" else "utilities"] += b["amount"]
    for dep in plan["checking_deposits"]:
        income[dep["date"][:7]] += dep["amount"]
    names = ("housing", "groceries", "transport", "utilities", "fun", "subscriptions", "other")
    errors = []
    for m, row in HISTORY.items():
        key = f"{YEAR}-{m:02d}"
        expected = dict(zip(names, (row[2], row[3], row[4], row[5], row[6], row[7], row[8])))
        if dict(spend[key]) != expected:
            errors.append(f"{key} categories {dict(spend[key])} != {expected}")
        if sum(spend[key].values()) != SPENDING_TOTALS[m]:
            errors.append(f"{key} total {sum(spend[key].values())} != {SPENDING_TOTALS[m]}")
        if income[key] != row[0]:
            errors.append(f"{key} income {income[key]} != {row[0]}")
    nov = dict(spend["2026-11"])
    if nov != {"groceries": 180, "transport": 70, "fun": 180, "subscriptions": 20, "other": 40}:
        errors.append(f"2026-11 so far {nov}")
    if sum(t["amount"] for t in plan["transfers"]) != 800:
        errors.append("savings transfers do not sum to $800")
    return errors


# --------------------------------------------------------------------------- #
# Nessie
# --------------------------------------------------------------------------- #
class Nessie:
    def __init__(self):
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        self.requests = requests
        self.key, self.base = os.getenv("NESSIE_API_KEY"), os.getenv("NESSIE_BASE_URL")
        if not self.key or not self.base:
            raise SystemExit("Missing NESSIE_API_KEY or NESSIE_BASE_URL in .env")
        self.created = defaultdict(int)
        self.skipped = defaultdict(int)

    def get_list(self, path):
        r = self.requests.get(f"{self.base}{path}", params={"key": self.key}, timeout=20)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()

    def post(self, path, body, kind):
        for attempt in range(3):
            r = self.requests.post(f"{self.base}{path}", params={"key": self.key}, json=body, timeout=20)
            if r.status_code == 201:
                self.created[kind] += 1
                return r.json()["objectCreated"]
            if r.status_code < 500:
                break
        raise SystemExit(f"FAILED POST {path} -> {r.status_code}: {r.text}\nBody: {body}")


def seed(plan):
    api = Nessie()

    # Customer + accounts (reuse if they already exist)
    customer = next((c for c in api.get_list("/customers")
                     if c.get("first_name") == CUSTOMER["first_name"]
                     and c.get("last_name") == CUSTOMER["last_name"]), None)
    customer_id = customer["_id"] if customer else api.post("/customers", CUSTOMER, "customers")["_id"]
    accounts = {a["nickname"]: a["_id"] for a in api.get_list(f"/customers/{customer_id}/accounts")}
    for acct_type, nickname, balance in (CHECKING, SAVINGS):
        if nickname not in accounts:
            accounts[nickname] = api.post(f"/customers/{customer_id}/accounts", {
                "type": acct_type, "nickname": nickname, "rewards": 0, "balance": balance}, "accounts")["_id"]
    checking, savings = accounts[CHECKING[1]], accounts[SAVINGS[1]]

    # Merchants (reuse by name)
    merchant_ids = {m.get("name"): m["_id"] for m in api.get_list("/merchants")}
    for name, category in MERCHANTS.items():
        if name not in merchant_ids:
            merchant_ids[name] = api.post("/merchants", {
                "name": name, "category": category,
                "address": {"street_number": "100", "street_name": "Main St", "city": "Richardson",
                            "state": "TX", "zip": "75080"},
                "geocode": {"lat": 32.95, "lng": -96.73}}, "merchants")["_id"]

    # What already exists (so a re-run or a resumed run never duplicates)
    def keys(path, date_field, amount_field="amount", text_field="description"):
        return {(r.get(date_field), float(r.get(amount_field, 0)), r.get(text_field))
                for r in api.get_list(path)}

    have = {
        "checking_deposits": keys(f"/accounts/{checking}/deposits", "transaction_date"),
        "savings_deposits": keys(f"/accounts/{savings}/deposits", "transaction_date"),
        "purchases": keys(f"/accounts/{checking}/purchases", "purchase_date"),
        "transfers": keys(f"/accounts/{checking}/transfers", "transaction_date"),
        "bills": {(b.get("payment_date"), float(b.get("payment_amount", 0)), b.get("nickname"), b.get("status"))
                  for b in api.get_list(f"/accounts/{checking}/bills")},
    }

    def todo(kind, key):
        if key in have[kind]:
            api.skipped[kind] += 1
            return False
        return True

    print("Seeding (this takes a few minutes)...")
    for dep in plan["checking_deposits"]:
        if todo("checking_deposits", (dep["date"], float(dep["amount"]), dep["description"])):
            api.post(f"/accounts/{checking}/deposits", {
                "medium": "balance", "transaction_date": dep["date"], "status": "completed",
                "amount": dep["amount"], "description": dep["description"]}, "deposits")
    for dep in plan["savings_deposits"]:
        if todo("savings_deposits", (dep["date"], float(dep["amount"]), dep["description"])):
            api.post(f"/accounts/{savings}/deposits", {
                "medium": "balance", "transaction_date": dep["date"], "status": "completed",
                "amount": dep["amount"], "description": dep["description"]}, "deposits")
    for t in plan["transfers"]:
        if todo("transfers", (t["date"], float(t["amount"]), t["description"])):
            api.post(f"/accounts/{checking}/transfers", {
                "transaction_date": t["date"], "status": "completed",
                "amount": t["amount"], "description": t["description"]}, "transfers")
    for b in plan["bills"]:
        if todo("bills", (b["date"], float(b["amount"]), b["nickname"], b["status"])):
            api.post(f"/accounts/{checking}/bills", {
                "status": b["status"], "payee": b["payee"], "nickname": b["nickname"],
                "payment_date": b["date"], "recurring_date": b["day"],
                "payment_amount": b["amount"]}, "bills")
    for i, p in enumerate(plan["purchases"], 1):
        if todo("purchases", (p["date"], float(p["amount"]), p["description"])):
            api.post(f"/accounts/{checking}/purchases", {
                "merchant_id": merchant_ids[p["merchant"]], "medium": "balance",
                "purchase_date": p["date"], "amount": p["amount"], "status": "completed",
                "description": p["description"]}, "purchases")
        if i % 25 == 0:
            print(f"  purchases {i}/{len(plan['purchases'])}")

    # Keep the old Alex's IDs as a backup, then point the pipeline at Alex v2
    if os.path.exists(IDS_FILE):
        old = json.load(open(IDS_FILE))
        if old.get("customer_id") != customer_id:
            shutil.copy(IDS_FILE, "pipeline/data/seed_ids_alex_v1.json")
    ids = {"customer_id": customer_id, "checking_id": checking, "savings_id": savings,
           "merchants": {name: merchant_ids[name] for name in MERCHANTS}}
    with open(IDS_FILE, "w") as f:
        json.dump(ids, f, indent=2)

    print("\nCreated:", dict(api.created))
    print("Skipped (already existed):", dict(api.skipped))
    print(f"\nAlex v2 customer ID: {customer_id}")
    print(f"Checking account ID: {checking}")
    print(f"Savings account ID:  {savings}")
    print(f"Saved to {IDS_FILE} (old Alex backed up to pipeline/data/seed_ids_alex_v1.json)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build and verify the plan only")
    args = parser.parse_args()

    plan = build_plan()
    errors = verify(plan)
    counts = {k: len(v) for k, v in plan.items()}
    print("Plan:", counts, "| total records:", sum(counts.values()))
    if errors:
        print("Plan does NOT match the frontend:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("Plan matches the frontend's demo Alex (Jan-Oct by category, November so far, $800 saved).")
    if not args.dry_run:
        seed(plan)


if __name__ == "__main__":
    main()