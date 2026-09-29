"""Conversation loop against a local Ollama server, with the calc.py tools."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .. import calc
from ..prompts import SYSTEM_PROMPT

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
MODEL = os.environ.get("KHABEER_LOCAL_MODEL", "qwen3:8b")
OUTPUT_DIR = Path(os.environ.get("KHABEER_OUTPUT_DIR", "output")).resolve()
MAX_TOOL_ROUNDS = 15
TIMEOUT = 600  # seconds; local models on CPU can be slow

# Small models follow short, explicit rules better than long prose.
LOCAL_RULES = """
## قواعد إضافية
- استخدم أداةً في كلّ عملية حسابية، ولا تخترع أرقاماً.
- بعد نتيجة الأداة، اكتب الجواب النهائي بالعربية واعرض الأرقام كما أعادتها الأداة.
- لا تكرّر استدعاء الأداة نفسها بالمدخلات نفسها.
"""


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _num(description: str) -> dict:
    return {"type": "number", "description": description}


TOOLS = [
    _fn("calculate_vat", "Split an amount into net, VAT and gross.", {
        "amount": _num("The amount."),
        "rate_percent": _num("VAT rate in percent, e.g. 15."),
        "inclusive": {"type": "boolean", "description": "True if the amount already includes VAT."},
    }, ["amount", "rate_percent"]),
    _fn("depreciation_schedule", "Yearly depreciation schedule for a fixed asset.", {
        "cost": _num("Acquisition cost."),
        "salvage": _num("Residual value at end of life."),
        "life_years": {"type": "integer", "description": "Useful life in years."},
        "method": {"type": "string", "enum": ["straight_line", "declining_balance", "sum_of_years"]},
    }, ["cost", "salvage", "life_years"]),
    _fn("loan_amortization", "Equal monthly installment loan schedule.", {
        "principal": _num("Loan amount."),
        "annual_rate_percent": _num("Annual interest rate in percent."),
        "months": {"type": "integer", "description": "Number of monthly installments."},
    }, ["principal", "annual_rate_percent", "months"]),
    _fn("investment_appraisal", "NPV, IRR and payback period for a project.", {
        "rate_percent": _num("Discount rate in percent."),
        "cash_flows": {"type": "array", "items": {"type": "number"},
                       "description": "Yearly cash flows; the first is the (negative) investment at time 0."},
    }, ["rate_percent", "cash_flows"]),
    _fn("break_even", "Break-even units and revenue, optionally for a target profit.", {
        "fixed_costs": _num("Total fixed costs."),
        "price_per_unit": _num("Selling price per unit."),
        "variable_cost_per_unit": _num("Variable cost per unit."),
        "target_profit": _num("Desired profit; 0 for plain break-even."),
    }, ["fixed_costs", "price_per_unit", "variable_cost_per_unit"]),
    _fn("financial_ratios", "Liquidity, leverage, profitability and efficiency ratios from the given figures.", {
        k: _num(k.replace("_", " ")) for k in (
            "current_assets", "current_liabilities", "inventory", "cash", "total_assets",
            "total_liabilities", "equity", "revenue", "cost_of_sales", "net_income",
            "receivables", "payables")
    }, []),
    _fn("check_journal_entry", "Verify a double-entry journal entry balances.", {
        "lines": {"type": "array", "description": "Lines with account, debit, credit.", "items": {
            "type": "object",
            "properties": {"account": {"type": "string"}, "debit": {"type": "number"},
                           "credit": {"type": "number"}},
            "required": ["account", "debit", "credit"]}},
    }, ["lines"]),
    _fn("concrete_quantity", "Concrete volume and optional cost for rectangular elements.", {
        "length_m": _num("Length in meters."),
        "width_m": _num("Width in meters."),
        "depth_m": _num("Depth in meters."),
        "count": {"type": "integer", "description": "Number of identical elements."},
        "waste_percent": _num("Waste allowance in percent."),
        "unit_price": _num("Price per cubic meter; 0 to skip cost."),
    }, ["length_m", "width_m", "depth_m"]),
    _fn("save_file", "Save a deliverable (HTML page, code, CSV, report) to the output folder.", {
        "filename": {"type": "string", "description": 'Relative file name, e.g. "landing.html".'},
        "content": {"type": "string", "description": "Full file content."},
    }, ["filename", "content"]),
]


def safe_output_path(filename: str) -> Path:
    path = (OUTPUT_DIR / filename).resolve()
    if not path.is_relative_to(OUTPUT_DIR) or path == OUTPUT_DIR:
        raise ValueError("filename must stay inside the output directory")
    return path


def _save_file(filename: str, content: str) -> dict:
    path = safe_output_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"saved": str(path), "bytes": len(content.encode("utf-8"))}


HANDLERS: dict[str, Callable[..., dict]] = {
    "calculate_vat": calc.vat,
    "depreciation_schedule": calc.depreciation_schedule,
    "loan_amortization": calc.loan_amortization,
    "investment_appraisal": calc.investment_appraisal,
    "break_even": calc.break_even,
    "financial_ratios": calc.financial_ratios,
    "check_journal_entry": calc.check_journal_entry,
    "concrete_quantity": calc.concrete_quantity,
    "save_file": _save_file,
}


def run_tool(name: str, args) -> str:
    """Run a tool; any failure (bad name, bad args, bad values) becomes {"error": ...}."""
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    if isinstance(args, str):  # some models send arguments as a JSON string
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return json.dumps({"error": "arguments are not valid JSON"})
    try:
        return json.dumps(handler(**(args or {})), ensure_ascii=False)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError, OSError) as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


_THINK = re.compile(r"<think>.*?</think>", re.S)


class OllamaError(Exception):
    """Ollama is not running, the model is missing, or the request failed."""


class LocalKhabeer:
    def __init__(self, model: str = MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + LOCAL_RULES}]

    def reset(self) -> None:
        del self.messages[1:]

    def _chat(self) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": self.messages,
            "tools": TOOLS,
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 16384},
        }).encode()
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 404 or "not found" in detail:
                raise OllamaError(f"النموذج {self.model} غير مُنزَّل. نفّذ: ollama pull {self.model}") from e
            raise OllamaError(f"خطأ من Ollama ({e.code}): {detail}") from e
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise OllamaError("برنامج Ollama لا يعمل. شغّله ثم أعد المحاولة.") from e

    def ask(self, text: str, on_tool: Callable[[str, dict], None] | None = None) -> dict:
        """Send one message; returns {"answer": str, "files": [paths]}. Rolls back on error."""
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        files: list[str] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                msg = self._chat().get("message", {})
                calls = msg.get("tool_calls") or []
                self.messages.append({
                    "role": "assistant",
                    "content": msg.get("content", ""),
                    **({"tool_calls": calls} if calls else {}),
                })
                if not calls:
                    return {"answer": _THINK.sub("", msg.get("content", "")).strip(), "files": files}
                for call in calls:
                    fn = call.get("function", {})
                    name, args = fn.get("name", ""), fn.get("arguments", {})
                    if on_tool:
                        on_tool(name, args if isinstance(args, dict) else {})
                    result = run_tool(name, args)
                    if name == "save_file" and '"saved"' in result:
                        files.append(json.loads(result)["saved"])
                    self.messages.append({"role": "tool", "tool_name": name, "content": result})
            raise OllamaError("تجاوز النموذج الحدّ الأقصى لخطوات الأدوات.")
        except BaseException:
            del self.messages[checkpoint:]
            raise
