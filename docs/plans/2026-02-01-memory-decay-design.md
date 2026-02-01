# Memory Decay para HARI

## Contexto

HARI ingiere principalmente informes de tendencias de consultoras (McKinsey, Gartner, Deloitte, etc.) que se publican anualmente. Un informe de tendencias de 2022 no debería competir en relevancia con uno de 2025.

## Objetivo

Reducir el peso de documentos antiguos en el retrieval para que los resultados reflejen información actualizada, sin eliminar los documentos (que siguen disponibles para consultas explícitas).

## Diseño

### Escalones de decay

| Estado | Antigüedad | Peso aplicado | Efecto |
|--------|------------|---------------|--------|
| Fresco | 0-18 meses | 100% | Score sin modificar |
| Viejo | 18-24 meses | 70% | Solo pasan documentos con similarity >= 0.71 |
| Obsoleto | >24 meses | 50% | Efectivamente invisibles (threshold 0.5 requiere similarity > 1.0) |

### Configuración

Variables de entorno en `backend/app/core/config.py`:

```python
DECAY_THRESHOLD_STALE_MONTHS: int = 18
DECAY_THRESHOLD_OBSOLETE_MONTHS: int = 24
DECAY_WEIGHT_STALE: float = 0.70
DECAY_WEIGHT_OBSOLETE: float = 0.50
```

### Implementación

**No se requieren cambios en el esquema de base de datos.** El campo `created_at` ya existe.

**Modificación en `backend/app/services/search/semantic.py`:**

La query añade `created_at` al SELECT:

```sql
SELECT
    id, title, quick_summary, keywords, url, created_at,
    1 - (embedding <=> cast(:embedding as vector)) as raw_similarity
FROM documents
WHERE processing_status = 'COMPLETED'::processingstatus
    AND embedding IS NOT NULL
ORDER BY embedding <=> cast(:embedding as vector)
LIMIT :limit
```

El decay se aplica post-query en Python:

```python
def apply_decay(raw_similarity: float, created_at: datetime, ignore_decay: bool) -> float:
    if ignore_decay:
        return raw_similarity

    age_months = (datetime.now(UTC) - created_at).days / 30

    if age_months <= settings.DECAY_THRESHOLD_STALE_MONTHS:
        weight = 1.0
    elif age_months <= settings.DECAY_THRESHOLD_OBSOLETE_MONTHS:
        weight = settings.DECAY_WEIGHT_STALE
    else:
        weight = settings.DECAY_WEIGHT_OBSOLETE

    return raw_similarity * weight
```

Después de aplicar decay: filtrar por threshold y re-ordenar.

### Flag ignore_decay

Permite desactivar el decay para búsquedas que necesiten incluir documentos antiguos.

**Frontend:**
- Checkbox junto al input del chat: "Incluir documentos antiguos"
- Se envía como parámetro en la request

**API:**
- `/api/query` recibe `ignore_decay: bool = False`
- `/api/search` recibe `ignore_decay: bool = False`

**Propagación:**
```
Frontend checkbox
    ↓
/api/query (ignore_decay param)
    ↓
AgentState.ignore_decay
    ↓
retriever_node
    ↓
HybridSearch.search(ignore_decay=...)
    ↓
SemanticSearch.search(ignore_decay=...)
```

## Archivos a modificar

1. `backend/app/core/config.py` - añadir settings de decay
2. `backend/app/services/search/semantic.py` - implementar decay post-query
3. `backend/app/services/search/hybrid.py` - propagar parámetro ignore_decay
4. `backend/app/agent/state.py` - añadir campo `ignore_decay: bool = False`
5. `backend/app/agent/nodes/retriever.py` - pasar flag a HybridSearch
6. `backend/app/api/query.py` - recibir ignore_decay en request
7. `backend/app/api/search.py` - recibir ignore_decay en request
8. `frontend/src/components/Chat.tsx` - añadir checkbox

## Testing

**Tests unitarios:**
- `test_apply_decay()` - verificar los tres escalones y el flag ignore_decay
- Casos borde: documentos exactamente en 18 y 24 meses

**Test de integración:**
- Insertar 3 documentos con fechas distintas (6, 20, 30 meses de antigüedad)
- Verificar orden correcto con decay activo
- Verificar que ignore_decay=True devuelve orden por similarity pura

## Rollout

1. Implementar con valores por defecto (18/24 meses, 70%/50%)
2. Los documentos actuales tienen pocos meses - el decay empezará a aplicarse naturalmente
3. Ajustar pesos via variables de entorno si es necesario
