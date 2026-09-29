// Deterministic calculations — JavaScript port of khabeer/calc.py.
// Keep results identical to the Python version (see test/calc.test.js).

export function round(x, places = 2) {
  const f = 10 ** places;
  // Nudge by EPSILON so values like 1.005 round half-up like Python's Decimal.
  return Math.round((x + Math.sign(x) * Number.EPSILON * Math.abs(x)) * f) / f + 0;
}

export function vat(amount, rate_percent, inclusive = false) {
  if (rate_percent < 0) throw new Error("rate_percent must be >= 0");
  const rate = rate_percent / 100;
  const net = inclusive ? amount / (1 + rate) : amount;
  const gross = inclusive ? amount : amount * (1 + rate);
  return { net: round(net), vat: round(gross - net), gross: round(gross), rate_percent };
}

export function depreciationSchedule(cost, salvage, life_years, method = "straight_line") {
  if (life_years <= 0) throw new Error("life_years must be > 0");
  if (salvage > cost) throw new Error("salvage cannot exceed cost");
  const base = cost - salvage;
  const schedule = [];
  let book = cost;
  for (let year = 1; year <= life_years; year++) {
    const remaining = life_years - year + 1;
    let dep;
    if (method === "straight_line") dep = base / life_years;
    else if (method === "sum_of_years") dep = (base * remaining) / ((life_years * (life_years + 1)) / 2);
    else if (method === "declining_balance") dep = Math.max((book * 2) / life_years, (book - salvage) / remaining);
    else throw new Error(`unknown method: ${method}`);
    dep = Math.min(dep, book - salvage);
    if (year === life_years) dep = book - salvage;
    book -= dep;
    schedule.push({ year, depreciation: round(dep), book_value_end: round(book) });
  }
  return { method, depreciable_base: round(base), schedule };
}

export function loanAmortization(principal, annual_rate_percent, months) {
  if (months <= 0) throw new Error("months must be > 0");
  const r = annual_rate_percent / 100 / 12;
  const payment = r === 0 ? principal / months : (principal * r) / (1 - (1 + r) ** -months);
  let balance = principal;
  let totalInterest = 0;
  const schedule = [];
  for (let m = 1; m <= months; m++) {
    const interest = balance * r;
    const princ = m === months ? balance : payment - interest;
    balance -= princ;
    totalInterest += interest;
    schedule.push({
      month: m,
      payment: round(princ + interest),
      interest: round(interest),
      principal: round(princ),
      balance: round(Math.max(balance, 0)),
    });
  }
  return {
    monthly_payment: round(payment),
    total_interest: round(totalInterest),
    total_paid: round(principal + totalInterest),
    schedule,
  };
}

export function npv(rate_percent, cashFlows) {
  const r = rate_percent / 100;
  return cashFlows.reduce((s, cf, t) => s + cf / (1 + r) ** t, 0);
}

export function irr(cashFlows) {
  if (!(cashFlows.some((c) => c < 0) && cashFlows.some((c) => c > 0))) return null;
  let lo = -99, hi = 1000;
  let fLo = npv(lo, cashFlows);
  if (fLo * npv(hi, cashFlows) > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    const fMid = npv(mid, cashFlows);
    if (Math.abs(fMid) < 1e-9) break;
    if (fLo * fMid < 0) hi = mid;
    else { lo = mid; fLo = fMid; }
  }
  return (lo + hi) / 2;
}

export function paybackPeriod(cashFlows) {
  let cum = 0;
  for (let t = 0; t < cashFlows.length; t++) {
    const prev = cum;
    const cf = cashFlows[t];
    cum += cf;
    if (cum >= 0 && t > 0) return t - 1 + (cf ? -prev / cf : 0);
  }
  return null;
}

export function investmentAppraisal(rate_percent, cash_flows) {
  const i = irr(cash_flows);
  const p = paybackPeriod(cash_flows);
  return {
    npv: round(npv(rate_percent, cash_flows)),
    irr_percent: i === null ? null : round(i),
    payback_years: p === null ? null : round(p),
  };
}

export function breakEven(fixed_costs, price_per_unit, variable_cost_per_unit, target_profit = 0) {
  const margin = price_per_unit - variable_cost_per_unit;
  if (margin <= 0) throw new Error("price must exceed variable cost per unit");
  const units = (fixed_costs + target_profit) / margin;
  return {
    contribution_margin_per_unit: round(margin),
    contribution_margin_ratio_percent: round((margin / price_per_unit) * 100),
    units: round(units),
    revenue: round(units * price_per_unit),
  };
}

export function financialRatios(i = {}) {
  const v = (k) => Number(i[k] ?? 0);
  const div = (a, b, pct = false) => (b ? round((a / b) * (pct ? 100 : 1)) : null);
  const out = {
    current_ratio: div(v("current_assets"), v("current_liabilities")),
    quick_ratio: div(v("current_assets") - v("inventory"), v("current_liabilities")),
    cash_ratio: div(v("cash"), v("current_liabilities")),
    debt_to_equity: div(v("total_liabilities"), v("equity")),
    debt_ratio_percent: div(v("total_liabilities"), v("total_assets"), true),
    gross_margin_percent: div(v("revenue") - v("cost_of_sales"), v("revenue"), true),
    net_margin_percent: div(v("net_income"), v("revenue"), true),
    roa_percent: div(v("net_income"), v("total_assets"), true),
    roe_percent: div(v("net_income"), v("equity"), true),
    asset_turnover: div(v("revenue"), v("total_assets")),
    dso_days: div(v("receivables") * 365, v("revenue")),
    dio_days: div(v("inventory") * 365, v("cost_of_sales")),
    dpo_days: div(v("payables") * 365, v("cost_of_sales")),
  };
  if (out.dso_days !== null && out.dio_days !== null && out.dpo_days !== null) {
    out.cash_conversion_cycle_days = round(out.dso_days + out.dio_days - out.dpo_days);
  }
  return Object.fromEntries(Object.entries(out).filter(([, x]) => x !== null));
}

export function checkJournalEntry(lines) {
  // Work in integer cents to avoid floating-point drift.
  const cents = (x) => Math.round(Number(x || 0) * 100);
  const problems = [];
  let dr = 0, cr = 0;
  lines.forEach((line, idx) => {
    const n = idx + 1;
    const d = cents(line.debit), c = cents(line.credit);
    if (!String(line.account ?? "").trim()) problems.push(`line ${n}: missing account`);
    if (d < 0 || c < 0) problems.push(`line ${n}: negative amount`);
    if (d && c) problems.push(`line ${n}: both debit and credit set`);
    if (!d && !c) problems.push(`line ${n}: zero line`);
    dr += d; cr += c;
  });
  if (lines.length < 2) problems.push("an entry needs at least two lines");
  if (dr !== cr) problems.push(`unbalanced by ${(dr - cr) / 100}`);
  return { balanced: problems.length === 0, total_debit: dr / 100, total_credit: cr / 100, problems };
}

export function concreteQuantity(length_m, width_m, depth_m, count = 1, waste_percent = 5, unit_price = 0) {
  if ([length_m, width_m, depth_m].some((x) => x <= 0)) throw new Error("dimensions must be > 0");
  const net = length_m * width_m * depth_m * count;
  const gross = net * (1 + waste_percent / 100);
  const out = { net_m3: round(net, 3), with_waste_m3: round(gross, 3), waste_percent };
  if (unit_price) out.estimated_cost = round(gross * unit_price);
  return out;
}
