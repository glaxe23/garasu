"""Календарь Garasu с заметками. Открывается кликом по часам на панели.
Левый клик по числу - показать заметку этого дня. Правый клик по числу - написать или изменить заметку
(Enter - сохранить, пустая строка - удалить, Esc - отмена). Дни с заметками отмечены точкой.
Стрелки ‹ › листают месяцы. С клавиатуры: стрелки - день, PageUp/PageDown - месяц,
Home - сегодня, Enter - заметка выбранного дня. Закрыть: Esc, клик мимо или повторный клик по часам.
Заметки лежат в calendar_notes.json рядом с этим файлом."""
import os, sys, json, ctypes, calendar, datetime
from ctypes import wintypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

TITLE = "Ryoku Calendar"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
old = u.FindWindowW(None, TITLE)
if old:
    u.PostMessageW(old, 0x0010, 0, 0)
    sys.exit()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk

here = os.path.dirname(os.path.abspath(__file__))
# заметки лежат рядом с виджетами, чтобы их показывал и виджет «Календарь» на обоях
NOTES = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "calendar_notes.json")
_old = os.path.join(here, "calendar_notes.json")
if not os.path.exists(NOTES) and os.path.exists(_old):
    open(NOTES, "w", encoding="utf-8").write(open(_old, encoding="utf-8").read())
ZTHEME = os.path.join(os.path.expanduser("~"), ".glzr", "zebar", "ryoku", "theme.json")
import fonts                              # на Windows 10 шрифты Windows 11 подменяются
FONT = fonts.UI
c = {"pill": "#0c080a", "fg": "#f7e8ed", "muted": "#8d7e84", "accent": "#eeb7d0"}
try:
    c.update(json.load(open(ZTHEME, encoding="utf-8")))
except Exception:
    pass
BG, FG, MUTED, ACC = c["pill"], c["fg"], c["muted"], c["accent"]
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def load_notes():
    try:
        return json.load(open(NOTES, encoding="utf-8"))
    except Exception:
        return {}


notes = load_notes()
today = datetime.date.today()
selected = [today]
OPEN_EDIT = False
if len(sys.argv) > 1:                       # запуск из виджета: сразу открыть заметку этой даты
    try:
        selected = [datetime.date.fromisoformat(sys.argv[1])]
        OPEN_EDIT = True
    except ValueError:
        pass
view = [selected[0].year, selected[0].month]
cells = []                      # (x1, y1, x2, y2, date)

W, H = 580, 318
GX, GY, CW, CH = 262, 78, 43, 32   # сетка: левый верхний угол и размер ячейки
win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.94)
win.configure(bg=BG)
SW = win.winfo_screenwidth()
win.geometry("%dx%d+%d+%d" % (W, H, (SW - W) // 2, 50))
cv = tk.Canvas(win, width=W, height=H, bg=BG, highlightthickness=0, bd=0)
cv.pack()
entry = tk.Entry(win, font=(FONT, 10), bg="#000000", fg=FG, insertbackground=FG, relief="flat",
                 highlightthickness=1, highlightbackground=ACC, highlightcolor=ACC)


def draw():
    cv.delete("all")
    cells.clear()
    cv.create_oval(-40, -40, -20, -20, fill=BG, outline="", tags="hov")   # подсветка дня под мышкой, лежит ниже всего
    # слева: сегодняшний день крупно
    cv.create_text(126, 46, text=DAYS[today.weekday()], font=(FONT, 13, "bold"), fill=FG)
    cv.create_text(126, 70, text=MONTHS_GEN[today.month - 1], font=(FONT, 12), fill=FG)
    cv.create_text(126, 92, text=str(today.year), font=(FONT, 12), fill=MUTED)
    cv.create_text(126, 158, text=str(today.day), font=(FONT, 62, "bold"), fill=FG)
    cv.create_text(126, 226, text="Неделя %d" % today.isocalendar()[1], font=(FONT, 9), fill=MUTED)
    cv.create_line(252, 26, 252, 250, fill="#ffffff", stipple="gray25")
    # справа: месяц с листанием
    y, m = view
    cv.create_text(GX + CW * 3.5, 30, text="%s %d" % (MONTHS[m - 1], y), font=(FONT, 11, "bold"), fill=FG)
    cv.create_text(GX + 14, 30, text="‹", font=(FONT, 16, "bold"), fill=ACC, tags="prev")
    cv.create_text(GX + CW * 7 - 14, 30, text="›", font=(FONT, 16, "bold"), fill=ACC, tags="next")
    for i, s in enumerate(SHORT):
        cv.create_text(GX + CW * i + CW / 2, 60, text=s, font=(FONT, 9), fill=MUTED)
    for r, week in enumerate(calendar.Calendar(0).monthdatescalendar(y, m)):
        for i, d in enumerate(week):
            x, yy = GX + CW * i, GY + CH * r
            cx, cy = x + CW / 2, yy + CH / 2
            color = FG if d.month == m else MUTED
            if d == today:
                cv.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, fill=ACC, outline="")
                color = BG
            elif d == selected[0]:
                cv.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, outline=ACC, width=1)
            cv.create_text(cx, cy - 1, text=str(d.day), font=(FONT, 10, "bold" if d == today else "normal"), fill=color)
            if notes.get(d.isoformat()):
                cv.create_oval(cx - 2, cy + 9, cx + 2, cy + 13, fill=BG if d == today else ACC, outline="")
            cells.append((x, yy, x + CW, yy + CH, d))
    if hov["d"]:
        put_hover(hov["d"], hov["k"])
    # внизу: заметка выбранного дня
    cv.create_line(24, 272, W - 24, 272, fill="#ffffff", stipple="gray25")
    d = selected[0]
    note = notes.get(d.isoformat(), "")
    head = "%d %s" % (d.day, MONTHS_GEN[d.month - 1])
    cv.create_text(28, 294, anchor="w", text=head, font=(FONT, 10, "bold"), fill=ACC)
    cv.create_text(130, 294, anchor="w", width=W - 160, font=(FONT, 10), fill=FG if note else MUTED,
                   text=note if note else "нет заметки. Enter или правый клик по числу - написать")


def cell_at(e):
    return next((d for x1, y1, x2, y2, d in cells if x1 <= e.x < x2 and y1 <= e.y < y2), None)


# ---------- подсветка при наведении: под днём плавно проявляется кружок цвета темы
hov = {"d": None, "k": 0.0, "job": None}


def _mix(a, b, t):
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def put_hover(d, k):
    cell = next((c for c in cells if c[4] == d), None)
    if not cell:
        return
    cx, cy = (cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2
    cv.coords("hov", cx - 14, cy - 14, cx + 14, cy + 14)
    cv.itemconfigure("hov", fill=_mix(BG, ACC, 0.24 * k))


def hover(e):
    d = cell_at(e)
    over_arrow = any(t in ("prev", "next") for i in cv.find_overlapping(e.x - 6, e.y - 6, e.x + 6, e.y + 6)
                     for t in cv.gettags(i))
    cv.configure(cursor="hand2" if d or over_arrow else "")
    if d == hov["d"]:
        return
    hov["d"], hov["k"] = d, 0.0
    if hov["job"]:
        cv.after_cancel(hov["job"])
        hov["job"] = None
    if not d:
        cv.coords("hov", -40, -40, -20, -20)
        return

    def step():                                  # 6 кадров по 16 мс: быстро, но без рывка
        hov["k"] = min(1.0, hov["k"] + 1 / 6)
        put_hover(d, 1 - (1 - hov["k"]) ** 2)
        hov["job"] = cv.after(16, step) if hov["k"] < 1 else None
    step()


def unhover(e):
    hover(type("E", (), {"x": -100, "y": -100})())


def shift(n):
    m = view[1] - 1 + n
    view[0] += m // 12
    view[1] = m % 12 + 1
    draw()


def click(e):
    hide_entry()
    if 16 <= e.y <= 44 and GX <= e.x <= GX + 30:
        return shift(-1)
    if 16 <= e.y <= 44 and GX + CW * 7 - 30 <= e.x <= GX + CW * 7:
        return shift(1)
    d = cell_at(e)
    if d:
        selected[0] = d
        draw()


def edit(e):
    d = cell_at(e)
    if d:
        edit_date(d)


def edit_date(d):
    selected[0] = d
    draw()
    entry.delete(0, "end")
    entry.insert(0, notes.get(d.isoformat(), ""))
    entry.place(x=126, y=281, width=W - 152, height=26)
    entry.focus_force()
    entry.icursor("end")


def hide_entry():
    entry.place_forget()


def save(e=None):
    text = entry.get().strip()
    key = selected[0].isoformat()
    if text:
        notes[key] = text
    else:
        notes.pop(key, None)
    json.dump(notes, open(NOTES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hide_entry()
    draw()
    win.focus_force()


def move(days=0, months=0):
    """Клавиатура: стрелки двигают выбранный день, PageUp/PageDown листают месяц, Home - сегодня."""
    if entry.winfo_ismapped():
        return
    d = selected[0]
    if months:
        m = d.month - 1 + months
        y, m = d.year + m // 12, m % 12 + 1
        d = d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))
    elif days is None:
        d = today
    else:
        d += datetime.timedelta(days=days)
    selected[0] = d
    view[:] = [d.year, d.month]
    draw()


def escape(e):
    if entry.winfo_ismapped():
        hide_entry()
        win.focus_force()
    else:
        win.destroy()


cv.bind("<Motion>", hover)
cv.bind("<Leave>", unhover)
cv.bind("<Button-1>", click)
cv.bind("<Button-3>", edit)
cv.bind("<MouseWheel>", lambda e: shift(-1 if e.delta > 0 else 1))
entry.bind("<Return>", lambda e: (save(), "break")[1])   # "break": чтобы Enter окна не открыл поле снова
win.bind("<Escape>", escape)
for key, args in (("Left", (-1,)), ("Right", (1,)), ("Up", (-7,)), ("Down", (7,)), ("Home", (None,))):
    win.bind("<%s>" % key, lambda e, a=args: move(*a))
win.bind("<Prior>", lambda e: move(months=-1))
win.bind("<Next>", lambda e: move(months=1))
win.bind("<Return>", lambda e: None if entry.winfo_ismapped() else edit_date(selected[0]))
win.bind("<FocusOut>", lambda e: win.after(150, lambda: win.focus_displayof() is None and win.destroy()))
draw()
win.update_idletasks()
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.after(80, lambda: (win.lift(), win.focus_force()))
if OPEN_EDIT:
    win.after(250, lambda: edit_date(selected[0]))
ui.motion(win)                   # плавное появление и закрытие
win.mainloop()
