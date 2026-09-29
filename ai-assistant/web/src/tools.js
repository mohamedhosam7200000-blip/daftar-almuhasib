// Tool definitions sent to Claude, and the dispatcher that runs them locally.
import * as calc from "./calc.js";

const num = (description) => ({ type: "number", description });

function tool(name, description, properties, required) {
  return {
    name,
    description,
    input_schema: { type: "object", properties, required, additionalProperties: false },
  };
}

export const TOOLS = [
  tool("calculate_vat", "Split an amount into net, VAT and gross.", {
    amount: num("The amount."),
    rate_percent: num("VAT rate in percent, e.g. 15 or 14."),
    inclusive: { type: "boolean", description: "True if the amount already includes VAT." },
  }, ["amount", "rate_percent"]),

  tool("depreciation_schedule", "Yearly depreciation schedule for a fixed asset.", {
    cost: num("Acquisition cost."),
    salvage: num("Residual (scrap) value at end of life."),
    life_years: { type: "integer", description: "Useful life in years." },
    method: { type: "string", enum: ["straight_line", "declining_balance", "sum_of_years"] },
  }, ["cost", "salvage", "life_years"]),

  tool("loan_amortization", "Equal monthly installment loan schedule with interest/principal split.", {
    principal: num("Loan amount."),
    annual_rate_percent: num("Annual interest rate in percent."),
    months: { type: "integer", description: "Number of monthly installments." },
  }, ["principal", "annual_rate_percent", "months"]),

  tool("investment_appraisal", "NPV, IRR and payback period for a project (feasibility study).", {
    rate_percent: num("Discount rate (cost of capital) in percent."),
    cash_flows: {
      type: "array", items: { type: "number" },
      description: "Yearly cash flows; the first is at time 0, usually the negative investment.",
    },
  }, ["rate_percent", "cash_flows"]),

  tool("break_even", "Break-even units and revenue, optionally for a target profit.", {
    fixed_costs: num("Total fixed costs for the period."),
    price_per_unit: num("Selling price per unit."),
    variable_cost_per_unit: num("Variable cost per unit."),
    target_profit: num("Desired profit; 0 for plain break-even."),
  }, ["fixed_costs", "price_per_unit", "variable_cost_per_unit"]),

  tool("financial_ratios",
    "Liquidity, leverage, profitability and efficiency ratios. Only ratios whose inputs are provided are returned.",
    Object.fromEntries([
      "current_assets", "current_liabilities", "inventory", "cash", "total_assets", "total_liabilities",
      "equity", "revenue", "cost_of_sales", "net_income", "receivables", "payables",
    ].map((k) => [k, num(k.replaceAll("_", " "))])),
    []),

  tool("check_journal_entry", "Verify a double-entry journal entry balances and each line is valid.", {
    lines: {
      type: "array",
      description: "Entry lines; each has account, debit and credit (one of them 0).",
      items: {
        type: "object",
        properties: { account: { type: "string" }, debit: { type: "number" }, credit: { type: "number" } },
        required: ["account", "debit", "credit"],
        additionalProperties: false,
      },
    },
  }, ["lines"]),

  tool("concrete_quantity", "Concrete volume (and optional cost) for rectangular elements.", {
    length_m: num("Length in meters."),
    width_m: num("Width in meters."),
    depth_m: num("Depth/thickness in meters."),
    count: { type: "integer", description: "Number of identical elements." },
    waste_percent: num("Waste allowance in percent (default 5)."),
    unit_price: num("Price per cubic meter; 0 to skip the cost estimate."),
  }, ["length_m", "width_m", "depth_m"]),

  tool("save_file",
    "Give the user a deliverable file (HTML page, CSS, code, CSV, Markdown report) to preview and download.", {
      filename: { type: "string", description: 'File name, e.g. "landing.html" or "budget.csv".' },
      content: { type: "string", description: "Full file content." },
    }, ["filename", "content"]),
];

const HANDLERS = {
  calculate_vat: (a) => calc.vat(a.amount, a.rate_percent, a.inclusive ?? false),
  depreciation_schedule: (a) => calc.depreciationSchedule(a.cost, a.salvage, a.life_years, a.method),
  loan_amortization: (a) => calc.loanAmortization(a.principal, a.annual_rate_percent, a.months),
  investment_appraisal: (a) => calc.investmentAppraisal(a.rate_percent, a.cash_flows),
  break_even: (a) => calc.breakEven(a.fixed_costs, a.price_per_unit, a.variable_cost_per_unit, a.target_profit ?? 0),
  financial_ratios: (a) => calc.financialRatios(a),
  check_journal_entry: (a) => calc.checkJournalEntry(a.lines),
  concrete_quantity: (a) =>
    calc.concreteQuantity(a.length_m, a.width_m, a.depth_m, a.count ?? 1, a.waste_percent ?? 5, a.unit_price ?? 0),
  // The UI shows the file; here we only acknowledge it.
  save_file: (a) => ({ saved: a.filename, bytes: new TextEncoder().encode(a.content).length }),
};

/** Run a tool and return its JSON result as a string; errors become {error}. */
export function runTool(name, input) {
  const handler = HANDLERS[name];
  if (!handler) return JSON.stringify({ error: `unknown tool: ${name}` });
  try {
    return JSON.stringify(handler(input ?? {}));
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}
