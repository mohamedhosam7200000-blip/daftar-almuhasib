// Same expectations as tests/test_calc.py, so both ports stay in step.
import assert from "node:assert/strict";
import { test } from "node:test";

import * as calc from "../src/calc.js";
import { runTool } from "../src/tools.js";

test("vat", () => {
  assert.deepEqual(calc.vat(1000, 15), { net: 1000, vat: 150, gross: 1150, rate_percent: 15 });
  const r = calc.vat(1150, 15, true);
  assert.equal(r.net, 1000);
  assert.equal(r.vat, 150);
});

test("straight line depreciation", () => {
  const s = calc.depreciationSchedule(10000, 1000, 3).schedule;
  assert.deepEqual(s.map((r) => r.depreciation), [3000, 3000, 3000]);
  assert.equal(s.at(-1).book_value_end, 1000);
});

test("accelerated methods end at salvage", () => {
  for (const m of ["declining_balance", "sum_of_years"]) {
    const s = calc.depreciationSchedule(50000, 5000, 5, m).schedule;
    assert.equal(s.at(-1).book_value_end, 5000);
    assert.ok(s[0].depreciation > s.at(-1).depreciation);
  }
  assert.equal(calc.depreciationSchedule(15000, 0, 5, "sum_of_years").schedule[0].depreciation, 5000);
});

test("loan", () => {
  const r = calc.loanAmortization(100000, 12, 12);
  assert.equal(r.monthly_payment, 8884.88);
  assert.equal(r.schedule.at(-1).balance, 0);
  assert.equal(calc.loanAmortization(1200, 0, 12).monthly_payment, 100);
});

test("investment appraisal", () => {
  assert.deepEqual(calc.investmentAppraisal(10, [-1000, 500, 500, 500]), {
    npv: 243.43, irr_percent: 23.38, payback_years: 2,
  });
  assert.equal(calc.irr([100, 200]), null);
});

test("break even", () => {
  const r = calc.breakEven(10000, 50, 30);
  assert.equal(r.units, 500);
  assert.equal(r.revenue, 25000);
  assert.throws(() => calc.breakEven(100, 10, 10));
});

test("ratios skip missing inputs", () => {
  assert.deepEqual(calc.financialRatios({ current_assets: 200, current_liabilities: 100, inventory: 50 }), {
    current_ratio: 2, quick_ratio: 1.5, cash_ratio: 0,
  });
});

test("journal entry", () => {
  assert.ok(calc.checkJournalEntry([
    { account: "الصندوق", debit: 1150, credit: 0 },
    { account: "المبيعات", debit: 0, credit: 1000 },
    { account: "ضريبة القيمة المضافة المستحقة", debit: 0, credit: 150 },
  ]).balanced);
  assert.ok(calc.checkJournalEntry([
    { account: "a", debit: 0.1, credit: 0 }, { account: "b", debit: 0.2, credit: 0 },
    { account: "c", debit: 0, credit: 0.3 },
  ]).balanced);
  const bad = calc.checkJournalEntry([
    { account: "الصندوق", debit: 100, credit: 0 },
    { account: "المبيعات", debit: 0, credit: 90 },
  ]);
  assert.equal(bad.balanced, false);
  assert.match(bad.problems[0], /unbalanced by 10/);
});

test("concrete", () => {
  assert.deepEqual(calc.concreteQuantity(2, 2, 0.5, 4, 5, 100), {
    net_m3: 8, with_waste_m3: 8.4, waste_percent: 5, estimated_cost: 840,
  });
});

test("runTool reports errors instead of throwing", () => {
  assert.deepEqual(JSON.parse(runTool("break_even", { fixed_costs: 1, price_per_unit: 1, variable_cost_per_unit: 2 })),
    { error: "price must exceed variable cost per unit" });
  assert.match(runTool("nope", {}), /unknown tool/);
});
