# Histórico de contenido y métricas de Facebook e Instagram

Descarga local de publicaciones y reels de la página **El Universal** (Facebook) y la cuenta **@eluniversalctg** (Instagram) con sus métricas. Fuente: **Graph API oficial de Meta**. Estado actualizado el 25/11/2026.

> **Historias: proyecto abandonado (25/11/2026).** Su código, datos y hallazgos están en [`historias_abandonado/`](historias_abandonado/README.md). Nada de lo que sigue las incluye.

## 1. Estado de cobertura (1-oct → 23-nov-2026)

| Fuente | Días cubiertos | Registros | Pendiente |
|---|---|---|---|
| Facebook posts y reels | 54 / 54 | 6.077 (5.812 fotos, 169 reels, 96 otros) | — |
| Instagram posts y reels | 54 / 54 | 748 (421 reels, 190 carruseles, 137 imágenes) | — |

El histórico cierra el **23 de noviembre**. El 24-nov queda para la primera prueba de la tarea diaria en producción (§6).

Cada post tiene **una sola medición**: los del 1-oct al 15-nov se midieron el 21/11/2026, y los del 16 al 23-nov el 25/11/2026 (con solo 2 a 9 días de publicados, por lo que aún pueden crecer unos puntos porcentuales; ver §5.7). Antes de la carga del 16-23 nov se hicieron copias `fb_history.backup_antes_16_23nov.db` e `ig_history.backup_antes_16_23nov.db`.

Se regenera la tabla con `python cobertura.py [--detalle]` (lee las bases locales; no llama a Meta).

Verificación del 24/11/2026: IG coincide con la API uno a uno (635 de 635); FB del 15-nov coincide (101 de 101).

## 2. Archivos

| Archivo | Función |
|---|---|
| `fb_load.py` | Carga Facebook (posts, reels y videos), día por día |
| `ig_load.py` | Carga Instagram (posts y reels), por ventanas semanales |
| `cobertura.py` | Tabla de cobertura por día y fuente → consola y `cobertura.csv` |
| `carga_lock.py` | Candado: impide que corran dos cargas a la vez |
| `fix_alcance_fb.py` | Corrección puntual ya ejecutada (ver §5.3). No volver a correr |
| `fb_history.db`, `ig_history.db` | Bases SQLite con el histórico |
| `fb_publicaciones.csv`, `ig_publicaciones.csv` | Vista plana, una fila por publicación (última captura). Se regeneran en cada carga |
| `auth.json` | Credenciales (no versionar; ver §7) |
| `fb_history.backup_*.db` | Copias previas a operaciones delicadas; se pueden borrar tras validar |
| `historias_abandonado/` | Todo lo relativo a historias (proyecto abandonado) |

Ejecutar con `python` normal desde esta carpeta (no con `-I`, que impide importar `carga_lock`).

## 3. Modelo de datos

Mismo esquema en ambas bases:

- **`posts`**: `id` (PK), `permalink`, `tipo` (Facebook: `foto`, `reel`, `video`, `otro`; Instagram: `reel`, `carrusel`, `imagen`, `video`), `timestamp_utc`, `fecha_local`, texto/tipo original de Meta.
- **`metricas`**: `post_id`, `captured_at`, `metric`, `value`. **Una fila por captura**: volver a medir un post añade filas nuevas; no sobrescribe.
- **`errores`**: publicaciones sin métricas o con fallos.

Convenciones: fechas locales en **hora de Colombia (UTC-5)**; el `id` de Facebook es `{página}_{post}`; los CSV muestran la captura más reciente de cada post.

**Métricas**

| Plataforma | Métricas |
|---|---|
| Facebook posts | `post_media_view` (vistas), `post_total_media_view_unique` (alcance), `post_clicks`, reacciones (`reacciones_total` y `reaccion_*`), `post_video_views`, `shares` (campo del post) |
| Instagram | `reach`, `views`, `saved`, `shares` |

## 4. Cómo se ejecuta

```
python fb_load.py --start 2026-11-16 --end 2026-11-23 --parar-en 60
python ig_load.py --start 2026-11-16 --end 2026-11-23
python cobertura.py
```

Reglas operativas: **un solo proceso a la vez** (el candado lo hace cumplir); copia de la base antes de cargas grandes; al terminar, verificar con `cobertura.py` y comprobar que no queden procesos de Python vivos. Para detener una carga, matar el proceso de Python directamente: cerrarla desde el terminal no siempre lo detiene.

## 5. Decisiones y hallazgos relevantes

1. **API oficial, no el tráfico interno.** Se descartó reproducir el GraphQL interno de Business Suite (cookies de sesión): Meta rechaza peticiones que no vienen del navegador y no se puede portar a Apps Script. La Graph API funciona con una app propia en **modo desarrollo** sobre una página de la que se es administrador: **no requiere App Review** ni verificación de empresa.
2. **Se pide por fecha de publicación; se mide por capturas.** La API solo filtra posts por fecha de publicación y sus métricas son acumuladas. La frescura se logra volviendo a medir (§6), no cambiando la ventana de búsqueda.
3. **Bug del alcance de Facebook (corregido).** Para `post_total_media_view_unique` Meta devuelve dos entradas: `lifetime` (valor real) y `day` (0). La primera versión guardaba ambas y el 0 sobrescribía al real. Ahora solo se acepta `lifetime` cuando existe. Los posts del 1-16 oct se corrigieron con `fix_alcance_fb.py`; ese alcance se midió el 21/11/2026.
4. **Cuota.** Los posts consumen el medidor de la página, que es holgado: descargar los 101 posts de FB de un día dejó la cuota en 1 %. `ig_load.py` no mide la cuota de forma preventiva; solo reintenta cuando Meta ya devolvió un error de límite. (Las historias, que consumen el medidor de la app, mucho más exigente, están en `historias_abandonado/`.)
5. **Métricas retiradas por Meta:** `post_impressions`, `post_impressions_unique`, `post_engaged_users`.
6. En v26+ el parámetro `ids` está en desuso: para consultas masivas se usa el endpoint `batch`.
7. **Las cifras cambian poco al volver a medir (prueba del 24/11/2026).** Se volvió a descargar el 15-nov, en una carpeta temporal, 3 días después de la primera captura (posts de 5-6 días de publicados al inicio):

   | | Vistas | Alcance |
   |---|---|---|
   | Instagram (31 posts) | +1,3 % | +1,1 % |
   | Facebook (101 posts) | +0,38 % | +0,29 % |

   Ninguna cifra de vistas ni de alcance bajó. Reels, carruseles e imágenes crecen más que las fotos de FB, y los posts más recientes crecen más que los viejos (IG: +2,1 % frente a +0,8 % en vistas). Pasada una semana el cambio es de alrededor de 1 % o menos.
8. **Los compartidos de Facebook pueden bajar.** En esa misma prueba, `shares` bajó en 22 de 101 posts (casi siempre de a 1; 5 quedaron en 0) y subió en 7. Es un campo del post, no una métrica de insights, y puede bajar. No es fiable comparado post por post; usar totales. Además, `fb_load.py` guarda 0 cuando la API no devuelve el campo `shares`, lo que no se ha descartado como causa de algunos de esos ceros.

## 6. Plan de actualización diaria (acordado, aún no implementado)

Una tarea que corre **cada día** y, para cada fecha, reemplaza la cifra de cada post por la nueva. No se conserva historial de capturas; interesa el dato fresco.

- **Fechas que actualiza cada día:** ayer y ayer menos 7 días (el mismo día de la semana, una semana antes). Ejemplo: el miércoles 25-nov actualiza el martes 24-nov y el martes 17-nov.
- Cada post se mide dos veces: al día siguiente de publicado y a los 8 días; después queda congelado.
- **Formato:** una fila por post, con las métricas en columnas, que se sobrescribe. Sin duplicados.
- **Desarrollo:** primero un script local (salida en CSV, mismo formato que tendrá el Sheet), y en producción pasarlo a **Apps Script** (token en `PropertiesService`, salida a Google Sheets, escritura en lote, alerta por correo si falla). Un día de datos cabe en el límite de 6 minutos de Apps Script. La carga histórica queda en Python.
- Las bases actuales (`fb_history.db`, `ig_history.db`) quedan como histórico de octubre y noviembre.

## 7. Credenciales y seguridad

`auth.json` guarda `page_token` (Facebook), `ig_token` + `ig_user_id` (Instagram), `app_id` y `app_secret`. Los tokens de página no caducan, pero:

- `data_access_expires_at` del token de página vence el **19/02/2027**; conviene revisarlo mensualmente (`debug_token`).
- Dejan de valer si se cambia la contraseña de Facebook, se quita la app de *Integraciones* o se borra la app.
- Renovación: token de usuario en el Explorador de la API Graph → intercambio por uno de larga duración → token de página.
- `auth.json` y `*.har` están en `.gitignore`. El HAR original contiene datos de sesión: borrarlo. No compartir capturas donde se vea un token vigente.

App de Meta: **Reporte Páginas** (modo desarrollo), casos de uso *Administrar todo en tu página* y *Administrar mensajes y contenido en Instagram*; permisos `read_insights`, `pages_read_engagement`, `pages_show_list`, `instagram_basic`, `instagram_manage_insights`.

## 8. Pendientes

- [ ] Escribir el script diario local (ayer y ayer menos 7 días, una fila por post, salida CSV).
- [x] Cargar los posts de FB e IG del 16 al 23-nov (hecho el 25/11/2026: 872 posts de FB y 113 de IG, cuota de Meta en 1 %, sin errores).
- [ ] Primera prueba en producción de la tarea diaria con el 24-nov.
- [ ] Portar la corrida diaria a Apps Script.
- [ ] Añadir pausa preventiva por cuota a `ig_load.py`.
- [ ] Revisar los posts de FB cuyos compartidos pasaron a 0 (¿campo ausente en la API?).
