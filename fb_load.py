"""
Carga histórica de Facebook (publicaciones, reels y videos) -> SQLite + CSV.

Las historias se abandonaron: su código y datos están en historias_abandonado/.

Credenciales: auth.json con {"page_token": "EAA..."}  (o FB_PAGE_TOKEN).

Tablas (mismo esquema que ig_load.py):
  posts(id PK, permalink, status_type, tipo, timestamp_utc, fecha_local, texto)
  metricas(post_id, captured_at, metric, value)      -> una captura por fecha, no se sobrescribe
  errores(post_id, captured_at, mensaje)
tipo: foto | reel | video | otro

Uso:
  python fb_load.py --start 2026-10-01 --end 2026-11-15
Fechas en hora de Colombia (UTC-5), extremos incluidos. Se procesa día por día.
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

API = "https://graph.facebook.com/v23.0"
PAGE = "127926969701"
TZ = timezone(timedelta(hours=-5))
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from carga_lock import adquirir  # noqa: E402

POST_METRICS = ("post_media_view", "post_total_media_view_unique", "post_clicks",
                "post_reactions_by_type_total", "post_video_views")

# nombre de métrica -> columna del CSV
POST_COLS = {"post_media_view": "vistas", "post_total_media_view_unique": "alcance",
             "shares": "compartidos", "post_clicks": "clics", "reacciones_total": "reacciones",
             "post_video_views": "vistas_video"}


USO = [0]  # última cuota observada (%)


def token():
    t = os.getenv("FB_PAGE_TOKEN")
    p = HERE / "auth.json"
    if not t and p.exists():
        t = json.loads(p.read_text(encoding="utf-8")).get("page_token")
    if not t:
        sys.exit("Falta page_token en auth.json")
    return t


def call(s, url, params, retries=6):
    """GET con reintentos ante límites de ritmo y reducción de 'limit' si Meta pide menos datos."""
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=90)
            j = r.json()
        except (requests.RequestException, ValueError):
            time.sleep(2 ** i)
            continue
        # Control preventivo: pausa si la cuota de la app o de la página supera ~60%
        try:
            u = 0
            app = json.loads(r.headers.get("x-app-usage", "{}"))
            u = max([u] + [v for v in app.values() if isinstance(v, (int, float))])
            bu = json.loads(r.headers.get("x-business-use-case-usage", "{}"))
            u = max([u] + [e[k] for lst in bu.values() for e in lst
                           for k in ("call_count", "total_cputime", "total_time")])
            USO[0] = u
            if u >= 85:  # freno de seguridad; el corte normal lo decide main() con --parar-en
                print(f"  uso de cuota {u}%, pausa 60s", file=sys.stderr, flush=True)
                time.sleep(60)
        except (ValueError, KeyError, TypeError):
            pass
        err = j.get("error")
        if not err:
            return j
        msg = err.get("message", "")
        if "reduce the amount of data" in msg and params and int(params.get("limit", 0)) > 5:
            params["limit"] = max(5, int(params["limit"]) // 2)
            continue
        if err.get("code") in (1, 2, 4, 17, 32, 613):
            wait = 30 * (i + 1)
            print(f"  límite/transitorio (code {err['code']}), espero {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        return j
    return {"error": {"message": "reintentos agotados", "code": -1}}


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY, permalink TEXT, status_type TEXT, tipo TEXT,
      timestamp_utc TEXT, fecha_local TEXT, texto TEXT);
    CREATE TABLE IF NOT EXISTS metricas(post_id TEXT, captured_at TEXT, metric TEXT, value REAL,
      PRIMARY KEY(post_id, captured_at, metric));
    CREATE TABLE IF NOT EXISTS errores(post_id TEXT, captured_at TEXT, mensaje TEXT);
    """)
    return db


def day_window(d):
    a = datetime(d.year, d.month, d.day, tzinfo=TZ)
    return int(a.timestamp()), int((a + timedelta(days=1)).timestamp())


def paged(s, url, params):
    out = []
    while url:
        j = call(s, url, params)
        if "error" in j:
            raise RuntimeError(j["error"].get("message"))
        out += j.get("data", [])
        url, params = j.get("paging", {}).get("next"), None
    return out


def save_metrics(db, pid, now, ins, extra=None):
    """ins: lista [{name, values:[{value}]}] de la expansión insights."""
    n = 0
    data = (ins or {}).get("data", [])
    # Meta puede devolver la misma métrica con varios periodos (lifetime + day). Solo vale el acumulado.
    has_lifetime = {m["name"] for m in data if m.get("period") == "lifetime"}
    for m in data:
        if m["name"] in has_lifetime and m.get("period") != "lifetime":
            continue
        v = m["values"][0]["value"] if m.get("values") else None
        name = m["name"].lower()
        if isinstance(v, dict):  # p. ej. reacciones por tipo
            for k, x in v.items():
                db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)", (pid, now, f"reaccion_{k}", x))
            db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)",
                       (pid, now, "reacciones_total", sum(v.values())))
            n += 1
        elif v is not None:
            db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)", (pid, now, name, v))
            n += 1
    for k, v in (extra or {}).items():
        db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)", (pid, now, k, v))
    return n


def load_posts(s, db, tk, d, now):
    since, until = day_window(d)
    fields = ("id,permalink_url,status_type,created_time,message,shares,"
              "insights.metric(" + ",".join(POST_METRICS) + ")")
    items = paged(s, f"{API}/{PAGE}/published_posts",
                  {"fields": fields, "limit": 25, "since": since, "until": until, "access_token": tk})
    for p in items:
        link = p.get("permalink_url") or ""
        tipo = "reel" if "/reel/" in link else {"added_photos": "foto", "added_video": "video"}.get(
            p.get("status_type"), "otro")
        ts = datetime.fromisoformat(p["created_time"].replace("+0000", "+00:00"))
        db.execute("INSERT OR REPLACE INTO posts VALUES(?,?,?,?,?,?,?)", (
            p["id"], link, p.get("status_type"), tipo, ts.isoformat(),
            ts.astimezone(TZ).date().isoformat(), p.get("message")))
        got = save_metrics(db, p["id"], now, p.get("insights"),
                           {"shares": p["shares"]["count"]} if p.get("shares") else {"shares": 0})
        if not got:
            db.execute("INSERT INTO errores VALUES(?,?,?)", (p["id"], now, "sin métricas en insights"))
    return len(items)


def export_csv(db, path, tipos, cols):
    names = list(dict.fromkeys(cols.values()))
    sel = ",".join(
        f"MAX(CASE WHEN m.metric='{k}' THEN m.value END)" for k in dict.fromkeys(cols))
    # varias métricas pueden mapear a la misma columna: se toma la primera disponible
    rows = db.execute(f"""
      SELECT p.id, p.permalink, p.tipo, p.status_type, p.timestamp_utc, p.fecha_local, {sel}
      FROM posts p LEFT JOIN metricas m ON m.post_id=p.id AND m.captured_at=(
           SELECT MAX(captured_at) FROM metricas WHERE post_id=p.id)
      WHERE p.tipo IN ({",".join("?" * len(tipos))}) GROUP BY p.id ORDER BY p.timestamp_utc""", tipos).fetchall()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "permalink", "tipo", "status_type", "timestamp_utc", "fecha_local"] + list(cols.values()))
        w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01")
    ap.add_argument("--end", default="2026-11-15")
    ap.add_argument("--parar-en", type=int, default=0, help="termina limpio al cierre de un día si la cuota >= N%%")
    ap.add_argument("--db", default=str(HERE / "fb_history.db"))
    a = ap.parse_args()
    adquirir("fb_load")
    tk, s, db = token(), requests.Session(), init_db(a.db)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    d, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    tp = 0
    while d <= end:
        np_ = load_posts(s, db, tk, d, now)
        db.commit()
        tp += np_
        print(f"{d}: {np_} posts/reels | cuota {USO[0]}%", flush=True)
        d += timedelta(days=1)
        if a.parar_en and USO[0] >= a.parar_en and d <= end:
            print(f"PARADA: cuota {USO[0]}% >= {a.parar_en}%. Siguiente día pendiente: {d}", flush=True)
            break
    n1 = export_csv(db, HERE / "fb_publicaciones.csv", ["foto", "reel", "video", "otro"], POST_COLS)
    err = db.execute("SELECT COUNT(*) FROM errores WHERE captured_at=?", (now,)).fetchone()[0]
    print(f"Listo: {tp} posts/reels | CSV: {n1} filas | sin métricas: {err}")


if __name__ == "__main__":
    main()
