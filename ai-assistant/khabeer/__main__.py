"""Interactive terminal chat: python -m khabeer"""

from __future__ import annotations

import json
import sys

import anthropic

from .agent import MODEL, Khabeer, TurnFailed
from .tools import OUTPUT_DIR

BANNER = f"""\
خبير — محاسب، مدير مالي وإداري، مهندس، ومصمّم مواقع  ({MODEL})
الملفّات تُحفظ في: {OUTPUT_DIR}
الأوامر:  /جديد  محادثة جديدة   ·   /خروج  إنهاء
"""


def show_tool(name: str, args: dict) -> None:
    summary = json.dumps(args, ensure_ascii=False)
    if len(summary) > 120:
        summary = summary[:117] + "..."
    print(f"  ⚙ {name} {summary}", file=sys.stderr)


def main() -> int:
    print(BANNER)
    bot = Khabeer()
    while True:
        try:
            text = input("أنت › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in ("/خروج", "/exit", "/quit"):
            return 0
        if text in ("/جديد", "/new"):
            bot.reset()
            print("— محادثة جديدة —\n")
            continue
        try:
            answer = bot.ask(text, on_tool=show_tool)
        except TurnFailed as e:
            print(f"⚠ {e}\n")
            continue
        except anthropic.AuthenticationError:
            print("⚠ مفتاح API غير صالح. عيّن المتغيّر ANTHROPIC_API_KEY.")
            return 1
        except anthropic.RateLimitError:
            print("⚠ تجاوزت حدّ الطلبات؛ انتظر قليلاً ثم أعد المحاولة.\n")
            continue
        except anthropic.APIStatusError as e:
            print(f"⚠ خطأ من الخادم ({e.status_code}): {e.message}\n")
            continue
        except anthropic.APIConnectionError:
            print("⚠ تعذّر الاتصال بالخادم؛ تحقّق من الإنترنت.\n")
            continue
        except KeyboardInterrupt:
            print("\n— أُلغي —\n")
            continue
        print(f"\nخبير › {answer}\n")


if __name__ == "__main__":
    sys.exit(main())
