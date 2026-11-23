"""Corrige el alcance (post_total_media_view_unique) de posts ya guardados con valor 0 por el bug de periodos."""
import json, sqlite3, sys, time
from pathlib import Path
import requests

HERE = Path(__file__).parent
tk = json.loads((HERE / "auth.json").read_text(encoding="utf-8"))["page_token"]
db = sqlite3.connect(HERE / "fb_history.db")
ids = [r[0] for r in db.execute("""
    SELECT p.id FROM posts p JOIN metricas m ON m.post_id=p.id AND m.metric='post_total_media_view_unique'
    WHERE p.tipo IN ('foto','reel','video','otro') AND m.value=0 AND p.fecha_local BETWEEN '2026-10-01' AND '2026-10-16'""")]
print("posts a corregir:", len(ids))
s, fixed, noval = requests.Session(), 0, 0
G = "https://graph.facebook.com/v23.0"
M = "post_total_media_view_unique"
for i in range(0, len(ids), 50):
    chunk = ids[i:i + 50]
    batch = [{"method": "GET", "relative_url": f"{pid}/insights?metric={M}"} for pid in chunk]
    for intento in range(4):
        r = s.post(G + "/", data={"access_token": tk, "batch": json.dumps(batch), "include_headers": "false"}, timeout=180)
        j = r.json()
        if isinstance(j, dict) and "error" in j:
            print("  error:", j["error"].get("code"), j["error"].get("message", "")[:100], file=sys.stderr, flush=True)
            time.sleep(30 * (intento + 1)); continue
        break
    else:
        sys.exit("abortado: Meta sigue rechazando; lo ya corregido queda guardado")
    for pid, item in zip(chunk, j):
        if not item or item.get("code") != 200:
            noval += 1; continue
        data = json.loads(item["body"]).get("data", [])
        life = [d for d in data if d["name"] == M and d.get("period") == "lifetime" and d.get("values")]
        if life:
            db.execute("UPDATE metricas SET value=? WHERE post_id=? AND metric=?", (life[0]["values"][0]["value"], pid, M)); fixed += 1
        else:
            noval += 1
    db.commit()
    print(f"  lote {i // 50 + 1}/{(len(ids) + 49) // 50}: corregidos {fixed}, sin valor {noval}", flush=True)
    time.sleep(3)
print("listo | corregidos:", fixed, "| sin valor:", noval)
