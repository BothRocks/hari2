# Catálogo de ejercicios — semilla

Formato definido en `DESIGN.md` §5.1. Los campos omitidos toman sus valores por defecto:

```yaml
unilateral: false          tipo_progresion: doble      requiere_escalon: false
carga_max_pct_peso: null   prerrequisito: null         penalizacion_usuario: {factor: 1.0}
es_core: false             es_potencia: false          video: null
seg_por_rep: 3.5
```

`doms_risk` (1–5) según §4.3. Criterio aplicado:

| Riesgo | Perfil | Ejemplos |
|---|---|---|
| 1 | Isométrico o rango corto, sin excéntrica cargada | Planchas, carries, movilidad |
| 2 | Concéntrico dominante o excéntrica trivial | Olímpicos, swings, remos |
| 3 | Compuesto estándar con excéntrica normal | Press banca, sentadilla, dominadas |
| 4 | Excéntrica marcada o posición estirada | Zancadas caminando, búlgara, RDL profundo |
| 5 | Excéntrica dominante o palanca larga en estiramiento | Nórdico, dragon flag, jefferson curl |

`estres_articular`: 0–3 por articulación. Se usa para filtrar cuando hay molestias activas.
