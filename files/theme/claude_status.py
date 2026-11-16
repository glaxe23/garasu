"""Пишет в файл, чем сейчас занят Claude Code, чтобы это показывала «таблетка» на панели.
Запускается хуками Claude Code (настроены в ~/.claude/settings.json), на вход получает JSON события:

  python claude_status.py tool     - перед каждым действием (PreToolUse)
  python claude_status.py think    - когда отправлен запрос (UserPromptSubmit)
  python claude_status.py wait     - когда Claude ждёт ответа или разрешения (Notification)
  python claude_status.py stop     - когда Claude закончил (Stop)

Файл claude_status.txt содержит одну короткую строку или пуст (тогда таблетка скрыта)."""
import os, sys, json

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_status.txt")
MAX = 46


def short(s):
    s = " ".join(str(s).split())
    return s if len(s) <= MAX else s[:MAX - 1].rstrip() + "…"


def name(path):
    return os.path.basename(str(path).replace("\\", "/").rstrip("/")) or str(path)


def describe(d):
    tool = d.get("tool_name", "")
    i = d.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        return i.get("description") or "выполняет команду"
    if tool == "Read":
        return "читает " + name(i.get("file_path", "файл"))
    if tool in ("Edit", "Write", "NotebookEdit"):
        return "правит " + name(i.get("file_path", "файл"))
    if tool in ("Grep", "Glob"):
        return "ищет: " + str(i.get("pattern", ""))
    if tool in ("WebFetch", "WebSearch"):
        return "смотрит в интернете"
    if tool == "Agent":
        return "помощник: " + str(i.get("description", ""))
    if tool == "AskUserQuestion":
        return "ждёт твоего ответа"
    if tool == "Skill":
        return "навык: " + str(i.get("skill", ""))
    if "Browser" in tool or "chrome" in tool:
        return "работает в браузере"
    if tool.endswith("update_plan") or tool.endswith("wrap_up"):
        return ""                                   # служебное, статус не меняем
    return tool.split("__")[-1] if tool else "работает"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tool"
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except Exception:
        d = {}
    if mode == "stop":
        text = ""
    elif mode == "think":
        text = "думает"
    elif mode == "wait":
        text = "ждёт тебя"
    else:
        text = describe(d)
        if text == "":
            return
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(short(text))
    os.replace(tmp, OUT)


try:
    main()
except Exception:
    pass
