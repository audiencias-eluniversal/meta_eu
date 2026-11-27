# ⚠️ PROYECTO ABANDONADO: historias de Facebook e Instagram

**Estado: abandonado el 25/11/2026.** Las historias quedaron fuera del alcance de `meta_eu`, que ahora trabaja solo con **publicaciones, reels y videos**. Esta carpeta conserva todo lo que se había hecho, por si se retoma.

Nada de esta carpeta es usado por los scripts del proyecto. No hay que mantenerla ni correrla.

## Qué hay aquí

| Archivo | Contenido |
|---|---|
| `fb_historias.db` | Base SQLite con las historias de Facebook que se alcanzaron a cargar: 2.446 historias, 14.676 filas de métricas. Mismo esquema que `fb_history.db` |
| `fb_historias.csv` | Vista plana de esas historias (última captura por historia) |
| `fb_load_historias.py` | Copia congelada de `fb_load.py` **con** la lógica de historias (`load_stories`, `--solo historias`) tal como estaba al abandonar |
| `cobertura_con_historias.py` | Copia congelada de `cobertura.py` con las filas de historias |
| `fb_history.backup_antes_historias_19_31oct.db` | Copia previa a la carga de historias del 19-31 oct |
| `fb_history.backup_antes_historias_20oct.db` | Copia previa a la carga de historias del 20 oct en adelante |
| `fb_history.backup_antes_de_separar_historias.db` | Copia completa de `fb_history.db` justo antes de sacar las historias. Permite deshacer la separación |

## Estado de los datos al abandonar

- **Facebook:** historias del **1 al 21 de octubre de 2026** (21 de 46 días del periodo 1-oct → 15-nov). **Faltan del 22-oct al 15-nov.**
- **Instagram:** nunca se cargó nada. La API solo muestra las historias de las últimas 24 horas y no hay archivo.
- Métricas de historias de Facebook: `story_media_view`, `story_total_media_view_unique`, `story_interaction`, `pages_fb_story_replies`, `pages_fb_story_shares`, `pages_fb_story_thread_lightweight_reactions`.
- Fechas locales en hora de Colombia (UTC-5).

## Por qué quedó difícil (hallazgos técnicos)

1. **Cuota de la app.** Las historias consumen el medidor de la app (`x-app-usage`), mucho más exigente que el de la página que usan los posts. Una carga de historias llegó al 87 % y el error 4 bloquea incluso lecturas simples. Mitigación usada: lotes de 10 historias, pausa de 120 s por encima del 60 % y un solo proceso a la vez. Opción que quedó pendiente: pedir 3 métricas por historia en vez de 6 para reducir el costo a la mitad.
2. **Facebook solo conserva ~80-90 días de historias archivadas** (`status=ARCHIVED` con `since/until` en epoch). Lo que no se cargó vence: las del 22-oct empezarían a perderse hacia mediados o finales de enero de 2027.
3. **Instagram no tiene archivo de historias.** Un histórico solo se construye con una captura **diaria** desde el momento en que se empiece. Esa captura diaria nunca se escribió.

## Cómo retomarlo

1. Copiar `fb_load_historias.py` a la raíz del proyecto (necesita `carga_lock.py` y `auth.json`, que viven allí).
2. Correrlo contra la base de esta carpeta, por ejemplo:
   `python fb_load_historias.py --start 2026-10-22 --end 2026-11-15 --solo historias --db historias_abandonado/fb_historias.db`
3. Correr una sola carga a la vez y vigilar la cuota (ver punto 1).
4. Revisar el vencimiento del `page_token` (`data_access_expires_at`: 19/02/2027).

Nota: `fb_load_historias.py` escribe sus CSV en la carpeta donde esté el script, y sus datos por defecto en `fb_history.db`. Por eso conviene pasar `--db` como arriba.
