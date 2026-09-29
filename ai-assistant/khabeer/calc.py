"""Deterministic financial and engineering calculations.

Pure functions with no API dependency, so the model never does arithmetic in
its head and every number can be unit-tested.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def _r(x: float, places: int = 2) -> float:
    q = Decimal(1).scaleb(-places)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


# --- Tax -------------------------------------------------------------------

def vat(amount: float, rate_percent: float, inclusive: bool = False) -> dict:
    """Split an amount into net, VAT and gross."""
    if rate_percent < 0:
        raise ValueError("rate_percent must be >= 0")
    rate = rate_percent / 100
    if inclusive:
        gross = amount
        net = amount / (1 + rate)
    else:
        net = amount
        gross = amount * (1 + rate)
    return {"net": _r(net), "vat": _r(gross - net), "gross": _r(gross), "rate_percent": rate_percent}


# --- Depreciation ------------------------------------------------------------

def depreciation_schedule(
    cost: float,
    salvage: float,
    life_years: int,
    method: str = "straight_line",
) -> dict:
    """Yearly depreciation schedule.

    method: straight_line | declining_balance (double declining, switching to
    straight line when that is higher) | sum_of_years
    """
    if life_years <= 0:
        raise ValueError("life_years must be > 0")
    if salvage > cost:
        raise ValueError("salvage cannot exceed cost")
    base = cost - salvage
    rows = []
    book = cost
    for year in range(1, life_years + 1):
        remaining = life_years - year + 1
        if method == "straight_line":
            dep = base / life_years
        elif method == "sum_of_years":
            dep = base * remaining / (life_years * (life_years + 1) / 2)
        elif method == "declining_balance":
            ddb = book * 2 / life_years
            sl = (book - salvage) / remaining
            dep = max(ddb, sl)
        else:
            raise ValueError(f"unknown method: {method}")
        dep = min(dep, book - salvage)
        if year == life_years:
            dep = book - salvage  # absorb rounding in the final year
        book -= dep
        rows.append({"year": year, "depreciation": _r(dep), "book_value_end": _r(book)})
    return {"method": method, "depreciable_base": _r(base), "schedule": rows}


# --- Loans -------------------------------------------------------------------

def loan_amortization(principal: float, annual_rate_percent: float, months: int) -> dict:
    """Equal-installment (annuity) loan schedule."""
    if months <= 0:
        raise ValueError("months must be > 0")
    r = annual_rate_percent / 100 / 12
    payment = principal / months if r == 0 else principal * r / (1 - (1 + r) ** -months)
    balance = principal
    rows = []
    total_interest = 0.0
    for m in range(1, months + 1):
        interest = balance * r
        princ = payment - interest
        if m == months:
            princ = balance
        balance -= princ
        total_interest += interest
        rows.append({
            "month": m,
            "payment": _r(princ + interest),
            "interest": _r(interest),
            "principal": _r(princ),
            "balance": _r(max(balance, 0.0)),
        })
    return {
        "monthly_payment": _r(payment),
        "total_interest": _r(total_interest),
        "total_paid": _r(principal + total_interest),
        "schedule": rows,
    }


# --- Investment appraisal ----------------------------------------------------

def npv(rate_percent: float, cash_flows: list[float]) -> float:
    """cash_flows[0] is at time 0 (usually the negative investment)."""
    r = rate_percent / 100
    return sum(cf / (1 + r) ** t for t, cf in enumerate(cash_flows))


def irr(cash_flows: list[float]) -> float | None:
    """IRR in percent by bisection; None if the flows never change sign."""
    if not (any(c < 0 for c in cash_flows) and any(c > 0 for c in cash_flows)):
        return None
    lo, hi = -99.0, 1000.0
    f_lo = npv(lo, cash_flows)
    if f_lo * npv(hi, cash_flows) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid, cash_flows)
        if abs(f_mid) < 1e-9:
            break
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def payback_period(cash_flows: list[float]) -> float | None:
    """Years until cumulative cash flow turns non-negative (interpolated)."""
    cum = 0.0
    for t, cf in enumerate(cash_flows):
        prev = cum
        cum += cf
        if cum >= 0 and t > 0:
            return (t - 1) + (-prev / cf if cf else 0)
    return None


def investment_appraisal(rate_percent: float, cash_flows: list[float]) -> dict:
    i = irr(cash_flows)
    p = payback_period(cash_flows)
    return {
        "npv": _r(npv(rate_percent, cash_flows)),
        "irr_percent": None if i is None else _r(i),
        "payback_years": None if p is None else _r(p),
    }


# --- Pricing -----------------------------------------------------------------

def break_even(fixed_costs: float, price_per_unit: float, variable_cost_per_unit: float,
               target_profit: float = 0.0) -> dict:
    margin = price_per_unit - variable_cost_per_unit
    if margin <= 0:
        raise ValueError("price must exceed variable cost per unit")
    units = (fixed_costs + target_profit) / margin
    return {
        "contribution_margin_per_unit": _r(margin),
        "contribution_margin_ratio_percent": _r(margin / price_per_unit * 100),
        "units": _r(units),
        "revenue": _r(units * price_per_unit),
    }


# --- Ratios ------------------------------------------------------------------

def financial_ratios(
    current_assets: float = 0.0,
    current_liabilities: float = 0.0,
    inventory: float = 0.0,
    cash: float = 0.0,
    total_assets: float = 0.0,
    total_liabilities: float = 0.0,
    equity: float = 0.0,
    revenue: float = 0.0,
    cost_of_sales: float = 0.0,
    net_income: float = 0.0,
    receivables: float = 0.0,
    payables: float = 0.0,
) -> dict:
    """Compute every ratio whose inputs were given (non-zero denominators)."""
    def div(a: float, b: float, pct: bool = False) -> float | None:
        if not b:
            return None
        return _r(a / b * (100 if pct else 1))

    out = {
        "current_ratio": div(current_assets, current_liabilities),
        "quick_ratio": div(current_assets - inventory, current_liabilities),
        "cash_ratio": div(cash, current_liabilities),
        "debt_to_equity": div(total_liabilities, equity),
        "debt_ratio_percent": div(total_liabilities, total_assets, pct=True),
        "gross_margin_percent": div(revenue - cost_of_sales, revenue, pct=True),
        "net_margin_percent": div(net_income, revenue, pct=True),
        "roa_percent": div(net_income, total_assets, pct=True),
        "roe_percent": div(net_income, equity, pct=True),
        "asset_turnover": div(revenue, total_assets),
        "dso_days": div(receivables * 365, revenue),
        "dio_days": div(inventory * 365, cost_of_sales),
        "dpo_days": div(payables * 365, cost_of_sales),
    }
    if None not in (out["dso_days"], out["dio_days"], out["dpo_days"]):
        out["cash_conversion_cycle_days"] = _r(out["dso_days"] + out["dio_days"] - out["dpo_days"])
    return {k: v for k, v in out.items() if v is not None}


# --- Journal entries ---------------------------------------------------------

def check_journal_entry(lines: list[dict]) -> dict:
    """Validate a double-entry journal: each line has account, debit, credit."""
    problems = []
    total_dr = Decimal(0)
    total_cr = Decimal(0)
    for i, line in enumerate(lines, 1):
        dr = Decimal(str(line.get("debit") or 0))
        cr = Decimal(str(line.get("credit") or 0))
        if not str(line.get("account", "")).strip():
            problems.append(f"line {i}: missing account")
        if dr < 0 or cr < 0:
            problems.append(f"line {i}: negative amount")
        if dr and cr:
            problems.append(f"line {i}: both debit and credit set")
        if not dr and not cr:
            problems.append(f"line {i}: zero line")
        total_dr += dr
        total_cr += cr
    if len(lines) < 2:
        problems.append("an entry needs at least two lines")
    diff = total_dr - total_cr
    if diff:
        problems.append(f"unbalanced by {diff}")
    return {
        "balanced": not problems,
        "total_debit": float(total_dr),
        "total_credit": float(total_cr),
        "problems": problems,
    }


# --- Construction quantities -------------------------------------------------

def concrete_quantity(length_m: float, width_m: float, depth_m: float, count: int = 1,
                      waste_percent: float = 5.0, unit_price: float = 0.0) -> dict:
    """Volume of rectangular elements (footings, slabs, beams, columns)."""
    for v in (length_m, width_m, depth_m):
        if v <= 0:
            raise ValueError("dimensions must be > 0")
    net = length_m * width_m * depth_m * count
    gross = net * (1 + waste_percent / 100)
    out = {"net_m3": _r(net, 3), "with_waste_m3": _r(gross, 3), "waste_percent": waste_percent}
    if unit_price:
        out["estimated_cost"] = _r(gross * unit_price)
    return out
