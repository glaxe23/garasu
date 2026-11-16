"""Свернуть/вернуть все окна (то же, что Win+D), быстро."""
import ctypes, time
k = ctypes.windll.user32.keybd_event
k(0x5B, 0, 0, 0); k(0x44, 0, 0, 0); k(0x44, 0, 2, 0); k(0x5B, 0, 2, 0)
