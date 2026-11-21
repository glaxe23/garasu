"""Расписание пар из заметки для виджета «Расписание».

  python schedule.py        - прочитать заметку и записать schedule.json для виджета

Формат заметки: заголовок с днём недели, под ним строки «время начала-конца, название, место»:

  ## Понедельник
  - 08:30-10:00 Геодезия, ауд. 204
  - 10:10-11:40 Математика

Перед днём может стоять любой значок заголовка (#, ##) или ничего. Место после запятой необязательно."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import widgets as W

OUT = os.path.join(W.zdir, "schedule.json")
DAYS = [("понедельник", "пн"), ("вторник", "вт"), ("среда", "ср"), ("четверг", "чт"),
        ("пятница", "пт"), ("суббота", "сб"), ("воскресенье", "вс")]
PAIR = re.compile(r"^\s*(?:[-*+]\s*)?(?:\[.\]\s*)?(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*(.*)$")
TEMPLATE = """---
created: %s
tags: [учёба, расписание]
---

# Расписание

Это расписание показывает виджет «Расписание» на рабочем столе. Замени примеры своими парами.
Строка пары: время начала и конца, название, после запятой место.

## Понедельник
- 08:30-10:00 Пример: первая пара, ауд. 101
- 10:10-11:40 Пример: вторая пара, ауд. 202

## Вторник

## Среда

## Четверг

## Пятница

## Суббота
"""


def day_of(line):
    s = re.sub(r"[#*_:>\-\s]+", " ", line).strip().lower()
    for i, names in enumerate(DAYS):
        if s in names or s.split(" ")[0] == names[0]:
            return i
    return None


def parse(text):
    days, cur = {str(i): [] for i in range(7)}, None
    for line in text.splitlines():
        m = PAIR.match(line)
        if m and cur is not None:
            h1, m1, h2, m2 = (int(v) for v in m.groups()[:4])
            title, _, place = m.group(5).strip().partition(",")
            days[str(cur)].append({"from": h1 * 60 + m1, "to": h2 * 60 + m2,
                                   "title": title.strip() or "Пара", "place": place.strip()})
            continue
        d = day_of(line) if len(line.strip()) < 40 else None
        if d is not None:
            cur = d
    for v in days.values():
        v.sort(key=lambda p: p["from"])
    return days


def sync(cfg=None):
    cfg = cfg or W.load()
    note = cfg["schedule"]["note"]
    data = {"days": {}, "error": ""}
    try:
        if not os.path.exists(note) and os.path.isdir(os.path.dirname(note)):      # первый запуск: заметка-образец
            import datetime
            open(note, "w", encoding="utf-8").write(TEMPLATE % datetime.date.today().isoformat())
        data["days"] = parse(open(note, encoding="utf-8").read())
    except FileNotFoundError:
        data["error"] = "Заметка с расписанием не найдена. Выбери её в настройках виджета."
    except Exception as e:
        data["error"] = "Не удалось прочитать расписание: %s" % e
    tmp = OUT + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    return data


if __name__ == "__main__":
    d = sync()
    if sys.stdout:
        print({k: len(v) for k, v in d["days"].items()}, d["error"])
