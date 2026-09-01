# Coach

Generador adaptativo de entrenamientos. Motor determinista + agente de Telegram
vía OpenClaw. Uso personal, un solo usuario, autoalojado en unraid.

## Contenido

```
DESIGN.md              Especificación completa. Fuente única de verdad.
data/
  repertorio.yaml      Los 39 ejercicios que el motor PUEDE programar hoy.
  exercises/*.yaml     Catálogo completo (144). Reserva para promociones.
  validate.py          Validador del catálogo. Debe correr en CI.
```

## Primer paso para una sesión de código

1. Leer `DESIGN.md` entero antes de escribir nada. En particular §0 (cómo usarlo),
   §2 (principios), §13 (invariantes, que ganan sobre cualquier decisión de
   implementación) y §15 (lo que ya se descartó y por qué).
2. `cd data && python3 validate.py` — debe pasar en verde.
3. Implementar P0 según §14: catálogo cargado a SQLite, motor de §6, servidor MCP
   con `generate_session` y `list_exercises`, contenedor. Sin IA, sin registro.
   Criterio de aceptación: una sesión generada cumple los invariantes 1–9.

## Lo que NO hay que hacer

Está en `DESIGN.md` §15, pero por si acaso: que el LLM decida el volumen o los
ejercicios, volver a cuotas semanales en lugar del modelo de frescura (§4.1),
meter Postgres, o ampliar el repertorio activo por encima de su límite (§5.6).
