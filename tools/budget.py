"""
Budget & Expense Tracker — Track income, expenses, and monthly summaries.
All data stored locally in memory/budget/transactions.json
"""
import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "budget"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "transactions.json"

_EXPENSE_CATEGORIES = [
    "food", "transport", "utilities", "rent", "healthcare",
    "entertainment", "shopping", "education", "travel", "general",
]


def _load() -> list:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            pass
    return []


def _save(data: list):
    _FILE.write_text(json.dumps(data, indent=2))


# ── Add Expense ────────────────────────────────────────────────────────────────
@register(
    name="add_expense",
    description="Record an expense. Category examples: food, transport, utilities, rent, entertainment, shopping.",
    parameters={"type": "object", "properties": {
        "amount":      {"type": "number",  "description": "Amount spent (positive number)"},
        "category":    {"type": "string",  "description": "Expense category (default 'general')"},
        "description": {"type": "string",  "description": "What was it for"},
        "date":        {"type": "string",  "description": "Date like '2025-06-01' or 'today' (default today)"},
    }, "required": ["amount"]},
)
def add_expense(amount: float, category: str = "general",
                description: str = "", date: str = "") -> str:
    if amount <= 0:
        return "Amount must be positive, sir."
    day = datetime.today().date().isoformat() if date in ("", "today") else date
    tx  = {"type": "expense", "amount": round(float(amount), 2),
           "category": category.lower().strip(),
           "description": description,
           "date": day, "ts": datetime.now().isoformat()}
    data = _load()
    data.append(tx)
    _save(data)
    return (f"Expense recorded: -{amount:.2f} [{category}]"
            f"{' — '+description if description else ''}, sir.")


# ── Add Income ─────────────────────────────────────────────────────────────────
@register(
    name="add_income",
    description="Record income or a deposit.",
    parameters={"type": "object", "properties": {
        "amount":      {"type": "number", "description": "Amount received"},
        "source":      {"type": "string", "description": "Income source (salary, freelance, gift, etc.)"},
        "description": {"type": "string", "description": "Optional note"},
        "date":        {"type": "string", "description": "Date or 'today'"},
    }, "required": ["amount"]},
)
def add_income(amount: float, source: str = "salary",
               description: str = "", date: str = "") -> str:
    if amount <= 0:
        return "Amount must be positive, sir."
    day = datetime.today().date().isoformat() if date in ("", "today") else date
    tx  = {"type": "income", "amount": round(float(amount), 2),
           "source": source.lower().strip(),
           "description": description,
           "date": day, "ts": datetime.now().isoformat()}
    data = _load()
    data.append(tx)
    _save(data)
    return (f"Income recorded: +{amount:.2f} [{source}]"
            f"{' — '+description if description else ''}, sir.")


# ── Monthly Summary ────────────────────────────────────────────────────────────
@register(
    name="monthly_summary",
    description="Show income vs expenses for a given month (default: current month).",
    parameters={"type": "object", "properties": {
        "month": {"type": "string", "description": "Month as 'YYYY-MM' e.g. '2025-06' (default current month)"},
    }},
)
def monthly_summary(month: str = "") -> str:
    if not month:
        month = datetime.today().strftime("%Y-%m")
    data   = _load()
    period = [t for t in data if t.get("date", "").startswith(month)]
    if not period:
        return f"No transactions for {month}, sir."

    total_income  = sum(t["amount"] for t in period if t["type"] == "income")
    total_expense = sum(t["amount"] for t in period if t["type"] == "expense")
    net           = total_income - total_expense

    # Expenses by category
    by_cat: dict = {}
    for t in period:
        if t["type"] == "expense":
            cat = t.get("category", "general")
            by_cat[cat] = by_cat.get(cat, 0) + t["amount"]

    lines = [
        f"--- Budget Summary: {month} ---",
        f"Income:   +{total_income:>10.2f}",
        f"Expenses: -{total_expense:>10.2f}",
        f"{'Net (surplus)' if net >= 0 else 'Net (deficit)'}: {'+'if net>=0 else ''}{net:.2f}",
    ]
    if by_cat:
        lines.append("\nExpenses by category:")
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            bar = "#" * min(20, int(amt / max(total_expense, 1) * 20))
            lines.append(f"  {cat:15} {bar:20} {amt:.2f}")
    return "\n".join(lines)


# ── Recent Transactions ────────────────────────────────────────────────────────
@register(
    name="list_transactions",
    description="Show recent transactions.",
    parameters={"type": "object", "properties": {
        "n":        {"type": "integer", "description": "Number to show (default 15)"},
        "type":     {"type": "string",  "description": "Filter: 'income', 'expense', or 'all' (default all)"},
        "category": {"type": "string",  "description": "Filter by category (optional)"},
    }},
)
def list_transactions(n: int = 15, type: str = "all", category: str = "") -> str:
    data = _load()
    if type in ("income", "expense"):
        data = [t for t in data if t["type"] == type]
    if category:
        data = [t for t in data if category.lower() in t.get("category", t.get("source", ""))]
    recent = sorted(data, key=lambda t: t.get("ts", ""), reverse=True)[:n]
    if not recent:
        return "No transactions found, sir."
    lines = []
    for t in recent:
        sign  = "+" if t["type"] == "income" else "-"
        tag   = t.get("category") or t.get("source", "")
        desc  = t.get("description", "")
        lines.append(f"{t['date']}  {sign}{t['amount']:>8.2f}  [{tag}]  {desc}")
    return "\n".join(lines)


# ── Delete / Clear ─────────────────────────────────────────────────────────────
@register(
    name="delete_transaction",
    description="Delete recent transactions by keyword in description or category.",
    parameters={"type": "object", "properties": {
        "keyword": {"type": "string", "description": "Keyword to match in description or category"},
    }, "required": ["keyword"]},
)
def delete_transaction(keyword: str) -> str:
    data   = _load()
    q      = keyword.lower()
    before = len(data)
    data   = [t for t in data
              if q not in t.get("description", "").lower()
              and q not in t.get("category", "").lower()
              and q not in t.get("source", "").lower()]
    _save(data)
    removed = before - len(data)
    return f"Removed {removed} transaction(s) matching '{keyword}', sir."


# ── Budget Report (all time) ───────────────────────────────────────────────────
@register(
    name="budget_report",
    description="Full budget report: all-time income, expenses, and top categories.",
    parameters={"type": "object", "properties": {}},
)
def budget_report() -> str:
    data = _load()
    if not data:
        return "No transactions recorded yet, sir."

    total_income  = sum(t["amount"] for t in data if t["type"] == "income")
    total_expense = sum(t["amount"] for t in data if t["type"] == "expense")
    net           = total_income - total_expense
    n_in  = sum(1 for t in data if t["type"] == "income")
    n_exp = sum(1 for t in data if t["type"] == "expense")

    by_cat: dict = {}
    for t in data:
        if t["type"] == "expense":
            cat = t.get("category", "general")
            by_cat[cat] = by_cat.get(cat, 0) + t["amount"]

    # Monthly breakdown (last 6 months)
    months: dict = {}
    for t in data:
        m = t.get("date", "")[:7]
        if m:
            months.setdefault(m, {"income": 0.0, "expense": 0.0})
            months[m][t["type"]] += t["amount"]

    lines = [
        "=== JARVIS Budget Report (All Time) ===",
        f"Total income:   +{total_income:,.2f}  ({n_in} transactions)",
        f"Total expenses: -{total_expense:,.2f}  ({n_exp} transactions)",
        f"Net balance:    {'+'if net>=0 else ''}{net:,.2f}",
        f"\nTop expense categories:",
    ]
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])[:5]:
        pct = amt / total_expense * 100 if total_expense else 0
        lines.append(f"  {cat:15} {amt:>10.2f}  ({pct:.1f}%)")

    if months:
        lines.append(f"\nMonthly breakdown (last {min(6,len(months))} months):")
        for m in sorted(months)[-6:]:
            v   = months[m]
            net_m = v["income"] - v["expense"]
            lines.append(f"  {m}  in:+{v['income']:>8.2f}  out:-{v['expense']:>8.2f}"
                         f"  net:{'+'if net_m>=0 else ''}{net_m:.2f}")

    return "\n".join(lines)
