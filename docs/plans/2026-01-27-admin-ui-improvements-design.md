# Admin UI Improvements Design

## Overview

Mejoras en las páginas de administración de Jobs y Drive: borrado lógico de jobs, paginación en la tabla de jobs, contadores detallados en Drive, procesamiento bulk, y sección dedicada para la carpeta de uploads de Slack.

---

## 1. Jobs Page - Borrado lógico y paginación

### 1.1 Borrado lógico

**Backend:**
- Nuevo campo `archived` (Boolean, default `false`) en el modelo `Job`.
- Migración Alembic para añadir la columna.
- Nuevo endpoint `POST /api/admin/jobs/archive` con body `{ "filter": "all" | "failed" | "completed" }`.
  - Marca como `archived=true` todos los jobs que coincidan con el filtro.
  - Devuelve `{ "archived_count": N }`.
- El endpoint `GET /api/admin/jobs` filtra `archived=false` por defecto.
- El endpoint `GET /api/admin/jobs/stats` solo cuenta jobs no archivados.

**Frontend:**
- 3 botones en la cabecera de la página: "Archivar todos", "Archivar failed", "Archivar completed".
- Cada botón requiere confirmación antes de ejecutar.
- Tras archivar, refresca la lista y los stats.

### 1.2 Paginación

**Backend:** Ya soporta `page` y `page_size` en `GET /api/admin/jobs`. No requiere cambios.

**Frontend:**
- Controles de paginación al pie de la tabla: botones anterior/siguiente.
- Indicador "Página X de Y".
- Page size fijo (20 por defecto, el mismo que el backend).

---

## 2. Drive Page - Contadores, procesamiento bulk y carpeta de uploads

### 2.1 Contadores por carpeta

**Backend:**
- Añadir `completed_count` al response de `GET /api/admin/drive/folders` (actualmente solo devuelve `pending_count` y `failed_count`).

**Frontend:**
- Cada fila de carpeta muestra 3 badges:
  - Verde: ficheros procesados (`completed_count`)
  - Azul: sin procesar (`pending_count`)
  - Rojo: fallidos (`failed_count`)

### 2.2 Procesamiento bulk

**Backend:**
- Nuevo endpoint `POST /api/admin/drive/folders/{folder_id}/retry-failed` que reprocesa todos los ficheros fallidos de una carpeta.
- Para pendientes se reutiliza `POST /api/admin/drive/folders/{id}/sync?process_files=true`.

**Frontend:**
- Los badges de "sin procesar" y "fallidos" tienen un botón de acción asociado para lanzar el procesamiento bulk.

### 2.3 Carpeta de uploads (sección separada)

**Backend:**
- Nuevo endpoint `GET /api/admin/drive/uploads-folder` que:
  - Lee `DRIVE_UPLOADS_FOLDER_ID` del env.
  - Devuelve info de la carpeta y contadores (`completed_count`, `pending_count`, `failed_count`).
  - Si no está configurada, devuelve `null`.

**Frontend:**
- Sección separada debajo de la tabla de carpetas con título "Carpeta de uploads".
- Enlace directo a Google Drive: `https://drive.google.com/drive/folders/{id}`.
- Mismos 3 badges de contadores con botones de procesamiento bulk.
- Sin botón de delete.

---

## Endpoints nuevos (resumen)

| Method | Path | Descripción |
|--------|------|-------------|
| POST | `/api/admin/jobs/archive` | Archivar jobs por filtro |
| POST | `/api/admin/drive/folders/{id}/retry-failed` | Reprocesar ficheros fallidos |
| GET | `/api/admin/drive/uploads-folder` | Info y contadores de la carpeta de uploads |
