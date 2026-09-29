// Backend for the offline build: talks to the local Python server
// (python -m khabeer.local.server), which runs the model through Ollama.

export class TurnFailed extends Error {}

export class LocalKhabeer {
  constructor() {
    this.session = crypto.randomUUID?.() ?? String(Math.random()).slice(2);
    this.messages = []; // kept for interface parity with the Claude backend
  }

  reset() {
    fetch("/api/reset", { method: "POST", body: JSON.stringify({ session: this.session }) }).catch(() => {});
  }

  async ask(text, { onText, onTool, onFile, signal } = {}) {
    let res;
    try {
      res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: this.session, text }),
        signal,
      });
    } catch (e) {
      if (e.name === "AbortError") throw e;
      throw new TurnFailed("تعذّر الاتصال بخادم خبير المحلي. هل أغلقت نافذة التشغيل؟");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new TurnFailed(data.error || `خطأ من الخادم المحلي (${res.status})`);
    for (const t of data.tools ?? []) onTool?.(t.name, t.args);
    for (const f of data.files ?? []) onFile?.(f.filename, f.content);
    onText?.(data.answer ?? "");
    return data.answer ?? "";
  }
}
