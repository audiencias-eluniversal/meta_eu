# meta_eu

Histórico local de publicaciones, reels e historias de **Facebook** (página El Universal) e **Instagram** (@eluniversalctg), con sus métricas. Los datos se descargan de la Graph API oficial de Meta y se guardan en bases SQLite.

## Qué incluye

| Archivo | Función |
|---|---|
| `fb_load.py` | Carga publicaciones, reels, videos e historias de Facebook |
| `ig_load.py` | Carga publicaciones y reels de Instagram |
| `cobertura.py` | Muestra qué días y fuentes ya están cargados (no llama a Meta) |
| `carga_lock.py` | Evita que corran dos cargas a la vez |
| `fix_alcance_fb.py` | Corrección puntual ya ejecutada; no volver a correr |

## Uso básico

```
python fb_load.py --start 2026-11-01 --end 2026-11-15 --solo posts
python ig_load.py --start 2026-11-16 --end 2026-11-21
python cobertura.py
```

Ejecutar desde esta carpeta, con un solo proceso a la vez.

## Datos y credenciales (no versionados)

El repositorio solo contiene el código. Quedan fuera de git, y hay que copiarlos aparte a otro equipo:

- `fb_history.db` e `ig_history.db`: bases con todo el histórico (cada medición se guarda como una fila nueva).
- `*.csv`: vista plana de la última captura de cada publicación; se regeneran en cada carga.
- `*.log` y copias `fb_history.backup_*.db`.
- `auth.json`: tokens y credenciales de la app de Meta.

## Más información

Detalles del modelo de datos, métricas, límites de cuota, decisiones técnicas y pendientes en [`DOCUMENTACION.md`](DOCUMENTACION.md).
