"""Задачи из заметки Obsidian для виджета «Задачи».

  python tasks.py sync            - прочитать заметку и записать tasks.json для виджета
  python tasks.py toggle <строка> - отметить задачу в этой строке заметки выполненной / невыполненной
  python tasks.py add <текст>     - дописать новую задачу в заметку (после последней задачи)

Задача - строка вида «- [ ] текст» или «- [x] текст». Меняется только символ в скобках."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W

OUT = os.path.join(W.zdir, "tasks.json")
RX = re.compile(r"^(\s*[-*+] \[)([ xX])(\] )(.*)$")


def clean(s):
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)        # [[заметка|текст]] -> текст
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)               # [текст](ссылка) -> текст
    return re.sub(r"[*_`~]{1,2}", "", s).strip()


def read(note):
    return open(note, encoding="utf-8", newline="").read().split("\n")


def sync(cfg=None):
    cfg = cfg or W.load()
    note = cfg["tasks"]["note"]
    data = {"note": os.path.splitext(os.path.basename(note))[0], "items": [], "open": 0, "done": 0, "error": ""}
    try:
        for i, line in enumerate(read(note)):
            m = RX.match(line.rstrip("\r"))
            if m:
                done = m.group(2) != " "
                data["items"].append({"line": i, "text": clean(m.group(4)), "done": done})
                data["done" if done else "open"] += 1
    except FileNotFoundError:
        data["error"] = "Заметка не найдена. Выбери её в настройках виджета."
    except Exception as e:
        data["error"] = "Не удалось прочитать заметку: %s" % e
    tmp = OUT + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    return data


def toggle(n):
    cfg = W.load()
    note = cfg["tasks"]["note"]
    lines = read(note)
    m = RX.match(lines[n].rstrip("\r")) if 0 <= n < len(lines) else None
    if m:
        tail = "\r" if lines[n].endswith("\r") else ""
        lines[n] = m.group(1) + ("x" if m.group(2) == " " else " ") + m.group(3) + m.group(4) + tail
        with open(note, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines))
    sync(cfg)
    try:                      # заметка изменилась: помощник заметит это сам и обновит строку на панели
        os.utime(note, None)
    except OSError:
        pass


def add(text):
    text = " ".join(text.split())
    if not text:
        return
    cfg = W.load()
    note = cfg["tasks"]["note"]
    try:
        lines = read(note)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(note), exist_ok=True)
        lines = ["# Задачи", "", ""]
    cr = "\r" if any(l.endswith("\r") for l in lines) else ""
    last = max((i for i, l in enumerate(lines) if RX.match(l.rstrip("\r"))), default=None)
    new = "- [ ] " + text + cr
    if last is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ([cr] if lines else []) + [new, ""]
    else:
        if not lines[last].endswith("\r") and cr and last == len(lines) - 1:
            lines[last] += cr
        lines.insert(last + 1, new)
    with open(note, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    sync(cfg)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "toggle":
        toggle(int(sys.argv[2]))
    elif len(sys.argv) > 2 and sys.argv[1] == "add":
        add(" ".join(sys.argv[2:]))
    else:
        d = sync()
        if sys.stdout:
            print(d["note"], "open:", d["open"], "done:", d["done"], d["error"])
