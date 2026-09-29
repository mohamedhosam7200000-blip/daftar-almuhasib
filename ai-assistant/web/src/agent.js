// Conversation loop in the browser: Claude + local calculation tools.
import Anthropic from "@anthropic-ai/sdk";

import { SYSTEM_PROMPT } from "./prompt.js";
import { TOOLS, runTool } from "./tools.js";

export const MODEL = "claude-opus-5-5";
const MAX_TOKENS = 64000;
const MAX_TOOL_ROUNDS = 25;

export class TurnFailed extends Error {}

export class Khabeer {
  constructor(apiKey, { effort = "high", fetch } = {}) {
    // The key belongs to the person using the page and never leaves their
    // browser except to api.anthropic.com.
    this.client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true, ...(fetch && { fetch }) });
    this.effort = effort;
    this.messages = [];
  }

  reset() {
    this.messages = [];
  }

  /**
   * Send one user message and run tool calls until Claude answers.
   * Callbacks: onText(delta), onTool(name, input), onFile(filename, content).
   * On failure the conversation is rolled back to before this message.
   */
  async ask(text, { onText, onTool, onFile, signal } = {}) {
    const checkpoint = this.messages.length;
    this.messages.push({ role: "user", content: text });
    try {
      return await this.#run({ onText, onTool, onFile, signal });
    } catch (e) {
      this.messages.length = checkpoint;
      throw e;
    }
  }

  async #run({ onText, onTool, onFile, signal }) {
    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      // Tool inputs are not streamed eagerly: the server validates them
      // against the schema before we run anything.
      const stream = this.client.beta.messages.stream(
        {
          model: MODEL,
          max_tokens: MAX_TOKENS,
          system: SYSTEM_PROMPT,
          tools: TOOLS,
          messages: this.messages,
          thinking: { type: "adaptive" },
          output_config: { effort: this.effort },
          cache_control: { type: "ephemeral" },
          // On a safety decline, the API retries on a suitable fallback model.
          betas: ["server-side-fallback-2026-07-01"],
          fallbacks: "default",
        },
        { signal },
      );
      if (onText) stream.on("text", onText);
      const message = await stream.finalMessage();

      // Append the full content (thinking blocks included, unchanged).
      this.messages.push({ role: "assistant", content: message.content });

      if (message.stop_reason === "refusal") {
        throw new TurnFailed("رُفض الطلب لأسباب تتعلّق بسياسة الاستخدام.");
      }
      if (message.stop_reason === "max_tokens") {
        throw new TurnFailed("الجواب أطول من الحدّ المسموح؛ اطلب جزءاً أصغر أو قسّم المهمّة.");
      }

      const toolUses = message.content.filter((b) => b.type === "tool_use");
      if (message.stop_reason !== "tool_use" || toolUses.length === 0) {
        return message.content.filter((b) => b.type === "text").map((b) => b.text).join("");
      }

      // All results go back together in one user message.
      const results = toolUses.map((b) => {
        onTool?.(b.name, b.input);
        if (b.name === "save_file" && b.input?.filename) onFile?.(b.input.filename, b.input.content ?? "");
        const content = runTool(b.name, b.input);
        const isError = content.startsWith('{"error"');
        return { type: "tool_result", tool_use_id: b.id, content, ...(isError && { is_error: true }) };
      });
      this.messages.push({ role: "user", content: results });
      onText?.("\n\n");
    }
    throw new TurnFailed("تجاوز المساعد الحدّ الأقصى لخطوات الأدوات في رسالة واحدة.");
  }
}
