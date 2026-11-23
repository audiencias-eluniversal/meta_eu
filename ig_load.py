"""
Carga histórica de publicaciones y reels de Instagram (Graph API) -> SQLite + CSV local.

Credenciales: auth.json con {"ig_token": "EAA...", "ig_user_id": "..."}  (o FB_IG_TOKEN / FB_IG_USER_ID).

Tablas:
  posts(id PK, permalink, media_type, media_product_type, tipo, timestamp_utc, fecha_local, caption)
  metricas(post_id, captured_at, metric, value, PRIMARY KEY(post_id, captured_at, metric))
    -> una fila por captura: permite ver cómo evolucionan las cifras en cargas semanales.

Uso:
  python ig_load.py --start 2026-10-01 --end 2026-11-15
Fechas interpretadas en hora de Colombia (UTC-5), ambos extremos incluidos.
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
TZ = timezone(timedelta(hours=-5))  # America/Bogota
METRICS = ("reach", "views", "saved", "shares")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from carga_lock import adquirir  # noqa: E402


def creds():
    t, u = os.getenv("FB_IG_TOKEN"), os.getenv("FB_IG_USER_ID")
    p = HERE / "auth.json"
    if p.exists():
        a = json.loads(p.read_text(encoding="utf-8"))
        t, u = t or a.get("ig_token"), u or a.get("ig_user_id")
    if not (t and u):
        sys.exit("Faltan ig_token / ig_user_id en auth.json")
    return t, u


def call(session, url, params, retries=5):
    """GET con reintentos ante límites de ritmo (códigos 4, 17, 32, 613) o fallos de red."""
    for i in range(retries):
        try:
            r = session.get(url, params=params, timeout=60)
            j = r.json()
        except (requests.RequestException, ValueError):
            time.sleep(2 ** i)
            continue
        err = j.get("error")
        if err and err.get("code") in (1, 2, 4, 17, 32, 613):
            wait = 30 * (i + 1)
            print(f"  límite/transitorio (code {err['code']}), espero {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        return j
    return {"error": {"message": "reintentos agotados", "code": -1}}


def tipo(product, media):
    if product == "REELS":
        return "reel"
    if product == "STORY":
        return "historia"
    return {"CAROUSEL_ALBUM": "carrusel", "IMAGE": "imagen", "VIDEO": "video"}.get(media, media.lower())


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS posts(
      id TEXT PRIMARY KEY, permalink TEXT, media_type TEXT, media_product_type TEXT,
      tipo TEXT, timestamp_utc TEXT, fecha_local TEXT, caption TEXT);
    CREATE TABLE IF NOT EXISTS metricas(
      post_id TEXT, captured_at TEXT, metric TEXT, value REAL,
      PRIMARY KEY(post_id, captured_at, metric));
    CREATE TABLE IF NOT EXISTS errores(post_id TEXT, captured_at TEXT, mensaje TEXT);
    """)
    return db


def list_media(session, token, ig, d0, d1):
    """Publicaciones con timestamp en [d0, d1] (fechas locales Bogotá, inclusive)."""
    since = int(datetime(d0.year, d0.month, d0.day, tzinfo=TZ).timestamp())
    until = int((datetime(d1.year, d1.month, d1.day, tzinfo=TZ) + timedelta(days=1)).timestamp())
    url = f"{API}/{ig}/media"
    params = {"fields": "id,permalink,media_type,media_product_type,timestamp,caption",
              "limit": 100, "since": since, "until": until, "access_token": token}
    out = []
    while url:
        j = call(session, url, params)
        if "error" in j:
            raise RuntimeError(j["error"].get("message"))
        out += j.get("data", [])
        url, params = j.get("paging", {}).get("next"), None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01")
    ap.add_argument("--end", default="2026-11-15")
    ap.add_argument("--db", default=str(HERE / "ig_history.db"))
    a = ap.parse_args()
    adquirir("ig_load")
    token, ig = creds()
    d0, d1 = date.fromisoformat(a.start), date.fromisoformat(a.end)
    s, db = requests.Session(), init_db(a.db)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1) Listar por ventanas de 7 días
    posts, cur = {}, d0
    while cur <= d1:
        end = min(cur + timedelta(days=6), d1)
        items = list_media(s, token, ig, cur, end)
        for m in items:
            posts[m["id"]] = m
        print(f"{cur} -> {end}: {len(items)} publicaciones")
        cur = end + timedelta(days=1)

    for m in posts.values():
        ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        db.execute("INSERT OR REPLACE INTO posts VALUES(?,?,?,?,?,?,?,?)", (
            m["id"], m.get("permalink"), m["media_type"], m["media_product_type"],
            tipo(m["media_product_type"], m["media_type"]), ts.isoformat(),
            ts.astimezone(TZ).date().isoformat(), m.get("caption")))
    db.commit()

    # 2) Métricas (una llamada por publicación, las 4 métricas juntas)
    ok = fail = 0
    for n, pid in enumerate(posts, 1):
        j = call(s, f"{API}/{pid}/insights", {"metric": ",".join(METRICS), "access_token": token})
        if "error" in j:
            # si falla por una métrica no soportada, reintenta métrica a métrica
            got = False
            for met in METRICS:
                jm = call(s, f"{API}/{pid}/insights", {"metric": met, "access_token": token})
                if "data" in jm and jm["data"]:
                    v = jm["data"][0]["values"][0]["value"]
                    db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)", (pid, now, met, v))
                    got = True
                else:
                    db.execute("INSERT INTO errores VALUES(?,?,?)",
                               (pid, now, f"{met}: {jm.get('error', {}).get('message', 'vacío')[:120]}"))
            ok, fail = (ok + 1, fail) if got else (ok, fail + 1)
        else:
            for d in j["data"]:
                db.execute("INSERT OR REPLACE INTO metricas VALUES(?,?,?,?)",
                           (pid, now, d["name"], d["values"][0]["value"]))
            ok += 1
        if n % 50 == 0:
            db.commit()
            print(f"  métricas: {n}/{len(posts)}")
    db.commit()

    # 3) CSV listo para análisis (última captura por publicación)
    csv_path = HERE / "ig_publicaciones.csv"
    rows = db.execute("""
      SELECT p.id, p.permalink, p.tipo, p.media_product_type, p.media_type, p.timestamp_utc, p.fecha_local,
             MAX(CASE WHEN m.metric='reach'  THEN m.value END),
             MAX(CASE WHEN m.metric='views'  THEN m.value END),
             MAX(CASE WHEN m.metric='saved'  THEN m.value END),
             MAX(CASE WHEN m.metric='shares' THEN m.value END)
      FROM posts p LEFT JOIN metricas m ON m.post_id=p.id AND m.captured_at=(
           SELECT MAX(captured_at) FROM metricas WHERE post_id=p.id)
      GROUP BY p.id ORDER BY p.timestamp_utc""").fetchall()
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "permalink", "tipo", "media_product_type", "media_type",
                    "timestamp_utc", "fecha_local", "alcance", "vistas", "guardados", "compartidos"])
        w.writerows(rows)
    print(f"Listo: {len(posts)} publicaciones | métricas ok: {ok}, con fallos: {fail} | {csv_path}")


if __name__ == "__main__":
    main()
