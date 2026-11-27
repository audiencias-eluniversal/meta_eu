# meta_eu

Histórico local de publicaciones y reels de **Facebook** (página El Universal) e **Instagram** (@eluniversalctg), con sus métricas. Los datos se descargan de la Graph API oficial de Meta y se guardan en bases SQLite.

> **Historias: proyecto abandonado.** Todo lo relativo a historias vive en [`historias_abandonado/`](historias_abandonado/README.md). No forma parte de este proyecto.

## Qué incluye

| Archivo | Función |
|---|---|
| `fb_load.py` | Carga publicaciones, reels y videos de Facebook |
| `ig_load.py` | Carga publicaciones y reels de Instagram |
| `cobertura.py` | Muestra qué días y fuentes ya están cargados (no llama a Meta) |
| `carga_lock.py` | Evita que corran dos cargas a la vez |
| `fix_alcance_fb.py` | Corrección puntual ya ejecutada; no volver a correr |
| `historias_abandonado/` | Código, datos y notas de las historias (abandonado) |

## Uso básico

```
python fb_load.py --start 2026-11-16 --end 2026-11-24
python ig_load.py --start 2026-11-16 --end 2026-11-24
python cobertura.py
```

Ejecutar desde esta carpeta, con un solo proceso a la vez.

## Datos y credenciales (no versionados)

El repositorio solo contiene el código. Quedan fuera de git, y hay que copiarlos aparte a otro equipo:

- `fb_history.db` e `ig_history.db`: bases con el histórico (cada medición se guarda como una fila nueva).
- `*.csv`: vista plana de la última captura de cada publicación; se regeneran en cada carga.
- `*.log` y copias `fb_history.backup_*.db`.
- `auth.json`: tokens y credenciales de la app de Meta.

## Más información

Detalles del modelo de datos, métricas, límites de cuota, decisiones técnicas, el plan de actualización diaria y pendientes en [`DOCUMENTACION.md`](DOCUMENTACION.md).
