// Online build: Claude API, key entered by each user.
import Anthropic from "@anthropic-ai/sdk";

import { Khabeer, TurnFailed } from "./agent.js";
import { start } from "./main.js";

start({
  needsKey: true,
  create: ({ key, effort }) => new Khabeer(key, { effort }),
  isAuthError: (e) => e instanceof Anthropic.AuthenticationError,
  describeError(e) {
    if (e instanceof TurnFailed) return e.message;
    if (e instanceof Anthropic.APIUserAbortError) return "أُوقف الردّ.";
    if (e instanceof Anthropic.AuthenticationError) return "مفتاح API غير صالح. أدخل مفتاحاً صحيحاً من الإعدادات.";
    if (e instanceof Anthropic.PermissionDeniedError) return "المفتاح لا يملك صلاحية استخدام هذا النموذج.";
    if (e instanceof Anthropic.RateLimitError) return "تجاوزت حدّ الطلبات؛ انتظر قليلاً ثم أعد المحاولة.";
    if (e instanceof Anthropic.APIConnectionError) return "تعذّر الاتصال بالخادم؛ تحقّق من الإنترنت.";
    if (e instanceof Anthropic.APIError) return `خطأ من الخادم (${e.status ?? "?"}): ${e.message}`;
    return null;
  },
});
