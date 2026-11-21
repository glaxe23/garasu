"""Виджет таймера сообщает заморозке (freeze.pyw), когда кончится отрезок и играет ли фон.
Вызов: freeze_note.pyw <running 0/1> <endsAt, мс> <phase> <amb>"""
import os, sys, json

here = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:] + ["", "", "", ""]
note = {"running": a[0] == "1", "endsAt": float(a[1] or 0), "phase": a[2], "amb": a[3] or "off"}
tmp = os.path.join(here, "freeze_note.json.tmp")
json.dump(note, open(tmp, "w", encoding="utf-8"))
os.replace(tmp, os.path.join(here, "freeze_note.json"))
