"""Шпаргалка по клавишам Garasu и окно «С чего начать».

  pythonw help_panel.pyw            - клавиши (открывается по Ctrl+Alt+H, повторное нажатие закрывает)
  pythonw help_panel.pyw welcome    - гайд из трёх страниц: первые шаги, где что теперь вместо привычного
                                      в Windows, клавиши (показывается один раз после установки)

Закрыть: Esc, крестик или клик мимо окна."""
import os, sys, ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

TITLE = "Ryoku Help"
WELCOME = len(sys.argv) > 1 and sys.argv[1] == "welcome"
u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
old = u.FindWindowW(None, TITLE)
if old:
    u.PostMessageW(old, 0x0010, 0, 0)
    if not WELCOME:
        sys.exit()
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
import tkinter as tk

import fonts                              # на Windows 10 шрифты Windows 11 подменяются
FONT = fonts.UI
c = ui.colors()
BG, FG, MUTED, ACC, TROUGH = c["BG"], c["FG"], c["MUTED"], c["ACC"], c["TROUGH"]

STEPS = [
    ("Темы", "кнопка с палитрой справа на верхней панели. Там же док, своя картинка и обновление."),
    ("Виджеты", "правый клик по любому виджету: можно двигать, растягивать, включать новые."),
    ("Режимы", "кнопка режима на панели: повседневный, рабочий, игровой (всё лишнее выключается)."),
    ("Поиск", "клавиша Win открывает поиск приложений."),
    ("Клавиши", "эта шпаргалка всегда под рукой: Ctrl+Alt+H."),
]
# Где теперь то, к чему привык в Windows
MOVED = [
    ("Меню «Пуск»", "клавиша Win: поиск приложений по названию"),
    ("Панель задач", "док внизу: значки открытых окон, прячется сам"),
    ("Свернуть все окна", "Win + D, как раньше, или кнопка слева в доке"),
    ("Проводник, переключение окон", "Win + E, Alt + Tab и Alt + F4 работают как раньше"),
    ("Развернуть и свернуть окно", "Win + вверх и Win + вниз, или кнопки в заголовке окна"),
    ("Параметры Windows", "Win + I, как раньше"),
    ("Обои и цвета", "кнопка с палитрой справа на верхней панели"),
    ("Громкость", "значок на панели, правый клик: громкость по приложениям"),
    ("Часы и календарь", "клик по часам на панели, там же заметки на дни"),
    ("Значки в трее", "справа на верхней панели"),
    ("Вернуть обычные окна", "Alt + Shift + P ставит плитку на паузу"),
    ("Вернуть Windows как был", "ярлык «Удалить Garasu» на рабочем столе"),
]
KEYS = [
    ("Окна", [
        ("Alt + стрелки", "перейти к соседнему окну"),
        ("Alt + Shift + стрелки", "передвинуть окно"),
        ("Alt + F", "развернуть окно и вернуть обратно"),
        ("Alt + Shift + Пробел", "окно поверх плитки (плавающее)"),
        ("Alt + M", "свернуть окно"),
        ("Alt + Shift + Q", "закрыть окно (или Alt + F4)"),
        ("Win + стрелки", "вверх: развернуть, вниз: свернуть, вбок: передвинуть"),
        ("Alt + U / P", "уже / шире"),
        ("Alt + V", "следующее окно встанет снизу, а не сбоку"),
    ]),
    ("Рабочие столы", [
        ("Alt + 1…9", "перейти на рабочий стол"),
        ("Alt + Shift + 1…9", "перенести туда окно"),
        ("Alt + S / A", "следующий и предыдущий стол"),
    ]),
    ("Оформление", [
        ("Win", "поиск приложений"),
        ("Ctrl + Alt + 1 / 2 / 3", "режим: повседневный, рабочий, игровой"),
        ("Alt + Shift + T / Y", "следующая и предыдущая тема"),
        ("Alt + Shift + P", "пауза плитки: окна ведут себя как обычно"),
        ("Ctrl + Alt + H", "эта шпаргалка"),
    ]),
    ("В панелях", [
        ("← →  или колёсико", "темы: листать карусель, Enter: применить"),
        ("стрелки, PgUp / PgDn", "календарь: дни, недели, месяцы; Enter: заметка"),
        ("1 / 2 / 3", "режимы: повседневный, рабочий, игровой"),
        ("колёсико", "микшер: громкость над строкой приложения"),
    ]),
]

win = tk.Tk()
win.title(TITLE)
win.overrideredirect(True)
win.attributes("-topmost", True)
ui.hidden(win, 0.95)
win.configure(bg=BG)
body = tk.Frame(win, bg=BG, padx=22, pady=16)
body.pack()

head = tk.Frame(body, bg=BG)
head.pack(fill="x", pady=(0, 8))
tk.Label(head, text="硝", font=(FONT, 15, "bold"), bg=BG, fg=ACC).pack(side="left")
head_title = tk.Label(head, text="  КЛАВИШИ", font=(FONT, 10, "bold"), bg=BG, fg=FG)
head_title.pack(side="left")
x = tk.Label(head, text="", font=(fonts.ICONS, 10), bg=BG, fg=MUTED, cursor="hand2", padx=8, pady=4)
x.pack(side="right")
x.bind("<Button-1>", lambda e: win.destroy())

pages = tk.Frame(body, bg=BG)
pages.pack(fill="both", expand=True)
p_start, p_moved, cols = tk.Frame(pages, bg=BG), tk.Frame(pages, bg=BG), tk.Frame(pages, bg=BG)
if WELCOME:
    tk.Label(p_start, text="Garasu установлен. Пять вещей, которые стоит знать:", font=(FONT, 10), bg=BG, fg=FG,
             anchor="w").pack(fill="x", pady=(0, 8))
    for i, (name, text) in enumerate(STEPS, 1):
        row = tk.Frame(p_start, bg=BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=str(i), font=(FONT, 10, "bold"), bg=ACC, fg=BG, width=2).pack(side="left", anchor="n")
        tk.Label(row, text=name, font=(FONT, 10, "bold"), bg=BG, fg=ACC, width=9, anchor="w").pack(side="left", padx=(10, 0), anchor="n")
        tk.Label(row, text=text, font=(FONT, 10), bg=BG, fg=FG, anchor="w", justify="left", wraplength=600).pack(side="left")
    tk.Label(p_moved, text="Привычные вещи из Windows никуда не делись. Вот где они теперь:", font=(FONT, 10), bg=BG, fg=FG,
             anchor="w").pack(fill="x", pady=(0, 8))
    for name, text in MOVED:
        row = tk.Frame(p_moved, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=name, font=(FONT, 9, "bold"), bg=TROUGH, fg=FG, padx=8, pady=2, width=28, anchor="w").pack(side="left")
        tk.Label(row, text=text, font=(FONT, 9), bg=BG, fg=MUTED, anchor="w").pack(side="left", padx=10)
left = tk.Frame(cols, bg=BG)
left.pack(side="left", anchor="n")
right = tk.Frame(cols, bg=BG)
right.pack(side="left", anchor="n", padx=(34, 0))
for (group, keys), parent in zip(KEYS, (left, right, right, right)):
    tk.Label(parent, text=group.upper(), font=(FONT, 8, "bold"), bg=BG, fg=ACC, anchor="w").pack(fill="x", pady=(8, 4))
    for key, text in keys:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=key, font=(FONT, 9, "bold"), bg=TROUGH, fg=FG, padx=8, pady=2).pack(side="left")
        tk.Label(row, text=text, font=(FONT, 9), bg=BG, fg=MUTED, anchor="w").pack(side="left", padx=10)

# страницы гайда: окно берёт размер самой большой, кнопки внизу листают
ORDER = [(p_start, "  С ЧЕГО НАЧАТЬ"), (p_moved, "  ГДЕ ЧТО ТЕПЕРЬ"), (cols, "  КЛАВИШИ")] if WELCOME else [(cols, "  КЛАВИШИ")]
page = [0]


def show_page(i):
    page[0] = i
    for fr, _t in ORDER:
        fr.pack_forget()
    ORDER[i][0].pack(fill="both", expand=True, anchor="n")
    head_title.configure(text=ORDER[i][1])
    if WELCOME:
        back.configure(fg=MUTED if i else BG)
        nxt.configure(text="Готово" if i == len(ORDER) - 1 else "Далее  ›")
        dots.configure(text="  ".join("●" if k == i else "○" for k in range(len(ORDER))))


if WELCOME:
    nav = tk.Frame(body, bg=BG)
    nav.pack(fill="x", pady=(14, 0), side="bottom")
    back = tk.Label(nav, text="‹  Назад", font=(FONT, 9, "bold"), bg=BG, fg=MUTED, cursor="hand2", padx=10, pady=5)
    back.pack(side="left")
    dots = tk.Label(nav, text="", font=(FONT, 9), bg=BG, fg=ACC)
    dots.pack(side="left", expand=True)
    nxt = tk.Label(nav, text="Далее  ›", font=(FONT, 9, "bold"), bg=ACC, fg=BG, cursor="hand2", padx=14, pady=5)
    nxt.pack(side="right")
    back.bind("<Button-1>", lambda e: page[0] and show_page(page[0] - 1))
    nxt.bind("<Button-1>", lambda e: win.destroy() if page[0] == len(ORDER) - 1 else show_page(page[0] + 1))
    win.bind("<Right>", lambda e: page[0] < len(ORDER) - 1 and show_page(page[0] + 1))
    win.bind("<Left>", lambda e: page[0] and show_page(page[0] - 1))
    sizes = []
    for i in range(len(ORDER)):                  # замер: какая страница самая большая
        show_page(i)
        win.update_idletasks()
        sizes.append((pages.winfo_reqwidth(), pages.winfo_reqheight()))
    pages.configure(width=max(s[0] for s in sizes), height=max(s[1] for s in sizes))
    pages.pack_propagate(False)
show_page(0)
win.update_idletasks()
w, h = win.winfo_reqwidth(), win.winfo_reqheight()
win.geometry("+%d+%d" % ((win.winfo_screenwidth() - w) // 2, max(40, (win.winfo_screenheight() - h) // 2)))
try:
    hwnd = wintypes.HWND(u.GetParent(win.winfo_id()) or win.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)
except Exception:
    pass
win.bind("<Escape>", lambda e: win.destroy())
def watch_focus():
    """Клик мимо окна закрывает шпаргалку. Проверка идёт по активному окну Windows: событие потери фокуса
    у окна без рамки иногда приходит ещё при открытии."""
    u.GetForegroundWindow.restype = wintypes.HWND
    mine = u.GetParent(win.winfo_id()) or win.winfo_id()
    if seen[0] and u.GetForegroundWindow() != mine:
        win.destroy()
        return
    seen[0] = seen[0] or u.GetForegroundWindow() == mine
    win.after(250, watch_focus)


seen = [False]
win.after(80, lambda: (win.lift(), win.focus_force()))
if not WELCOME:              # приветствие закрывается только крестиком или Esc
    win.after(600, watch_focus)
ui.live(win)                      # плавная подсветка кнопок и ссылок при наведении
win.mainloop()
