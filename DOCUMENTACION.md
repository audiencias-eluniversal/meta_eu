# Histórico de contenido y métricas de Facebook e Instagram

Descarga local de publicaciones, reels e historias de la página **El Universal** (Facebook) y la cuenta **@eluniversalctg** (Instagram) con sus métricas, más los ingresos de monetización de la página. Fuente: **Graph API oficial de Meta**. Estado actualizado el 21/11/2026.

## 1. Estado de cobertura (1-oct → 15-nov-2026)

| Fuente | Días cubiertos | Registros | Pendiente |
|---|---|---|---|
| Facebook posts y reels | 31 / 46 | 3.643 | 1 → 15 nov |
| Facebook historias | 18 / 46 | 2.048 | 19 oct → 15 nov |
| Instagram posts y reels | 46 / 46 | 635 | — |
| Instagram historias | — | — | No recuperables (ver §5) |

Se regenera en cualquier momento con `python cobertura.py [--detalle]` (lee las bases locales; no llama a Meta).

## 2. Archivos

| Archivo | Función |
|---|---|
| `fb_load.py` | Carga Facebook (posts, reels, videos, historias archivadas), día por día. `--solo posts\|historias` |
| `ig_load.py` | Carga Instagram (posts y reels), por ventanas semanales |
| `video_earnings.py` | Ingresos de monetización de la página (total y por herramienta) → `video_earnings.json` |
| `cobertura.py` | Tabla de cobertura por día y fuente → consola y `cobertura.csv` |
| `carga_lock.py` | Candado: impide que corran dos cargas a la vez |
| `fix_alcance_fb.py` | Corrección puntual ya ejecutada (ver §5.3). No volver a correr |
| `fb_history.db`, `ig_history.db` | Bases SQLite con todo el histórico |
| `fb_publicaciones.csv`, `fb_historias.csv`, `ig_publicaciones.csv` | Vista plana, una fila por publicación (última captura). Se regeneran en cada carga |
| `auth.json` | Credenciales (no versionar; ver §7) |
| `fb_history.backup_*.db` | Copias previas a operaciones delicadas; se pueden borrar tras validar |

Ejecutar con `python` normal desde esta carpeta (no con `-I`, que impide importar `carga_lock`).

## 3. Modelo de datos

Mismo esquema en ambas bases:

- **`posts`**: `id` (PK), `permalink`, `tipo` (`foto`, `reel`, `video`, `carrusel`, `imagen`, `historia`, `otro`), `timestamp_utc`, `fecha_local`, texto/tipo original de Meta.
- **`metricas`**: `post_id`, `captured_at`, `metric`, `value`. **Una fila por captura**: volver a medir un post añade filas nuevas; no sobrescribe. Así se ve la evolución y se calculan incrementos restando capturas.
- **`errores`**: publicaciones sin métricas o con fallos.

Convenciones: fechas locales en **hora de Colombia (UTC-5)**; el `id` de Facebook es `{página}_{post}`; los CSV muestran la captura más reciente de cada post.

**Métricas**

| Plataforma | Métricas |
|---|---|
| Facebook posts | `post_media_view` (vistas), `post_total_media_view_unique` (alcance), `post_clicks`, reacciones (`reacciones_total` y `reaccion_*`), `post_video_views`, `shares` (campo del post) |
| Facebook historias | `story_media_view`, `story_total_media_view_unique`, `story_interaction`, `pages_fb_story_replies`, `pages_fb_story_shares`, `pages_fb_story_thread_lightweight_reactions` |
| Instagram | `reach`, `views`, `saved`, `shares` (`saved` no existe para historias) |

## 4. Cómo se ejecuta

```
python fb_load.py --start 2026-10-19 --end 2026-10-31 --solo historias
python fb_load.py --start 2026-11-01 --end 2026-11-15 --solo posts
python ig_load.py --start 2026-11-16 --end 2026-11-21
python video_earnings.py --start 2026-11-01 --end 2026-11-20
python cobertura.py
```

Reglas operativas: **un solo proceso a la vez** (el candado lo hace cumplir); copia de la base antes de cargas grandes; al terminar, verificar con `cobertura.py` y comprobar que no queden procesos de Python vivos. Para detener una carga, matar el proceso de Python directamente: cerrarla desde el terminal no siempre lo detiene.

## 5. Decisiones y hallazgos relevantes

1. **API oficial, no el tráfico interno.** Se descartó reproducir el GraphQL interno de Business Suite (cookies de sesión): Meta rechaza peticiones que no vienen del navegador y no se puede portar a Apps Script. La Graph API funciona con una app propia en **modo desarrollo** sobre una página de la que se es administrador: **no requiere App Review** ni verificación de empresa.
2. **Se pide por fecha de publicación; se mide por capturas.** La API solo filtra posts por fecha de publicación y sus métricas son acumuladas. La frescura se logra volviendo a medir (§6), no cambiando la ventana de búsqueda.
3. **Bug del alcance de Facebook (corregido).** Para `post_total_media_view_unique` Meta devuelve dos entradas: `lifetime` (valor real) y `day` (0). La primera versión guardaba ambas y el 0 sobrescribía al real. Ahora solo se acepta `lifetime` cuando existe. Los 1.913 posts del 1-16 oct se corrigieron con `fix_alcance_fb.py`; ese alcance se midió el 21/11/2026, no en la captura original de sus otras métricas.
4. **Límites de cuota: dos medidores distintos.** Los posts consumen el medidor de la página (holgado). Las **historias** consumen el de la app (`x-app-usage`), mucho más exigente: una carga de historias llegó al 87% y el error 4 bloquea incluso lecturas simples. Mitigación: lotes de 10 historias, pausa de 120 s si la cuota supera 60% y un solo proceso. Opción pendiente: pedir 3 métricas por historia (vistas, alcance, interacciones) en vez de 6 para reducir el costo a la mitad.
5. **Historias.** Facebook conserva un archivo de unos **80-90 días** (`status=ARCHIVED` + `since/until` en epoch). Instagram solo expone las **últimas 24 horas**, sin archivo: su histórico solo puede construirse con una captura diaria desde hoy.
6. **Ingresos.** Solo existen a nivel de página y por día (`monetization_approximate_earnings`, con desglose por herramienta). Los ingresos por video/post devuelven error 200 con token de página. Son cifras aproximadas que Meta corrige después.
7. **Métricas retiradas por Meta:** `post_impressions`, `post_impressions_unique`, `post_engaged_users`.
8. En v26+ el parámetro `ids` está en desuso: para consultas masivas se usa el endpoint `batch`.

## 6. Plan de actualización semanal (lunes)

1. Cargar los posts de la semana anterior (nuevos).
2. Volver a medir la semana previa a esa (captura de madurez).
3. Historias de Facebook: carga semanal (el archivo cubre ~90 días); una sola medición.
4. Instagram historias: captura **diaria** (pendiente de escribir).
5. Primera ejecución semanal: además, actualizar métricas del 9 al 15 nov y cargar desde el 16 nov, porque el histórico cierra el 15.

Consumo estimado del lunes: ~450-550 llamadas. Orden recomendado y secuencial: FB posts → pausa → FB historias → pausa → IG. Para comparar posts entre sí, usar la segunda captura (madura).

## 7. Credenciales y seguridad

`auth.json` guarda `page_token` (ingresos y Facebook), `ig_token` + `ig_user_id` (Instagram), `app_id` y `app_secret`. Los tokens de página no caducan, pero:

- `data_access_expires_at` del token de página vence el **19/02/2027**; conviene revisarlo mensualmente (`debug_token`).
- Dejan de valer si se cambia la contraseña de Facebook, se quita la app de *Integraciones* o se borra la app.
- Renovación: token de usuario en el Explorador de la API Graph → intercambio por uno de larga duración → token de página.
- `auth.json` y `*.har` están en `.gitignore`. El HAR original contiene datos de sesión: borrarlo. No compartir capturas donde se vea un token vigente.

App de Meta: **Reporte Páginas** (modo desarrollo), casos de uso *Administrar todo en tu página* y *Administrar mensajes y contenido en Instagram*; permisos `read_insights`, `pages_read_engagement`, `pages_show_list`, `instagram_basic`, `instagram_manage_insights`.

## 8. Pendientes

- [ ] Facebook: historias 19-oct → 15-nov y posts/reels 1 → 15 nov (esperar a que baje la cuota de la app).
- [ ] Decidir 6 vs 3 métricas por historia.
- [ ] Script de corrida semanal en un solo proceso.
- [ ] Captura diaria de historias de Instagram.
- [ ] Portar la corrida semanal a Apps Script (token en `PropertiesService`, salida a Sheets). La carga histórica queda en Python por el límite de 6 minutos de Apps Script.
