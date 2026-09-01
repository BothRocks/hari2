# Coach — Generador adaptativo de entrenamientos (diseño)

Fecha: 2026-09-01
Estado: propuesta / en iteración
Branch: `claude/workout-generator-app-p1g0ev`

---

## 1. Problema

Volver al gimnasio a los 54 años, con historial de CrossFit y de 5x5, y con tres
restricciones fuertes que definen el producto:

| Restricción | Implicación de diseño |
|---|---|
| "No quiero agujetas todos los días" | El daño muscular (DOMS) es una **variable de primera clase** del motor, con presupuesto y tope semanal. No es un efecto secundario aceptable. |
| "5x5 me aburre y llego a plateau rápido" | Rotación controlada de variantes + progresión autorregulada, no lineal. |
| "Tengo X minutos y estoy en Y sitio" | La sesión se genera **en el momento**, no se sigue un plan rígido de calendario. |

**Objetivos, por orden de prioridad:**
1. Fortalecer core y espalda (fundamental)
2. Movilidad y agilidad
3. VO2máx

**Contextos:**
- **Gimnasio**: pesos libres (barra olímpica, mancuernas, kettlebells). Máquinas solo como último recurso.
- **Casa**: cero equipamiento, solo peso corporal.

---

## 2. Idea central

> Un **motor determinista** decide *qué* hay que entrenar hoy (a partir de déficits
> acumulados, fatiga y tiempo disponible). La **IA** decide *cómo* se ve (variantes,
> redacción, sustituciones) y hace la **revisión semanal** de la progresión.

Razones:

- **Latencia y fiabilidad**: "voy a entrenar, 40 minutos, gimnasio" tiene que devolver
  la tabla en <1 s, en el móvil, en el vestuario, aunque no haya API key ni internet.
  El camino crítico no puede depender de un LLM.
- **Los LLM alucinan volumen**. Un modelo suelto propone 25 series de espalda el martes
  y 0 el resto de la semana. Las cuentas (series semanales por patrón, topes de DOMS,
  minutos) son aritmética: código.
- **El código es aburrido**. Elegir *qué variante concreta* de remo, con qué cue, con qué
  progresión narrativa, y detectar "llevas 3 semanas estancado en el hinge y además
  siempre te quejas del hombro derecho en press" — eso sí es razonamiento.
- **Testeable**: el motor se valida con property tests (nunca excede el tiempo, nunca
  supera el tope de DOMS, nunca deja el core sin tocar 4 días). Un LLM no.

```
"voy a entrenar, 45 min, gimnasio"
        │
        ├─► [parser]  minutos / lugar / estado  (regex → fallback LLM barato)
        │
        ├─► [estado]  déficits semanales · fatiga por grupo · anchors y su progresión
        │
        ├─► [motor]   plantilla por tiempo → slots (patrón, series, intensidad, RIR)
        │             filtros: equipamiento, fatiga, tope DOMS, novedad, dolor articular
        │             scoring → ejercicio elegido por slot + carga sugerida del histórico
        │
        ├─► [LLM opcional, no bloqueante]  cues, título, nota del coach, desempate
        │
        └─► TABLA  (siempre se devuelve, aunque el LLM falle)
```

---

## 3. Metodología de entrenamiento (el corazón)

Esto es lo que hay que discutir primero: si el modelo de entrenamiento está mal,
la app es una interfaz bonita sobre malos consejos.

### 3.1 Modelo de "frescura" (entrenamiento oportunista, sin cuotas semanales)

No hay lunes de pecho ni cuota semanal que cumplir. Cada **cualidad** lleva su propio
reloj: cuánto hace que no la tocas y con qué rapidez "caduca". La sesión de hoy ataca
lo que esté más rancio y sea más prioritario, con el tiempo que tengas.

```
score(cualidad) = prioridad × frescura × encaje_readiness × encaje_tiempo

frescura = 1 − exp(−días_desde_última_exposición / τ)
```

| Cualidad | Prioridad | τ (días) | Comentario |
|---|---|---|---|
| Core anti-extensión / anti-rotación | 1.00 | 1.5 | Caduca rápido: quieres tocarlo casi a diario |
| Movilidad | 0.85 | 1.0 | La más perecedera de todas |
| Tracción horizontal (espalda) | 0.95 | 3.0 | |
| Tracción vertical (espalda) | 0.90 | 3.5 | |
| Hinge / erectores | 0.85 | 4.0 | Alta prioridad pero se recupera despacio |
| Potencia / agilidad | 0.70 | 4.0 | Dosis pequeñas, siempre en fresco |
| Intervalos VO2 | 0.65 | 3.5 | |
| Z2 | 0.55 | 3.0 | Puede venir de actividad externa (paseo, bici) |
| Rodilla dominante | 0.60 | 4.5 | |
| Empuje | 0.45 | 5.0 | Equilibrio, no objetivo |
| Carries | 0.60 | 4.0 | Core + espalda + agarre, DOMS ≈ 0 |

**Por qué esto y no cuotas semanales:** con entrenamiento oportunista, una cuota
("9 series de espalda esta semana") genera dos patologías. Si entrenas poco, acumulas
una deuda que el sistema intenta meter a martillazos en la siguiente sesión — justo lo
que produce agujetas. Si entrenas mucho, se queda sin nada que mandarte y repite.
El modelo de frescura se **autonormaliza**: si entrenas 6 días, todo está fresco y las
sesiones se vuelven variadas y de menor volumen por cualidad; si entrenas 2, cada
sesión va directa a lo más prioritario y rancio. Nunca hay deuda, nunca hay culpa.
(Es, básicamente, el mismo decaimiento exponencial que usa la memoria de HARI.)

El **volumen** por sesión se calibra con la frecuencia real observada (media móvil
exponencial de sesiones/semana de las últimas 4 semanas), para que entrenar 2 días no
signifique intentar meter la semana entera en cada sesión.

### 3.2 Los McGill Big 3 como columna vertebral diaria

Curl-up, side plank, bird dog. Isométricos, progresión por **densidad** (segundos y
repeticiones, no carga), casi cero daño muscular, y atacan exactamente el objetivo 1.
Se microdosifican en el calentamiento de *toda* sesión de gimnasio y son el núcleo de
las sesiones cortas de casa. Es la forma más barata de cumplir "core y espalda" sin
generar agujetas.

### 3.3 Modelo de DOMS (la restricción diferencial)

Las agujetas vienen sobre todo de: **novedad** del ejercicio, **carga excéntrica**,
**carga en posición estirada**, **volumen** y **llegar al fallo**. El catálogo
etiqueta cada ejercicio con un `doms_risk` (1–5) derivado de esas dimensiones.

Reglas del motor:

- **Novedad**: ejercicio nunca hecho o sin hacer >8 semanas → primera exposición al
  **60 % del volumen** y máximo **1 ejercicio nuevo por sesión**. Esto es el 80 % del
  problema resuelto: las agujetas casi siempre son "hice algo nuevo con volumen normal".
- **Tope semanal de daño**: `Σ (doms_risk × series_efectivas)` por grupo muscular
  ≤ umbral. Al superarse, ese grupo solo recibe trabajo de bajo daño (isométrico,
  concéntrico, rango corto, carries).
- **RIR objetivo por defecto 2–3.** El fallo se reserva a 1–2 series "top" por semana,
  y nunca en ejercicios con `doms_risk ≥ 4`.
- **Fatiga por grupo** con decaimiento exponencial (vida media ~40 h) alimentada por
  volumen ejecutado + feedback de agujetas del usuario. Si un grupo está por encima
  del umbral, se excluye o se degrada a trabajo técnico.
- **Feedback loop**: al día siguiente, dos taps ("¿agujetas? ¿dónde?"). Eso recalibra
  el `doms_risk` **personal** de los ejercicios concretos que hiciste. En 4–6 semanas
  el sistema conoce tu tolerancia real, no la media poblacional.

### 3.4 Anti-plateau y anti-aburrimiento (la tensión de diseño)

Rotar mucho = variedad pero progresión inmedible. Rotar poco = 5x5 otra vez.
La resolución es la separación en dos capas:

- **Anchors (4–5 ejercicios fijos)**: se mantienen 8–12 semanas y son la métrica de
  progreso. Propuesta: *peso muerto con barra hexagonal o RDL*, *front squat o goblet*,
  *dominada lastrada*, *remo con apoyo en banco*, *press militar con mancuernas*.
  Progresión de doble avance (reps → carga) con top set autorregulado + back-offs.
  Se estima e1RM (Epley con corrección por RPE) para graficar tendencia.
- **Accesorios y acondicionamiento: rotación libre.** Aquí vive la variedad, y aquí es
  donde el LLM aporta. Cambian cada 2–3 semanas, dentro de la misma familia de patrón.

**Detección de plateau**: pendiente del e1RM del anchor ≤ 0 en 3 sesiones →
el sistema propone, en este orden: (1) cambiar rango de repeticiones, (2) cambiar a
variante hermana del mismo patrón, (3) descarga de una semana.
**Deload automático** cada 5–6 semanas o disparado por tendencia de readiness/RPE.

**Índice de aburrimiento**: si un ejercicio accesorio aparece más de N veces en M
semanas, se penaliza en el scoring. La variedad es una restricción explícita, no un
accidente.

### 3.5 VO2 y Z2

- **Modalidad de bajo impacto** por defecto (remo, bici, assault bike, cuesta/cinta
  inclinada, comba): a los 54, correr intervalos duros es la vía rápida a la lesión y
  a las agujetas.
- **Protocolos**: 4x4 noruego (4 min @ 90–95 % FCmáx / 3 min suave), 30/30 de Billat,
  10-20-30. 1–2 por semana, **nunca en días consecutivos** ni el día después de un
  hinge pesado (interferencia).
- **Z2**: se puede registrar como actividad externa (paseo, bici) sin generar sesión.
- **Test mensual**: Cooper 12 min, o 5 min máximos en remo, o FC en reposo + HRR.
  Sirve para graficar el objetivo 3, que si no es invisible.

### 3.5.1 Entrada de datos: Apple Health / HealthKit

HealthKit no tiene API de servidor y **una PWA no puede leerlo** (es una API nativa de
iOS). El dato tiene que empujarlo el teléfono. Opciones, de más a menos práctica:

1. **Health Auto Export (app de iOS, ~5 €)** — recomendada. Permite automatizaciones
   tipo "cada día a las 7:00, POST en JSON a esta URL" con cabeceras propias. Apuntas
   a `POST /api/health/ingest` con un token y ya está. Cero código en iOS.
2. **Atajos (Shortcuts)** — gratis. Automatización "al terminar un entrenamiento" que
   lee muestras de salud y hace una petición. Más frágil y más limitado en qué métricas
   puede extraer, pero no cuesta dinero.
3. **App nativa propia con HealthKit** — requiere Xcode y cuenta de desarrollador
   (99 €/año para instalarla de forma permanente). Desproporcionado.

**Lo que merece la pena traerse:**

| Métrica | Uso en la app |
|---|---|
| VO2máx ("Capacidad cardiovascular") | Es *directamente* el objetivo 3, medido por Apple sin tests |
| FC en reposo, HRV (SDNN) | Readiness **automática**: desviación frente a la línea base de 60 días |
| Sueño (duración y fases) | Readiness |
| Entrenamientos (tipo, minutos, FC media, zonas) | Alimenta Z2 y VO2 sin registro manual |
| Peso | Métrica de contexto |

**El gran beneficio no es el gráfico de VO2, es que la readiness deja de pedir taps.**
Si el sistema ya sabe que has dormido 5 h y tu HRV está un 20 % por debajo de tu base,
recorta el volumen solo y te lo dice, sin preguntarte nada.

**Aviso importante sobre el VO2máx de Apple**: solo se actualiza en caminata, carrera o
senderismo **al aire libre** con el Watch. Remo, bici estática o assault bike no lo
tocan. Si quieres ver moverse el objetivo 3 sin salir a la calle, hay que mantener el
test manual mensual (Cooper o 5 min de remo) además del dato de Apple.

**Diseño del endpoint**: `POST /api/health/ingest` con token compartido, idempotente por
UUID de muestra o por (fecha, métrica), tolerante a lotes solapados y a llegadas
desordenadas. Escribe en `metric` y `external_activity`. Un job nocturno recalcula las
líneas base y la readiness derivada.

### 3.6 Movilidad y agilidad

- **Calentamiento específico generado**: siempre acorde a los patrones del día
  (no "5 min de bici").
- **Flow diario de 6–10 min**: CARs, 90/90, cossack, rotación torácica, dorsiflexión
  de tobillo. Es también la sesión de casa por defecto cuando hay poco tiempo.
- **Agilidad/potencia en dosis pequeñas y en fresco**: saltos bajos, lanzamientos de
  balón medicinal (potencia + anti-rotación), swings de kettlebell, cambios de
  dirección, gateos, *Turkish get-up* (movilidad + core + control: encaja perfecto con
  el perfil ex-CrossFit y los objetivos 1 y 2).

### 3.7 Plantillas por tiempo disponible

| Min | Gimnasio | Casa |
|---|---|---|
| 15 | Big 3 + carries + movilidad | Flow de movilidad + Big 3 |
| 20–25 | Calentamiento + 1 anchor (top set + 2 back-off) + core | Circuito core/espalda + movilidad |
| 30–35 | + 1 superserie accesoria | + potencia ligera / intervalos sin impacto |
| 45 | Calentamiento 8' + anchor 15' + 2 accesorios en superserie 12' + finisher core/carry 8' | Circuito completo + intervalos |
| 60 | + 2º patrón principal o bloque de acondicionamiento | |
| 75+ | Sesión completa + Z2 o intervalos | |

Regla dura: la suma de tiempos estimados (series × (trabajo + descanso) + transiciones)
**nunca** excede el presupuesto. Se recorta por la cola, empezando por lo de menor
prioridad según el déficit semanal.

### 3.8 Readiness (3 taps, sin fricción)

Sueño / energía / agujetas (mapa corporal tocable). Produce un modificador que escala
el volumen ±20 % y limita la intensidad. Se puede saltar: por defecto asume "normal".

---

## 4. Uso de IA

| Tarea | Modelo | Dónde | Bloqueante |
|---|---|---|---|
| Parseo de "voy a entrenar, 40 min, gimnasio, reventado" | Haiku vía API (regex primero) | request | No (fallback a formulario) |
| Cues, título de sesión, nota corta del coach | Haiku vía API | request, async | No |
| Sustituir ejercicio ("el rack está ocupado", "me molesta el hombro") | Haiku vía API | request | No (fallback: siguiente candidato del motor) |
| **Revisión semanal / mesociclo** | Opus vía `claude -p` (o codex) | cron semanal, offline | No |
| Ampliar catálogo de ejercicios | Opus vía `claude -p` | manual, con revisión humana | No |

**Revisión semanal (el uso interesante):** un job lee 4 semanas de logs, feedback,
dolores y tendencias de e1RM, y emite un **parche de política** en JSON validado contra
esquema: ajusta objetivos semanales, rota anchors, marca ejercicios problemáticos,
propone la descarga, y escribe 5 líneas en castellano explicando qué ha visto y qué
cambia. Sale del camino crítico, puede tardar 2 minutos y costar lo que sea.

**Guardarraíles**: toda salida del LLM se valida contra el catálogo (IDs reales) y
contra las restricciones de volumen/DOMS. Si no valida → se descarta y se usa el
resultado determinista. El LLM nunca inventa ejercicios en tiempo de ejecución; puede
*proponerlos* a una cola de aprobación.

---

## 5. Modelo de datos

```
exercise            id, slug, nombre_es, patrones[], equipamiento[], unilateral,
                    tipo_carga (barra/mancuerna/kb/corporal/banda/máquina),
                    doms_risk (1-5), doms_risk_personal, skill, estrés_articular{},
                    es_core, es_potencia, rango_reps_sugerido, tiempo_por_serie,
                    familia_id, cues[], video_url
exercise_family     id, patrón, progresiones[] / regresiones[]   (para sustituciones)

policy              versión, objetivos_semanales{}, anchors[], topes_doms{},
                    creada_por (motor|revisión_llm), notas
session             fecha, lugar, minutos_previstos/reales, readiness, estado,
                    generation_meta (semilla, déficits, por qué cada elección)
session_block       orden, tipo (warmup|fuerza|accesorio|acond|movilidad|cooldown)
session_item        bloque, exercise_id, series, reps/tiempo, carga_objetivo, RIR,
                    descanso, notas, sustituido_de
set_log             item, nº serie, reps, carga, RPE, hecho
feedback            sesión, RPE global, disfrute (1-5), dolor_articular{}, 
                    agujetas_día_siguiente{grupo: 0-3}
muscle_state        grupo, fatiga, última_carga, actualizado
note                texto libre, fecha, tags        ("el hombro derecho en press...")
metric              fecha, tipo (peso|FC_reposo|test_VO2|e1RM), valor
external_activity   fecha, tipo, minutos, zona      (paseo, bici, partido de pádel)
```

`generation_meta` es importante: guardar **por qué** se eligió cada ejercicio hace que
el sistema sea depurable y explicable ("hoy toca tirón vertical porque llevas 5 días").

---

## 6. API

```
POST /api/sessions/generate     {minutos, lugar, readiness?, texto_libre?}  → sesión
POST /api/sessions/{id}/items/{n}/swap   {motivo}                → item alternativo
POST /api/sessions/{id}/sets             {item, serie, reps, carga, rpe}
POST /api/sessions/{id}/finish           {rpe_global, disfrute, dolor}
POST /api/feedback/soreness              {mapa}                  (al día siguiente)
GET  /api/dashboard                      déficits, tendencias, próximo test
GET  /api/exercises                      catálogo, filtros
POST /api/reviews/run                    dispara revisión LLM (también por cron)
GET  /api/export | POST /api/import      JSON completo (sin lock-in)
```

---

## 7. Stack y despliegue en unraid

- **Backend**: FastAPI + SQLAlchemy + Alembic (mismas convenciones que HARI).
- **Persistencia**: **SQLite** (aiosqlite). Un usuario, un fichero, backup = copiar.
  Postgres es innecesario aquí y complica el contenedor de unraid.
- **Frontend**: React + Vite + Tailwind + shadcn (reutilizable desde `frontend/`),
  **PWA instalable**, mobile-first, cola offline para registrar series sin cobertura
  (los sótanos de los gimnasios no tienen 4G).
- **Contenedor**: imagen única multi-stage (build del frontend → FastAPI sirve estáticos).
  `docker-compose.yml` + plantilla unraid. Un volumen `/data`.
- **Auth**: PIN o token en env; pensado para LAN / Tailscale. Sin OAuth.
- **`claude -p`**: no vive dentro del contenedor (auth y peso). Se ejecuta en el host
  por cron semanal contra la API (`POST /api/reviews/run --dry` → parche JSON), o se
  usa la API de Anthropic también para la revisión. **Decisión abierta.**

### UX (lo que decide si la usas o no)

Pantalla única: `[ Entrenar ]` → slider de minutos + chips `Gimnasio | Casa | Fuera`
+ 3 taps de readiness (saltables) → tabla. Durante la sesión: checkbox por serie,
carga preplaceada con la de la última vez, temporizador de descanso, botón **↺
sustituir** en cada ejercicio. Al terminar: 3 taps. Nada más. Ninguna pantalla de
configuración obligatoria.

---

## 8. Fases

| Fase | Alcance | Valor |
|---|---|---|
| **P0** | Catálogo semilla (~120 ejercicios), motor determinista, plantillas por tiempo, generar + mostrar tabla. Sin IA. | Ya es usable el primer día |
| **P1** | Registro de series, histórico, cargas sugeridas, anchors y e1RM, dashboard de déficits | Progresión medible |
| **P2** | Readiness + modelo de DOMS/fatiga + feedback de agujetas + sustituciones | Aquí se cumple "sin agujetas" |
| **P3** | IA: parseo de texto libre, cues, **revisión semanal con `claude -p`**, notas del coach | Aquí deja de aburrir |
| **P4** | PWA offline, tests de VO2, importación de wearable (Garmin/Strava), gráficas | Objetivo 3 medible |

Property tests desde P0: el motor nunca excede minutos, nunca supera topes de DOMS,
nunca deja déficit crítico sin cubrir, nunca prescribe equipamiento no disponible.

---

## 9. Decisiones tomadas (2026-09-01)

1. **Repositorio propio**, no subcarpeta de hari2. Se desarrolla de forma
   autocontenida y se extrae con `git subtree split` cuando exista el repo destino.
2. **Revisión semanal con `claude -p`** ejecutado por cron en el host de unraid, contra
   la API de la app. El contenedor no lleva el CLI ni credenciales de Claude.
3. **Apple Health como fuente de cardio**, vía push del teléfono (ver §3.5.1). Tests
   manuales de VO2 igualmente, porque el dato de Apple solo se actualiza al aire libre.
4. **Entrenamiento oportunista**: sin cuotas semanales; modelo de frescura (§3.1).

## 10. Decisiones abiertas

1. Health Auto Export (de pago, robusto) vs Atajos (gratis, frágil) para el push.
2. ¿Modo "gimnasio desconocido" (hotel, vacaciones) con inventario ad-hoc?
3. Nombre de la aplicación y del repositorio.
4. ¿Interesa un histórico importable de entrenamientos previos, o empezamos de cero?
