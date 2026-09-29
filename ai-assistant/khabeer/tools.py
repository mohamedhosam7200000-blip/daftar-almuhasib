"""Tools exposed to the model. Each wraps a function from calc.py."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing_extensions import TypedDict

from anthropic import beta_tool

from . import calc

OUTPUT_DIR = Path(os.environ.get("KHABEER_OUTPUT_DIR", "output")).resolve()


def _run(fn, *args, **kwargs) -> str:
    try:
        return json.dumps(fn(*args, **kwargs), ensure_ascii=False)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@beta_tool
def calculate_vat(amount: float, rate_percent: float, inclusive: bool = False) -> str:
    """Split an amount into net, VAT and gross.

    Args:
        amount: The amount.
        rate_percent: VAT rate in percent, e.g. 15 or 14.
        inclusive: True if the amount already includes VAT.
    """
    return _run(calc.vat, amount, rate_percent, inclusive)


@beta_tool
def depreciation_schedule(cost: float, salvage: float, life_years: int,
                          method: str = "straight_line") -> str:
    """Yearly depreciation schedule for a fixed asset.

    Args:
        cost: Acquisition cost.
        salvage: Residual (scrap) value at end of life.
        life_years: Useful life in years.
        method: straight_line, declining_balance (double declining) or sum_of_years.
    """
    return _run(calc.depreciation_schedule, cost, salvage, life_years, method)


@beta_tool
def loan_amortization(principal: float, annual_rate_percent: float, months: int) -> str:
    """Equal monthly installment loan schedule with interest/principal split.

    Args:
        principal: Loan amount.
        annual_rate_percent: Annual interest rate in percent.
        months: Number of monthly installments.
    """
    return _run(calc.loan_amortization, principal, annual_rate_percent, months)


@beta_tool
def investment_appraisal(rate_percent: float, cash_flows: list[float]) -> str:
    """NPV, IRR and payback period for a project (feasibility study).

    Args:
        rate_percent: Discount rate (cost of capital) in percent.
        cash_flows: Yearly cash flows; the first is at time 0, usually the negative investment.
    """
    return _run(calc.investment_appraisal, rate_percent, cash_flows)


@beta_tool
def break_even(fixed_costs: float, price_per_unit: float, variable_cost_per_unit: float,
               target_profit: float = 0.0) -> str:
    """Break-even units and revenue, optionally for a target profit.

    Args:
        fixed_costs: Total fixed costs for the period.
        price_per_unit: Selling price per unit.
        variable_cost_per_unit: Variable cost per unit.
        target_profit: Desired profit; 0 for plain break-even.
    """
    return _run(calc.break_even, fixed_costs, price_per_unit, variable_cost_per_unit, target_profit)


@beta_tool
def financial_ratios(current_assets: float = 0.0, current_liabilities: float = 0.0,
                     inventory: float = 0.0, cash: float = 0.0, total_assets: float = 0.0,
                     total_liabilities: float = 0.0, equity: float = 0.0, revenue: float = 0.0,
                     cost_of_sales: float = 0.0, net_income: float = 0.0,
                     receivables: float = 0.0, payables: float = 0.0) -> str:
    """Liquidity, leverage, profitability and efficiency ratios.

    Only ratios whose inputs are provided are returned.

    Args:
        current_assets: Total current assets.
        current_liabilities: Total current liabilities.
        inventory: Inventory balance.
        cash: Cash and equivalents.
        total_assets: Total assets.
        total_liabilities: Total liabilities.
        equity: Total equity.
        revenue: Revenue for the period (annual for day-based ratios).
        cost_of_sales: Cost of goods sold for the period.
        net_income: Net profit for the period.
        receivables: Trade receivables balance.
        payables: Trade payables balance.
    """
    return _run(calc.financial_ratios, current_assets, current_liabilities, inventory, cash,
                total_assets, total_liabilities, equity, revenue, cost_of_sales, net_income,
                receivables, payables)


class JournalLine(TypedDict):
    account: str
    debit: float
    credit: float


@beta_tool
def check_journal_entry(lines: list[JournalLine]) -> str:
    """Verify a double-entry journal entry balances and each line is valid.

    Args:
        lines: Entry lines; each has account, debit and credit (one of them 0).
    """
    return _run(calc.check_journal_entry, [dict(line) for line in lines])


@beta_tool
def concrete_quantity(length_m: float, width_m: float, depth_m: float, count: int = 1,
                      waste_percent: float = 5.0, unit_price: float = 0.0) -> str:
    """Concrete volume (and optional cost) for rectangular elements.

    Args:
        length_m: Length in meters.
        width_m: Width in meters.
        depth_m: Depth/thickness in meters.
        count: Number of identical elements.
        waste_percent: Waste allowance in percent.
        unit_price: Price per cubic meter; 0 to skip the cost estimate.
    """
    return _run(calc.concrete_quantity, length_m, width_m, depth_m, count, waste_percent, unit_price)


def safe_output_path(filename: str) -> Path:
    """Resolve filename inside OUTPUT_DIR, rejecting anything that escapes it."""
    path = (OUTPUT_DIR / filename).resolve()
    if not path.is_relative_to(OUTPUT_DIR) or path == OUTPUT_DIR:
        raise ValueError("filename must stay inside the output directory")
    return path


@beta_tool
def save_file(filename: str, content: str) -> str:
    """Save a deliverable (HTML page, CSS, code, CSV, Markdown report) to the output folder.

    Args:
        filename: Relative file name, e.g. "landing.html" or "reports/budget.md".
        content: Full file content.
    """
    try:
        path = safe_output_path(filename)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return json.dumps({"saved": str(path), "bytes": len(content.encode("utf-8"))}, ensure_ascii=False)


ALL_TOOLS = [
    calculate_vat,
    depreciation_schedule,
    loan_amortization,
    investment_appraisal,
    break_even,
    financial_ratios,
    check_journal_entry,
    concrete_quantity,
    save_file,
]
