"""Открывает программу, файл или папку для виджета «Ярлыки»:   pythonw launch.pyw <путь>"""
import os, sys

if len(sys.argv) > 1:
    try:
        os.startfile(sys.argv[1])
    except OSError:
        pass
