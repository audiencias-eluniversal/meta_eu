"""Candado para que no corran dos cargas a la vez (evita procesos duplicados que gastan cuota y bloquean la base).

Uso: `from carga_lock import adquirir; adquirir("fb_load")` al inicio de un script.
Si otra carga sigue viva, el script termina con un aviso. Si el candado quedó huérfano
(proceso muerto o cerrado a la fuerza), se reemplaza solo.
"""
import atexit
import ctypes
import os
import sys
from pathlib import Path

LOCK = Path(__file__).with_name(".carga.lock")


def _vivo(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _leer():
    try:
        pid, quien = LOCK.read_text(encoding="utf-8").split("|", 1)
        return int(pid), quien.strip()
    except (OSError, ValueError):
        return 0, "?"


def liberar():
    try:
        if LOCK.exists() and _leer()[0] == os.getpid():
            LOCK.unlink()
    except OSError:
        pass


def adquirir(nombre):
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}|{nombre}".encode("utf-8"))
            os.close(fd)
            atexit.register(liberar)
            return
        except FileExistsError:
            pid, quien = _leer()
            if _vivo(pid):
                sys.exit(f"Ya hay una carga corriendo ({quien}, PID {pid}). No se lanza otra copia.")
            print("Candado huérfano de una ejecución anterior: se reemplaza.", file=sys.stderr)
            try:
                LOCK.unlink()
            except OSError:
                pass
    sys.exit("No se pudo adquirir el candado.")
