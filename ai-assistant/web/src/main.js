// Chat UI shared by both builds. The backend (Claude API or the local
// Ollama server) is injected by entry-claude.js / entry-local.js.
import DOMPurify from "dompurify";
import { marked } from "marked";

/**
 * backend: {
 *   needsKey: boolean,
 *   create({ key, effort }) -> bot with ask()/reset()/messages,
 *   describeError(e) -> string | null,
 *   isAuthError(e) -> boolean,
 * }
 */
export function start(backend) {

const $ = (sel) => document.querySelector(sel);
const log = $("#log");
const input = $("#input");
const sendBtn = $("#send");
const stopBtn = $("#stop");
const settings = $("#settings");

const TOOL_LABELS = {
  calculate_vat: "حساب الضريبة",
  depreciation_schedule: "جدول الإهلاك",
  loan_amortization: "جدول القرض",
  investment_appraisal: "دراسة الجدوى",
  break_even: "نقطة التعادل",
  financial_ratios: "النسب المالية",
  check_journal_entry: "التحقّق من القيد",
  concrete_quantity: "حصر الخرسانة",
  save_file: "تجهيز ملفّ",
};

// --- Settings (per-browser; storage can be unavailable) ---------------------

const store = {
  get(k) { try { return localStorage.getItem(k) ?? ""; } catch { return ""; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* private mode */ } },
};

let bot = null;

function makeBot() {
  const key = store.get("khabeer.key");
  bot = !backend.needsKey || key ? backend.create({ key, effort: store.get("khabeer.effort") || "high" }) : null;
}

function openSettings() {
  $("#key").value = store.get("khabeer.key");
  $("#effort").value = store.get("khabeer.effort") || "high";
  settings.showModal();
}

$("#settings-form").addEventListener("submit", (e) => {
  if (e.submitter?.value !== "save") return;
  const key = $("#key").value.trim();
  if (key) store.set("khabeer.key", key); else store.del("khabeer.key");
  store.set("khabeer.effort", $("#effort").value);
  const history = bot?.messages ?? [];
  makeBot();
  if (bot) bot.messages = history;
});
$("#open-settings").addEventListener("click", openSettings);
$("#forget-key").addEventListener("click", () => { $("#key").value = ""; });

// --- Rendering ---------------------------------------------------------------

function md(text) {
  return DOMPurify.sanitize(marked.parse(text, { breaks: true }));
}

function addMessage(role) {
  $("#welcome")?.remove();
  const el = document.createElement("article");
  el.className = `msg ${role}`;
  log.append(el);
  return el;
}

function scrollDown() {
  window.scrollTo({ top: document.body.scrollHeight });
}

function fileCard(filename, content) {
  const card = document.createElement("div");
  card.className = "file";
  const size = new Blob([content]).size;
  const type = filename.endsWith(".html") || filename.endsWith(".htm") ? "text/html" : "text/plain";
  const url = URL.createObjectURL(new Blob([content], { type: `${type};charset=utf-8` }));

  const name = document.createElement("span");
  name.className = "file-name";
  name.textContent = `📄 ${filename}`;
  const meta = document.createElement("span");
  meta.className = "file-meta";
  meta.textContent = size > 1024 ? `${(size / 1024).toFixed(1)} ك.ب` : `${size} بايت`;
  const dl = document.createElement("a");
  dl.className = "btn small";
  dl.href = url;
  dl.download = filename.split("/").pop();
  dl.textContent = "تنزيل";
  card.append(name, meta);
  if (type === "text/html") {
    const view = document.createElement("button");
    view.className = "btn small";
    view.type = "button";
    view.textContent = "معاينة";
    view.addEventListener("click", () => {
      // Scripts may run, but without same-origin access to this page.
      $("#preview-frame").srcdoc = content;
      $("#preview-title").textContent = filename;
      $("#preview").showModal();
    });
    card.append(view);
  }
  card.append(dl);
  return card;
}

// --- Chat --------------------------------------------------------------------

let controller = null;

function setBusy(busy) {
  sendBtn.hidden = busy;
  stopBtn.hidden = !busy;
  input.disabled = busy;
  if (!busy) input.focus();
}

async function send(text) {
  if (!text.trim() || controller) return;
  if (!bot) { openSettings(); return; }

  addMessage("user").textContent = text;
  input.value = "";
  autosize();

  const reply = addMessage("assistant");
  const tools = document.createElement("div");
  tools.className = "tools";
  const body = document.createElement("div");
  body.className = "body";
  const files = document.createElement("div");
  files.className = "files";
  const thinking = document.createElement("div");
  thinking.className = "thinking";
  thinking.textContent = "يفكّر…";
  reply.append(tools, body, files, thinking);
  scrollDown();

  let raw = "";
  let pending = false;
  const render = () => {
    pending = false;
    body.innerHTML = md(raw);
    scrollDown();
  };

  controller = new AbortController();
  setBusy(true);
  try {
    const answer = await bot.ask(text, {
      signal: controller.signal,
      onText: (delta) => {
        raw += delta;
        thinking.hidden = true;
        if (!pending) { pending = true; requestAnimationFrame(render); }
      },
      onTool: (name) => {
        thinking.hidden = false;
        thinking.textContent = `${TOOL_LABELS[name] ?? name}…`;
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = `⚙ ${TOOL_LABELS[name] ?? name}`;
        tools.append(chip);
      },
      onFile: (filename, content) => files.append(fileCard(filename, content)),
    });
    raw = raw.trim() ? raw : answer;
    render();
  } catch (e) {
    const err = document.createElement("div");
    err.className = "error";
    err.textContent = describeError(e);
    reply.append(err);
    if (backend.isAuthError(e)) openSettings();
  } finally {
    thinking.remove();
    controller = null;
    setBusy(false);
    scrollDown();
  }
}

function describeError(e) {
  if (e?.name === "AbortError") return "أُوقف الردّ.";
  return backend.describeError(e) ?? `خطأ غير متوقّع: ${e?.message ?? e}`;
}

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 240)}px`;
}

$("#composer").addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
});
stopBtn.addEventListener("click", () => controller?.abort());
$("#new-chat").addEventListener("click", () => {
  if (controller) return;
  bot?.reset();
  location.reload();
});
document.querySelectorAll("[data-example]").forEach((b) =>
  b.addEventListener("click", () => send(b.querySelector("span").textContent)),
);

if (!backend.needsKey) {
  $("#open-settings").hidden = true;
}
makeBot();
if (!bot) openSettings();
input.focus();
}
