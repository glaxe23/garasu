"""Обнаружение Wallpaper Engine в текущем сеансе Windows."""

import ctypes
import os
from ctypes import wintypes


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("session_id", wintypes.DWORD),
        ("process_id", wintypes.DWORD),
        ("name", wintypes.LPWSTR),
        ("user_sid", ctypes.c_void_p),
    ]


_wts = ctypes.windll.wtsapi32
_enumerate = _wts.WTSEnumerateProcessesW
_enumerate.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(ctypes.POINTER(_ProcessInfo)), ctypes.POINTER(wintypes.DWORD),
]
_enumerate.restype = wintypes.BOOL
_free = _wts.WTSFreeMemory
_free.argtypes = [ctypes.c_void_p]
_free.restype = None

_session_for_pid = ctypes.windll.kernel32.ProcessIdToSessionId
_session_for_pid.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
_session_for_pid.restype = wintypes.BOOL
_engine_names = {"wallpaper32.exe", "wallpaper64.exe"}


def is_running():
    session = wintypes.DWORD()
    if not _session_for_pid(os.getpid(), ctypes.byref(session)):
        return False
    processes = ctypes.POINTER(_ProcessInfo)()
    count = wintypes.DWORD()
    if not _enumerate(None, 0, 1, ctypes.byref(processes), ctypes.byref(count)):
        return False
    try:
        return any(
            process.session_id == session.value and (process.name or "").lower() in _engine_names
            for process in processes[:count.value]
        )
    finally:
        _free(processes)
