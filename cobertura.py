"""Tabla de cobertura: qué hay guardado, por día y fuente, en fb_history.db e ig_history.db.
Solo lee las bases locales (no llama a Meta).

Uso:  python cobertura.py [--start 2026-10-01] [--end 2026-11-15] [--detalle]
Escribe también cobertura.csv (una fila por día).
"""
import argparse
import csv
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
FUENTES = [  # (columna, base, filtro SQL sobre posts.tipo)
    ("FB posts/reels", "fb_history.db", "1=1"),
    ("IG posts/reels", "ig_history.db", "1=1"),
]


def conteos(base, filtro):
    p = HERE / base
    if not p.exists():
        return {}
    db = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    return dict(db.execute(f"SELECT fecha_local, COUNT(*) FROM posts WHERE {filtro} GROUP BY 1").fetchall())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01")
    ap.add_argument("--end", default="2026-11-15")
    ap.add_argument("--detalle", action="store_true", help="imprime todos los días")
    a = ap.parse_args()
    d0, d1 = date.fromisoformat(a.start), date.fromisoformat(a.end)
    dias = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
    datos = {n: conteos(b, f) for n, b, f in FUENTES}

    filas = [[d.isoformat()] + [datos[n].get(d.isoformat(), 0) for n, _, _ in FUENTES] for d in dias]
    cols = ["fecha"] + [n for n, _, _ in FUENTES]
    with open(HERE / "cobertura.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(filas)

    if a.detalle:
        print(" | ".join(f"{c:>14}" for c in cols))
        for r in filas:
            print(" | ".join(f"{('—' if v == 0 else v):>14}" for v in r))
        print()

    print(f"Cobertura {a.start}  a  {a.end} ({len(dias)} días)\n")
    print(f"{'Fuente':<16}{'Días con datos':>16}{'Registros':>11}   Faltan")
    for i, (n, _, _) in enumerate(FUENTES, start=1):
        falt = [r[0] for r in filas if r[i] == 0]
        # comprime los días faltantes en rangos
        rangos, ini, prev = [], None, None
        for f in falt:
            fd = date.fromisoformat(f)
            if ini is None:
                ini = prev = fd
            elif (fd - prev).days == 1:
                prev = fd
            else:
                rangos.append((ini, prev)); ini = prev = fd
        if ini:
            rangos.append((ini, prev))
        txt = ", ".join(f"{x:%d-%b}" if x == y else f"{x:%d-%b} a {y:%d-%b}" for x, y in rangos) or "nada"
        print(f"{n:<16}{len(dias) - len(falt):>10}/{len(dias):<5}{sum(r[i] for r in filas):>11}   {txt}")


if __name__ == "__main__":
    main()
