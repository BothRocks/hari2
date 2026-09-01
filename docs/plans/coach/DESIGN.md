# Coach — Especificación de diseño

**Versión:** 1.0 · 2026-09-01
**Estado:** especificación cerrada, lista para implementar
**Destino:** repositorio propio (nombre por decidir; en este documento, `coach`)

---

## 0. Cómo usar este documento

Este documento es la fuente única de verdad para implementar la aplicación. Está
escrito para que un agente de código pueda construirla sin contexto adicional.

- Las secciones **1–4** definen *qué* se construye y *por qué*. No se cambian sin
  discutirlo: contienen las decisiones de producto y de metodología deportiva.
- Las secciones **5–12** son la especificación técnica: esquemas, algoritmos, firmas.
  Las constantes numéricas son **valores por defecto ajustables**, no dogma; van todas
  en un único módulo de configuración (§12.3).
- La sección **13** son los invariantes que deben cubrir los tests. Si una decisión de
  implementación entra en conflicto con un invariante, gana el invariante.
- La sección **15** documenta lo que se descartó y por qué. Consúltala antes de
  "mejorar" el diseño: puede que ya se evaluara y se rechazara.

**Prioridad de implementación:** §14 define las fases. P0 debe ser usable el primer día.

---

## 1. Contexto

### 1.1 Usuario

Un único usuario. Varón, 54 años. Historial de CrossFit (buena técnica en barra,
kettlebell y movimientos complejos; tolera variedad) y de programas 5x5 (progresó, pero
se aburrió y llegó a mesetas rápidamente). Vuelve al gimnasio tras un parón.

No es un producto multiusuario. No hay registro, ni planes, ni onboarding. Cualquier
decisión de diseño que asuma "usuarios" en plural es incorrecta.

### 1.2 Objetivos, en orden estricto de prioridad

1. **Fortalecer core y espalda.** Es el objetivo fundamental.
2. **Mejorar movilidad y agilidad.**
3. **Mejorar VO2máx.**

Este orden se codifica literalmente en los pesos de prioridad del motor (§4.1). Cuando
haya que recortar una sesión por falta de tiempo, se recorta desde el objetivo 3 hacia
el 1, nunca al revés.

### 1.3 Restricciones

| Restricción | Origen | Implicación |
|---|---|---|
| **"No quiero agujetas todos los días. Me desanima."** | Explícita del usuario | El daño muscular es una variable de primera clase con presupuesto y tope (§4.3), no un efecto secundario aceptable |
| **"5x5 me aburre y llego a plateau rápido"** | Explícita | Rotación controlada de variantes + progresión autorregulada (§4.2). La variedad es una restricción del motor, no un accidente |
| **Entrenamiento oportunista** | Explícita | No hay calendario ni cuotas semanales. La sesión se genera en el momento (§4.1) |
| **Edad 54** | Contexto | Prioridad a la potencia (primera cualidad que se pierde), cardio de bajo impacto, recuperación más lenta, cero trabajo al fallo sistemático |

### 1.4 Contextos de entrenamiento

- **`gimnasio`**: barra olímpica, discos, rack, banco, mancuernas, kettlebells, barra de
  dominadas, remo/bici estática. **Preferencia fuerte por peso libre.** Las máquinas
  solo aparecen como último recurso (§5.3).
- **`casa`**: **cero equipamiento**. Únicamente peso corporal. No se asume ni una
  banda elástica ni una barra de dominadas.
- **`fuera`** (opcional, P3): peso corporal + espacio exterior para caminar/correr.

---

## 2. Principios de diseño (invariantes de producto)

1. **El motor es determinista; la IA no está en el camino crítico.** Un LLM decidiendo
   volumen propone 25 series de espalda un día y cero el resto de la semana. Las cuentas
   —series por patrón, minutos, presupuesto de daño— son aritmética, y van en código.
   La IA aporta en variantes, redacción, conversación y revisión periódica.
2. **La sesión siempre se entrega.** Sin API key, sin internet, con el LLM caído: el
   motor produce una tabla válida. Toda función de IA es degradable a un camino
   determinista.
3. **Fricción cero o la app se abandona.** Pedir entrenamiento debe costar una frase.
   Registrar debe costar un mensaje. Ninguna pantalla de configuración obligatoria.
4. **Nunca hay deuda ni culpa.** El sistema no reprocha sesiones perdidas ni acumula
   déficits que "hay que compensar". Compensar déficits acumulados es precisamente lo
   que genera agujetas.
5. **Todo lo que decide el motor es explicable.** Cada elección guarda su razón
   (`generation_meta`). El usuario puede preguntar "¿por qué hoy dominadas?" y obtener
   una respuesta real, no una racionalización del LLM.
6. **Sin lock-in.** Exportación e importación completas en JSON. El histórico es del
   usuario.

---

## 3. Arquitectura

### 3.1 Componentes

```
   ┌──────────────────────────────────────────────┐
   │  coach  (contenedor Docker en unraid)        │
   │                                              │
   │   FastAPI                                    │
   │    ├── servidor MCP  (HTTP/SSE)  ◄───────────┼──── OpenClaw
   │    ├── POST /api/health/ingest   ◄───────────┼──── iPhone (Apple Health)
   │    ├── GET  /s/{token}           ◄───────────┼──── mini-web de registro (P3)
   │    └── /api/export | /api/import             │
   │                                              │
   │   Motor determinista  ── SQLite (/data)      │
   └──────────────────────────────────────────────┘
                    ▲
                    │  MCP
   ┌────────────────┴─────────────────┐
   │  OpenClaw + SOUL.md              │
   │   ├── canal Telegram             │──────────►  usuario
   │   └── cron semanal: revisión     │
   └──────────────────────────────────┘
```

**`coach`** es un servicio headless. No tiene interfaz propia en P0–P2: expone sus
capacidades como herramientas MCP y como endpoints HTTP.

**OpenClaw** es el canal. Agente self-hosted con heartbeat/cron, plugin de Telegram y
conexiones MCP. Aporta la conversación y la proactividad.

### 3.2 La regla que sostiene toda la arquitectura

> **El agente no programa entrenamientos.** Llama a `generate_session(...)` y recibe la
> tabla ya calculada. Traduce lenguaje natural a llamadas de herramienta y redacta el
> resultado. No decide series, ni cargas, ni ejercicios.

Si el agente razonara sobre programación, el sistema perdería el control del volumen y
del daño muscular, que son exactamente las dos cosas que el usuario pidió controlar.
Esta regla se refuerza en tres sitios: el prompt del agente (§9), la validación de
salida (§11.3) y los tests (§13).

### 3.3 Flujo de una sesión

```
usuario: "voy a entrenar, tengo 45 min, en el gimnasio, hecho polvo"
   │
   ├─ OpenClaw interpreta → generate_session(minutos=45, lugar="gimnasio",
   │                                          estado="cansado")
   │
   ├─ motor:  1. estado: frescura por cualidad, fatiga por grupo, readiness
   │          2. plantilla por minutos → bloques y presupuesto de tiempo
   │          3. ranking de cualidades → asignación a slots
   │          4. selección de ejercicio por slot (equipamiento, daño, novedad, hastío)
   │          5. prescripción (series/reps/carga/RIR/descanso) desde el histórico
   │          6. ajuste de tiempo hasta encajar en el presupuesto
   │          7. persiste sesión + generation_meta
   │
   ├─ OpenClaw formatea la tabla (monoespaciada, ≤35 col) y la envía por Telegram
   │
   ├─ durante: "el rack está ocupado" → swap_exercise(...)
   │
   ├─ al acabar: "hecho todo, remo a 30, la última de press me costó"
   │             → log_sets(...) + finish_session(...)
   │
   └─ al día siguiente: "¿agujetas?" → record_soreness(...) → recalibra doms_risk personal
```

### 3.4 Stack

| Capa | Elección | Motivo |
|---|---|---|
| Lenguaje | Python 3.12 | Ecosistema del motor y del SDK de MCP |
| Framework | FastAPI | Sirve API HTTP y monta el servidor MCP en el mismo proceso |
| ORM / migraciones | SQLAlchemy 2.0 (async) + Alembic | |
| BD | **SQLite** (aiosqlite), fichero en `/data` | Un usuario. Backup = copiar un fichero. Postgres es complejidad sin retorno aquí |
| MCP | SDK oficial `mcp`, transporte HTTP/SSE | OpenClaw corre en otro proceso/contenedor; stdio no vale |
| Dependencias | `uv` | |
| Tests | pytest + hypothesis (property tests, §13) | |
| Contenedor | Imagen única, `docker-compose.yml` + plantilla unraid | |

**Sin autenticación de usuario.** Token compartido en cabecera para `/api/health/ingest`
y para MCP. Pensado para LAN o Tailscale. No exponer a internet sin proxy inverso.

---

## 4. Metodología de entrenamiento

Esta sección es el núcleo del producto. Si el modelo de entrenamiento está mal, la app
es una interfaz agradable sobre malos consejos.

### 4.1 Modelo de frescura (sustituye a cuotas y a calendario)

No hay "día de espalda" ni objetivo semanal. Cada **cualidad** tiene un reloj: cuánto
hace que no se entrena y a qué velocidad caduca. La sesión de hoy ataca lo más rancio y
más prioritario que quepa en el tiempo disponible.

```
frescura(c) = 1 − exp(−días_desde_última_exposición(c) / τ(c))
score(c)    = prioridad(c) × frescura(c) × puerta_fatiga(c) × encaje_readiness(c)
```

**Tabla de cualidades** (`quality`), con prioridad y τ por defecto:

| Cualidad | Prioridad | τ (días) | Objetivo | Notas |
|---|---|---|---|---|
| `core_antiext` | 1.00 | 1.5 | 1 | Anti-extensión (bird dog, dead bug, rueda) |
| `core_antirot` | 1.00 | 1.5 | 1 | Anti-rotación (pallof, lanzamientos) |
| `core_antilat` | 0.95 | 2.0 | 1 | Anti-flexión lateral (side plank, suitcase carry) |
| `pull_horizontal` | 0.95 | 3.0 | 1 | Remos |
| `pull_vertical` | 0.90 | 3.5 | 1 | Dominadas, jalones |
| `hinge` | 0.85 | 4.0 | 1 | Peso muerto, RDL, swing. Alta prioridad, recuperación lenta |
| `mobility` | 0.85 | 1.0 | 2 | La cualidad más perecedera |
| `power` | 0.70 | 4.0 | 2 | Saltos, lanzamientos, swings explosivos |
| `agility` | 0.65 | 5.0 | 2 | Cambios de dirección, gateos, coordinación |
| `vo2` | 0.65 | 3.5 | 3 | Intervalos duros |
| `carry` | 0.60 | 4.0 | 1 | Core + espalda + agarre con daño muscular ≈ 0 |
| `balance` | 0.60 | 3.0 | 2 | Apoyo unipodal, propiocepción. Coste de fatiga ≈ 0 |
| `squat` | 0.60 | 4.5 | — | Base |
| `lunge` | 0.55 | 5.0 | — | Unilateral, también equilibrio |
| `z2` | 0.55 | 3.0 | 3 | Puede cubrirse con actividad externa |
| `push_horizontal` | 0.45 | 5.0 | — | Equilibrio estructural, no objetivo |
| `push_vertical` | 0.45 | 5.0 | — | Vigilar hombro |

**Por qué frescura y no cuotas semanales.** Con entrenamiento oportunista, una cuota
("9 series de espalda esta semana") produce dos patologías. Si se entrena poco, se
acumula deuda y el sistema intenta meterla a martillazos en la siguiente sesión — que
es exactamente el mecanismo que genera agujetas. Si se entrena mucho, la cuota se agota
y el motor repite. El modelo de frescura **se autonormaliza**: entrenando 6 días todo
está fresco, así que las sesiones salen variadas y de menor volumen por cualidad;
entrenando 2, cada sesión va directa a lo prioritario y rancio. Nunca hay deuda.

El **volumen por sesión** se calibra con la frecuencia real observada: media móvil
exponencial de sesiones/semana de las últimas 4 semanas (`observed_frequency`), para que
entrenar 2 días no signifique intentar meter la semana entera en cada sesión.

```
volume_factor = clamp(0.75 + 0.10 × (4 − observed_frequency), 0.75, 1.25)
```

### 4.2 Anchors y progresión

**La tensión**: rotar mucho da variedad pero hace la progresión inmedible; rotar poco es
volver al 5x5. Se resuelve separando en dos capas.

**Capa 1 — Anchors (4–5 ejercicios fijos, 8–12 semanas).** Son la métrica de progreso.

| Anchor propuesto | Cualidad | Progresión |
|---|---|---|
| Peso muerto con barra hexagonal (o RDL con barra) | `hinge` | Doble progresión 5–8 |
| Front squat con barra (o goblet squat con KB) | `squat` | Doble progresión 5–8 |
| Dominada lastrada (o con banda/negativas) | `pull_vertical` | Doble progresión 4–8 |
| Remo con mancuerna apoyado en banco | `pull_horizontal` | Doble progresión 8–12 |
| Press militar con mancuernas | `push_vertical` | Doble progresión 6–10 |
| **Clean (o clean & jerk / snatch)** | `power`, `hinge` | **Máximo técnico del día** (§4.2.1) |

*Los anchors son configurables y revisables cada mesociclo. La lista es un punto de
partida razonado, no una imposición: cubre los objetivos 1 y 2, usa peso libre y evita
cargar la columna con volumen alto.*

**Doble progresión**: se trabaja en un rango de repeticiones. Cuando la serie principal
alcanza el techo del rango con RIR ≥ 2, se sube la carga (+2.5 kg en tren superior,
+5 kg en tren inferior) y se vuelve al suelo del rango.

**Estimación de 1RM** (para graficar tendencia y detectar mesetas):

```
e1RM = carga × (1 + (reps + RIR) / 30)          # Epley corregido por RIR
```

**Capa 2 — Accesorios y acondicionamiento: rotación libre.** Aquí vive la variedad.
Cambian cada 2–3 semanas dentro de la misma familia de patrón. Aquí es donde el LLM
aporta al elegir variantes.

#### 4.2.1 Progresión de los levantamientos olímpicos

Clean, clean & jerk y snatch **no** progresan por doble progresión: no admiten series a
repeticiones altas y su factor limitante es técnico, no de fuerza máxima. Necesitan su
propio modelo, marcado en el catálogo como `tipo_progresion: olimpico`.

**Prescripción**: 5–6 series de 1–3 repeticiones, subiendo hasta un **single técnico del
día a RPE 7–8** (barra rápida, recepción limpia), seguido de 2–3 dobles de descarga al
~90 % de ese single.

**Corte por calidad**: el ejercicio termina cuando cae la velocidad de barra o falla la
técnica, aunque queden series. Esto se prescribe explícitamente en el texto del item
("para cuando pierdas velocidad") y el agente debe transmitirlo.

**Métrica de progreso**: el single técnico más pesado con RPE ≤ 8. **No se calcula e1RM
por Epley** para estos ejercicios; la fórmula no tiene sentido aquí y produciría
tendencias falsas.

**Reintroducción tras un parón** (4–6 semanas antes de las recepciones profundas):

```
hang power clean → power clean → clean
hang power snatch → power snatch → snatch
```

Las variantes `power` (recepción por encima del paralelo) exigen mucha menos movilidad
de hombro y tobillo y reducen la exposición lumbar desde el suelo.

**Reglas duras** (ver invariante 15, §13):

- Nunca más de 3 repeticiones por serie.
- Nunca en circuito, en metcon ni a repeticiones altas bajo fatiga. Es el patrón que
  más lesiones produce en atletas veteranos, y viene heredado del CrossFit.
- Siempre en el primer bloque de trabajo, tras el calentamiento, y nunca después de
  sentadilla o peso muerto pesados.
- Solo con `readiness ≥ 60`.

**Por qué encajan tan bien en este sistema:** son casi puramente concéntricos —la
excéntrica es mínima o inexistente— así que su daño muscular es muy bajo pese a ser
exigentes. `doms_risk: 2`. Fatigan al sistema nervioso, no al músculo. Para alguien que
no quiere agujetas pero sí quiere entrenar potencia con barra, son óptimos.

**Detección de meseta.** Con ≥ 3 exposiciones al anchor, si la pendiente de regresión
lineal del e1RM sobre las últimas 4 exposiciones es ≤ 0, se escala en este orden:

1. Cambiar el rango de repeticiones (5–8 → 8–12, o → 3–5).
2. Cambiar a una variante hermana de la misma familia, manteniendo el seguimiento de
   e1RM a nivel de familia.
3. Semana de descarga.

**Descarga (deload).** Automática cada 5–6 semanas, o disparada antes si la tendencia de
readiness cae o la de RPE sube de forma sostenida. Volumen × 0.6, intensidad mantenida,
cero ejercicios nuevos.

**Índice de hastío.** Si un ejercicio accesorio ha aparecido más de 4 veces en las
últimas 3 semanas, se penaliza su score. La variedad es una restricción explícita.

### 4.3 Modelo de daño muscular (DOMS)

La restricción diferencial del producto. Las agujetas provienen sobre todo de:
**novedad** del ejercicio, **carga excéntrica**, **carga en posición estirada**,
**volumen** y **proximidad al fallo**. El catálogo etiqueta cada ejercicio con un
`doms_risk` base (1–5) derivado de esas dimensiones.

**Coste de daño de una serie efectiva:**

```
damage(ejercicio, serie) = doms_risk_efectivo × novelty_mult × intensity_mult

doms_risk_efectivo = doms_risk_personal si existe, si no doms_risk base

novelty_mult   = 1.5  si nunca se ha hecho o hace > 8 semanas
                 1.2  si sólo hay 1 exposición previa
                 1.0  en otro caso

intensity_mult = 1.3  si RIR ≤ 1
                 1.0  si RIR 2–3
                 0.8  si RIR ≥ 4
```

**Reglas duras del motor:**

1. **Máximo 1 ejercicio nuevo por sesión**, y su primera exposición se prescribe al
   **60 % del volumen** habitual. *Esta es la regla que resuelve el 80 % del problema:
   las agujetas casi siempre son "hice algo nuevo con volumen normal".*
2. **Tope de daño rodante de 7 días por grupo muscular**: `Σ damage ≤ DAMAGE_CAP`
   (por defecto 30 para grupos prioritarios —espalda, core—, 20 para el resto).
   Al superarse, ese grupo solo recibe trabajo de bajo daño: isométrico, rango corto,
   concéntrico dominante, carries.
3. **RIR objetivo por defecto 2–3.** El fallo se reserva a 1–2 series principales por
   semana y **nunca** en ejercicios con `doms_risk ≥ 4`.

**Fatiga por grupo muscular**, con decaimiento exponencial:

```
fatiga(g) ← fatiga(g) × 0.5 ^ (horas_transcurridas / 40)     # vida media 40 h
fatiga(g) ← fatiga(g) + carga_de_la_sesión(g)
```

Si `fatiga(g) > FATIGUE_GATE`, el grupo queda excluido del trabajo pesado en la
generación (`puerta_fatiga` = 0 para las cualidades que lo cargan).

**Calibración personal (el bucle que hace único al sistema).** Al día siguiente de
entrenar, el agente pregunta por agujetas (mapa corporal simple, 0–3 por grupo). Con esa
respuesta:

```
si agujetas(g) ≥ 2 dentro de las 48 h siguientes a la sesión S:
    para cada ejercicio de S que carga g:
        doms_risk_personal += 0.3        (media móvil, clamp 1–5)

si agujetas(g) == 0 de forma repetida:
    doms_risk_personal -= 0.1            (converge hacia el valor base)
```

En 4–6 semanas el sistema conoce la tolerancia real del usuario, no la media
poblacional. Esto es lo que convierte "sin agujetas" en una promesa cumplible.

### 4.4 Readiness

Se calcula automáticamente cuando hay datos de Apple Health (§10); es opcional y
saltable si no los hay.

```
readiness = clamp(50 + 15×z_hrv − 10×z_fc_reposo + 10×factor_sueño + ajuste_subjetivo, 0, 100)

z_*            = desviación frente a línea base de 60 días
factor_sueño   = (horas_sueño − 7) / 1.5, clamp −1.5..1.5
ajuste_subjetivo = −15 "reventado" / 0 normal / +10 "fuerte"   (del texto del usuario)
```

| Readiness | Efecto |
|---|---|
| < 40 | Día flojo: **caminata de 5–10k pasos** + movilidad + core ligero. Sin potencia, sin VO2, sin cargas altas |
| 40–60 | Volumen × 0.8. Sin series al fallo. Sin ejercicios nuevos |
| 60–80 | Normal |
| > 80 | Permite serie principal pesada y/o intervalos VO2 duros |

### 4.5 Plantillas por tiempo disponible

Presupuestos de minutos por bloque. La suma **nunca** puede excederse (§13, invariante 1).

| Min | Lugar | Bloques |
|---|---|---|
| 15 | gimnasio | calentamiento 3 · core 6 · carry 4 · enfriamiento 2 |
| 15 | casa | movilidad 8 · core 7 |
| 20–25 | gimnasio | calentamiento 5 · anchor 12 · core 5 |
| 20–25 | casa | movilidad 7 · circuito core/espalda 13 |
| 30–35 | gimnasio | calentamiento 6 · anchor 14 · superserie accesoria 9 · core 5 |
| 30–35 | casa | movilidad 7 · circuito 15 · intervalos sin impacto 10 |
| 45 | gimnasio | calentamiento 8 · anchor 15 · superserie accesoria 12 · finisher core/carry 8 |
| 45 | casa | movilidad 10 · circuito 20 · intervalos 12 |
| 60 | gimnasio | calentamiento 8 · anchor 16 · 2º patrón 12 · accesorios 14 · core 8 |
| 75+ | gimnasio | lo anterior + bloque de acondicionamiento (Z2 o VO2) 15 |

**Estimación de tiempo** (constante y auditable):

```
tiempo_serie   = reps × 3.5 s   (o los segundos prescritos en isométricos)
descanso       = 150–180 s anchors · 60–90 s accesorios · 45 s core · 30 s movilidad
superserie     = descanso efectivo entre pares ÷ 2
transición     = 60 s entre ejercicios (90 s si requiere montar barra)
calentamiento  = según plantilla, específico de los patrones del día
```

### 4.6 Cardio: Z2 y VO2

- **Modalidad de bajo impacto por defecto**: remo, bici, assault bike, cinta inclinada,
  comba. A los 54, los intervalos corriendo son la vía rápida a la lesión.
- **Protocolos VO2**: 4×4 noruego (4 min al 90–95 % FCmáx / 3 min suave), 30/30 de
  Billat, 10-20-30. **Máximo 2 por semana, nunca en días consecutivos, y nunca el día
  siguiente a un `hinge` pesado** (interferencia y fatiga acumulada).
- **Z2**: 60–120 min semanales deseables, cubribles con actividad externa (paseo, bici)
  importada desde Apple Health, sin generar sesión.
- **Test mensual**: Cooper de 12 min, o 5 min máximos en remo, o FC de reposo + HRR.
  Necesario porque el VO2máx que estima Apple **solo se actualiza al aire libre**
  (§10.3), y el cardio recomendado aquí es mayoritariamente indoor.

### 4.7 Core, movilidad, potencia y agilidad

**Core: los McGill Big 3 como columna vertebral.** Curl-up, side plank y bird dog. Son
isométricos, progresan por **densidad** (tiempo y repeticiones, no carga) y su daño
muscular es prácticamente nulo. Atacan exactamente el objetivo 1 y se pueden
microdosificar en el calentamiento de *toda* sesión de gimnasio, además de ser el núcleo
de las sesiones cortas en casa. Es la forma más barata de cumplir "core y espalda" sin
generar agujetas.

Progresión por pirámide descendente (McGill): 6/4/2 repeticiones de 10 s de sostén,
aumentando series o segundos antes que dificultad.

**Espalda**: prioridad al volumen de tracción horizontal, con preferencia por variantes
con apoyo en banco (menor fatiga lumbar acumulada); tracción vertical; y trabajo
postural de bajo daño (face pulls, aperturas con banda, y sin banda en casa: YTW en
suelo). Los erectores se entrenan con el patrón `hinge` y con carries, no con volumen
alto de hiperextensiones.

**Movilidad**: calentamiento **específico de los patrones del día** (nunca "5 min de
bici") + un flow de 6–10 min (CARs, 90/90, cossack, rotación torácica, dorsiflexión de
tobillo) que además es la sesión de casa por defecto cuando hay poco tiempo.

**Potencia y agilidad, en dosis pequeñas y siempre en fresco** (principio de sesión,
readiness ≥ 60): saltos bajos, lanzamientos de balón medicinal (potencia + anti-rotación
en un solo movimiento), swings de kettlebell, cambios de dirección, gateos, y *Turkish
get-up*, que combina movilidad, core y control en una sola pieza y encaja especialmente
bien con el perfil ex-CrossFit.

### 4.8 Preferencias explícitas del usuario

Estas preferencias son datos de producto, no sugerencias. El catálogo semilla debe
incluir todo lo listado aquí, y el motor debe poder programarlo.

**Le gustan y quiere hacerlos:**

| Ejercicio | Cualidades | Tratamiento |
|---|---|---|
| Turkish get-up | `core_antilat`, `mobility`, `balance` | Ya contemplado. Excelente encaje: tres cualidades en un movimiento, daño muscular bajo |
| Clean, clean & jerk, snatch | `power`, `hinge` | Anchor de `power` con progresión propia (§4.2.1) |
| Dragon flag | `core_antiext` | **Escalera de progresión obligatoria** (§5.4). `doms_risk: 5` |
| Caminar 5–10k pasos | `z2` | Contenido por defecto de los días flojos y de baja readiness |

**Preferencia general por la barra.** A igualdad de score en un slot de `hinge`,
`squat`, `power` o `push_vertical`, el motor prefiere variantes con barra olímpica sobre
mancuerna o kettlebell (multiplicador 1.15). No aplica a `pull_horizontal`, donde las
variantes con apoyo son preferibles por fatiga lumbar acumulada.

**No le interesa:** trabajo de máquinas (§5.3), prácticas de bajo estímulo tipo qi gong
(prefiere caminar), y programas de estructura fija tipo 5x5 (§1.3).

**Reacciones adversas conocidas:** el **remo con barra inclinado** le produce mareo
ocasional, atribuible a Valsalva sostenida en posición inclinada. Penalizado a 0.4
(§5.5) y con cue de respiración obligatorio. Se prefieren variantes con apoyo, que ya
eran preferibles por fatiga lumbar: remo con mancuerna apoyado, seal row, remo con
apoyo en pecho. Esto refuerza la excepción de §4.8 a la preferencia por barra en
`pull_horizontal`. Ejercicio con barra por defecto en ese patrón: **seal row** (§5.5.1).

---

## 5. Catálogo de ejercicios

### 5.1 Esquema

El catálogo vive en YAML versionado (`data/exercises/*.yaml`) y se carga a la BD en el
arranque. Se versiona en git para poder revisarlo a mano: es el activo más valioso del
sistema y no debe generarse sin supervisión humana.

```yaml
- slug: remo_mancuerna_banco
  nombre: Remo con mancuerna apoyado en banco
  patrones: [pull_horizontal]          # cualidades que cubre (1..n)
  equipamiento: [mancuerna, banco]     # ver §5.3
  lugares: [gimnasio]
  unilateral: true
  tipo_carga: externa                  # externa | corporal | isometrica | tiempo
  doms_risk: 2                         # 1-5, ver §4.3
  estres_articular: {hombro: 1, lumbar: 1, rodilla: 0, codo: 1}   # 0-3
  skill: 1                             # 1 fácil .. 3 técnico
  es_core: false
  es_potencia: false
  rango_reps: [8, 12]
  seg_por_rep: 3.5
  descanso_seg: 75
  familia: remo                        # para sustituciones y progresión
  progresion_de: [remo_invertido]      # más fácil
  progresion_a: [remo_pendlay]         # más difícil
  cues:
    - "Costillas hacia abajo, no rotes el torso"
    - "Tira con el codo, no con la mano"
  cues_siempre:                        # se muestran sin que el usuario los pida
    - "Respira por repetición: coge aire abajo, suelta al bajar la barra"
  penalizacion_usuario:                # §5.5, ausente por defecto
    factor: 1.0
    motivo: null
  video: null
```

### 5.2 Taxonomía de cualidades

Los `patrones` de un ejercicio deben ser valores del enum `quality` de §4.1. Un
ejercicio puede cubrir varias: el *Turkish get-up* es
`[core_antilat, mobility, agility]`; el suitcase carry es `[carry, core_antilat]`.

### 5.3 Equipamiento y filtrado por lugar

```
gimnasio → barra, discos, rack, banco, mancuerna, kettlebell, barra_dominadas,
           remo_ergometro, bici, comba, balon_medicinal, [maquina]
casa     → ninguno (solo peso corporal)
fuera    → ninguno + exterior
```

**Preferencia por peso libre**: los ejercicios con `equipamiento: [maquina]` reciben un
multiplicador de 0.4 en el score de selección. Aparecen solo si no hay alternativa libre
disponible (por fatiga, daño o hastío).

**Casa significa cero equipamiento.** No se prescribe nada que requiera banda, barra de
dominadas o mochila lastrada. Si el catálogo no tiene suficientes opciones corporales
para una cualidad, esa cualidad simplemente no se programa en casa (típicamente
`pull_vertical`, que en casa se sustituye por trabajo escapular y de espalda en suelo).

### 5.4 Escaleras de progresión: el caso de la dragon flag

Algunos ejercicios no pueden prescribirse directamente aunque el usuario los pida. La
dragon flag es el ejemplo canónico y sirve de plantilla para el resto:

```
dead bug → hollow hold → hollow rock → dragon flag agrupada (rodillas al pecho)
         → dragon flag a una pierna → dragon flag en straddle → dragon flag completa
```

**Criterio de avance**: 3 series limpias en el techo del rango del escalón actual, sin
pérdida de posición lumbar, en dos sesiones consecutivas.

**Por qué importa**: la dragon flag es **casi enteramente excéntrica** —el ejercicio *es*
el descenso controlado—, que es el perfil de mayor producción de agujetas que existe.
Además, si la cadera cede, carga la lumbar en extensión, lo cual es inaceptable para un
usuario cuyo objetivo número uno es una espalda sana. `doms_risk: 5`,
`estres_articular: {lumbar: 2}`.

Las reglas generales del motor ya la gestionan correctamente sin excepciones: máximo un
ejercicio nuevo por sesión, primera exposición al 60 % del volumen, y tope de daño
rodante. La escalera solo añade la restricción de que no se puede saltar a un escalón
sin haber consolidado el anterior.

Se modela con los campos `progresion_de` / `progresion_a` del catálogo (§5.1) más un
campo `requiere_escalon: true`, que impide que el motor seleccione el ejercicio si el
escalón previo no está consolidado.

### 5.5 Reacciones adversas: penalización por ejercicio

Un ejercicio puede sentar mal al usuario por razones que no captura `estres_articular`:
mareo, náusea, sensación de inestabilidad, un patrón que agrava una molestia antigua.
El sistema debe recordarlo y actuar, no solo anotarlo.

Cada ejercicio tiene `penalizacion_usuario: {factor, motivo}`, que multiplica su score
de selección (§6, paso 5):

| Severidad reportada | Factor | Efecto |
|---|---|---|
| leve ("no me convence", "prefiero otro") | 0.7 | Sale menos, sigue disponible |
| media ("me sienta regular", "me marea un poco") | 0.4 | Solo si no hay alternativa en su patrón |
| alta ("me hace daño", "no lo quiero hacer") | 0.0 | Excluido; solo reaparece si el usuario lo reactiva |

Se fija con la herramienta `flag_exercise` (§8), que el agente **debe** llamar siempre
que el usuario reporte una reacción adversa, además de guardar la nota. La penalización
es persistente y revisable: aparece en `get_status` y la revisión semanal (§11) puede
proponer reactivar un ejercicio penalizado hace meses, nunca aplicarlo por su cuenta.

**Penalizaciones semilla** (de la conversación de diseño):

| Ejercicio | Factor | Motivo |
|---|---|---|
| Remo con barra inclinado | 0.4 | Mareo por **sobre-braceo**: inseguridad postural lumbar → Valsalva sostenida en posición inclinada. Revisable (§5.5.1) |

#### 5.5.1 Caso del remo con barra: causa y solución

El usuario reporta mareo **solo** en el remo con barra inclinado, y describe ir "un poco
agobiado con la espalda" al hacerlo. Ambas cosas son el mismo fenómeno: la inseguridad
sobre la posición lumbar produce un **braceo excesivo y sostenido** —apretar se siente
como protegerse— que equivale a Valsalva mantenida durante toda la serie, en posición
inclinada y con la cabeza baja. El mareo es la consecuencia, no la causa.

**Implicación de diseño**: esto no se corrige con un cue de respiración, porque el cue
no elimina el motivo del braceo. Se corrige con **soporte del torso**. Si la columna no
sostiene la posición, no hay nada que vigilar, no hay razón para apretar y la
respiración se libera sola.

**Tracción horizontal con barra por defecto: seal row** (tumbado boca abajo en banco
elevado). Conserva la barra olímpica —preferencia explícita del usuario— con la columna
descargada, imposibilidad mecánica de redondear y sin impulso de cadera. Alternativas si
no hay banco elevado disponible: remo con apoyo en pecho en banco inclinado, remo con
mancuerna con mano apoyada.

**Condición de revisión**: la penalización no es permanente. Tras ≥ 8 semanas de trabajo
consolidado de `core_antiext`, `carry` y `hinge`, la revisión semanal (§11) **debe
proponer** reevaluar el remo con barra inclinado con series de 6–8 repeticiones y
respiración por repetición. La inseguridad postural es entrenable y se espera que
remita; vetar el ejercicio de por vida sería un falso positivo.

**Cues obligatorios.** Cuando el fallo de un ejercicio es de ejecución y no de carga
—típicamente la respiración—, el cue va en `cues_siempre` y el agente lo muestra sin que
se lo pidan. El remo con barra, el peso muerto y todo lo que implique Valsalva en
posición inclinada llevan cue de respiración obligatorio.

### 5.6 Volumen del catálogo

Semilla objetivo: **120–150 ejercicios**, repartidos de forma que ninguna cualidad
prioritaria tenga menos de 6 opciones por lugar. Mínimo por cualidad en `casa`: 4.
Sin esa densidad, el índice de hastío (§4.2) no tiene de dónde elegir y el sistema se
vuelve repetitivo — que es justo el fallo del 5x5 que hay que evitar.

---

## 6. Algoritmo de generación

```
FUNCIÓN generar_sesión(minutos, lugar, estado_texto?, fecha=ahora):

  1. ESTADO
     readiness      ← §4.4 (Apple Health + ajuste del texto del usuario)
     frescura[c]    ← para cada cualidad, §4.1
     fatiga[g]      ← para cada grupo muscular, con decaimiento aplicado, §4.3
     daño_7d[g]     ← suma rodante de daño de los últimos 7 días
     volume_factor  ← §4.1
     deload?        ← §4.2

  2. PLANTILLA
     bloques ← plantilla(minutos, lugar)               # §4.5
     presupuesto_min[bloque] ← de la plantilla

  3. RANKING DE CUALIDADES
     para cada cualidad c:
         puerta_fatiga(c)   ← 0 si algún grupo principal de c supera FATIGUE_GATE
                              o si daño_7d de ese grupo supera DAMAGE_CAP
         encaje_readiness(c)← 0 si readiness<60 y c ∈ {power, vo2}
                              0 si readiness<40 y c ∉ {mobility, z2, core_*}
         score(c) ← prioridad(c) × frescura(c) × puerta_fatiga(c) × encaje_readiness(c)

     REGLAS DURAS adicionales:
         vo2 ← 0 si hubo vo2 en las últimas 48 h
         vo2 ← 0 si hubo hinge pesado en las últimas 24 h
         power/agility solo en el primer bloque de trabajo

  4. ASIGNACIÓN A SLOTS
     - Todo bloque de calentamiento incluye movilidad específica de los patrones
       que se van a entrenar más una microdosis de McGill Big 3.
     - Slot "anchor" (si minutos ≥ 20 y hay bloque de fuerza): el anchor cuya cualidad
       tenga mayor score y cuya puerta de fatiga esté abierta.
     - Slots restantes: cualidades por score descendente, sin repetir grupo muscular
       principal más de 2 veces, y garantizando ≥ 1 slot de core en toda sesión.

  5. SELECCIÓN DE EJERCICIO POR SLOT
     candidatos ← catálogo filtrado por (cualidad, lugar, equipamiento,
                                          estrés_articular vs dolores activos,
                                          skill ≤ nivel_usuario)
     para cada candidato e:
         score(e) = encaje_patrón(e)
                  × (1 − hastío(e))            # §4.2
                  × (1 − coste_daño(e))        # §4.3, normalizado 0..1
                  × pref_peso_libre(e)         # 1.0 libre, 0.4 máquina
                  × pref_barra(e)              # 1.15 barra en hinge/squat/power/press
                  × penalizacion_usuario(e)    # §5.5, reacciones adversas
                  × disponibilidad_progresión(e)
     elegir el de mayor score
     RESTRICCIÓN: máximo 1 ejercicio con novelty_mult > 1.0 en toda la sesión

  6. PRESCRIPCIÓN
     anchors      → doble progresión desde el histórico; serie principal + back-offs
     accesorios   → series/reps del rango del catálogo, RIR 2-3, carga = última + ajuste
     core         → progresión por densidad (§4.7)
     acondicionam.→ protocolo de §4.6
     TODO ajustado por volume_factor y por el modificador de readiness
     Si el ejercicio es nuevo → volumen × 0.6

  7. AJUSTE DE TIEMPO
     mientras tiempo_estimado > minutos:
         recortar por la cola, empezando por la cualidad de menor prioridad
         (primero series, luego el ejercicio entero)
     INVARIANTE: tiempo_estimado ≤ minutos, siempre

  8. PERSISTIR
     sesión + bloques + items + generation_meta {
         frescura, fatiga, readiness, por_qué_cada_slot, candidatos_descartados
     }
     RETORNAR sesión
```

**Determinismo y variedad.** El motor es determinista dado el estado; la variedad no
viene de aleatoriedad sino del índice de hastío y de la rotación de familias. Para
desempates se usa una semilla derivada de `(fecha, session_id)`, que se guarda en
`generation_meta` para poder reproducir una generación exactamente.

---

## 7. Modelo de datos

```
exercise
  id, slug, nombre, patrones[], equipamiento[], lugares[], unilateral,
  tipo_carga, doms_risk, doms_risk_personal, estres_articular{}, skill,
  es_core, es_potencia, rango_reps[], seg_por_rep, descanso_seg,
  familia, progresion_de[], progresion_a[], cues[], video

policy
  id, versión, creada_en, creada_por (seed|revisión_llm|manual),
  prioridades{}, taus{}, anchors[], damage_caps{}, notas
  # versionada: una revisión semanal crea una versión nueva, nunca sobreescribe

session
  id, fecha, lugar, minutos_previstos, minutos_reales, readiness,
  estado (generada|en_curso|completada|abandonada), policy_id,
  generation_meta (JSON), token_web (para §12.4)

session_block
  id, session_id, orden, tipo (warmup|fuerza|accesorio|acond|core|movilidad|cooldown),
  presupuesto_min

session_item
  id, block_id, orden, exercise_id, series, reps | segundos, carga_objetivo,
  rir_objetivo, descanso_seg, es_novedad, notas, sustituido_de (exercise_id?)

set_log
  id, session_item_id, nº_serie, reps, carga, rpe, hecho, registrado_en

session_feedback
  session_id, rpe_global, disfrute (1-5), dolor_articular{}, comentario

soreness_report
  fecha, mapa{grupo: 0-3}, session_id_atribuida

muscle_state
  grupo, fatiga, daño_7d, actualizado_en

note
  id, fecha, texto, tags[]        # "el hombro derecho me molesta en press"
                                  # se inyecta como contexto en la revisión semanal
                                  # y filtra por estres_articular en la selección

metric
  id, fecha, tipo (peso|fc_reposo|hrv|sueño|vo2max_apple|test_vo2|e1rm), valor, fuente

external_activity
  id, fecha, tipo, minutos, fc_media, zona, fuente (apple_health|manual)

review
  id, fecha, ventana_analizada, entrada (JSON), salida (JSON patch),
  aplicada (bool), resumen_texto
```

**Notas de implementación:**

- `generation_meta` no es decorativo: es lo que permite responder "¿por qué hoy
  dominadas?" (principio 5, §2) y lo que hace depurable el motor.
- `policy` versionada permite revertir una revisión semanal que empeore las cosas.
- `doms_risk_personal` vive en `exercise` porque hay un solo usuario. Si algún día
  hubiera más, se movería a una tabla puente.

---

## 8. Interfaz MCP

El motor expone estas herramientas. Son la **única** superficie que consume el agente.

```
generate_session(minutos: int, lugar: "gimnasio"|"casa"|"fuera",
                 estado: str? )                       → Session
    Genera y persiste la sesión. `estado` es texto libre del usuario
    ("reventado", "con ganas") que solo modula el ajuste subjetivo de readiness.

swap_exercise(session_id: str, item_orden: int, motivo: str?) → SessionItem
    Devuelve la mejor alternativa del mismo patrón, respetando daño, fatiga y
    equipamiento. `motivo` puede contener información clínica ("me molesta el hombro"):
    si menciona una articulación, se filtra además por `estres_articular`.

log_sets(session_id: str, texto: str?, sets: SetLog[]?)     → resumen
    Acepta registro estructurado o texto libre ya interpretado por el agente.
    Idempotente por (session_item_id, nº_serie).

finish_session(session_id: str, rpe_global: int?, disfrute: int?,
               dolor: dict?, minutos_reales: int?)          → resumen + progresión
    Cierra la sesión, actualiza fatiga, daño rodante y estado de progresión de anchors.

record_soreness(mapa: dict[str, 0..3], fecha: date?)        → ok
    Recalibra `doms_risk_personal` (§4.3).

get_status()                                                → estado
    Frescura por cualidad, fatiga, readiness, tendencias de anchors, días desde
    el último test de VO2, próxima descarga prevista.

add_note(texto: str)                                        → ok
    Guarda una observación libre (molestias, preferencias, contexto).

flag_exercise(slug: str, motivo: str,
              severidad: "leve"|"media"|"alta")             → ok
    Registra una reacción adversa y penaliza el ejercicio (§5.5). El agente DEBE
    llamarla siempre que el usuario reporte que algo le sienta mal, además de add_note.

unflag_exercise(slug: str)                                  → ok
    Reactiva un ejercicio penalizado. Solo a petición explícita del usuario.

render_chart(metrica: str, ventana_dias: int = 90)          → PNG (bytes)
    Tendencia de e1RM por anchor, VO2máx, peso, readiness. El bot lo envía como imagen.

list_exercises(cualidad: str?, lugar: str?)                 → Exercise[]
    Consulta del catálogo. Solo lectura.
```

**Endpoints HTTP** (fuera de MCP): `POST /api/health/ingest` (§10),
`GET /s/{token}` (mini-web de registro, §12.4), `GET /api/export`, `POST /api/import`,
`POST /api/reviews/run` (§11).

---

## 9. Agente OpenClaw

### 9.1 Reglas de comportamiento (para `SOUL.md`)

```markdown
Eres el entrenador personal de Jorge (54 años). Hablas en castellano, directo y sin
paja. Tuteas. Nada de motivación de póster.

REGLAS DURAS
1. NUNCA inventas ejercicios, series, cargas ni progresiones. Todo entrenamiento sale
   de la herramienta `generate_session`. Si la herramienta falla, lo dices; no
   improvisas una tabla.
2. NUNCA modificas lo que devuelve el motor. Puedes reformatear y explicar; no puedes
   añadir ni quitar series.
3. Para cambiar un ejercicio usas `swap_exercise`, nunca lo eliges tú.
4. Si falta un dato para generar (minutos o lugar), haces UNA pregunta corta. Si el
   usuario no lo dice, asumes 45 minutos y preguntas solo el lugar.
5. Si el usuario menciona dolor o molestia en una articulación, lo guardas con
   `add_note` ADEMÁS de pasarlo como motivo al swap.
6. Si el usuario reporta que un ejercicio le sienta mal (mareo, molestia, náusea, o
   simplemente que no lo quiere), llamas a `flag_exercise` con la severidad que
   corresponda. No basta con anotarlo: si no lo marcas, se lo volverás a programar.
7. Los cues marcados como `cues_siempre` se muestran SIEMPRE, aunque no los pidan.
   Son los que corrigen un fallo de ejecución, no una preferencia.

FORMATO
- Las tablas van en bloque de código monoespaciado, máximo 35 caracteres de ancho.
- Sin markdown de tablas. Sin emojis decorativos.
- Cada ejercicio: nombre corto, series×reps, carga, RIR. Los cues solo si se piden.
- Al final de la tabla, UNA línea explicando la sesión ("hoy toca tirón vertical:
  llevas 5 días sin espalda").

REGISTRO
- Al terminar, el usuario escribe en lenguaje natural ("hecho todo, remo a 30, la
  última de press me costó"). Lo conviertes a `log_sets` estructurado y confirmas en
  una línea lo que has entendido. Si algo es ambiguo, asumes lo prescrito y lo dices.

PROACTIVIDAD (cron)
- Al día siguiente de entrenar: preguntas por agujetas (una frase, escala 0-3 por zona)
  y llamas a `record_soreness`.
- Domingo: ejecutas la revisión semanal y entregas el resumen.
- Nunca reprochas sesiones perdidas. No existe la deuda de entrenamiento.
```

### 9.2 Formato de salida en Telegram

Diseñado para ~35 columnas monoespaciadas, legible en móvil sin scroll horizontal:

```
GIMNASIO · 45 min · readiness 72

CALENTAMIENTO (8')
· Movilidad cadera+torácica  5'
· Bird dog        2x6/lado
· Side plank      2x30s/lado

FUERZA (15')
1 Peso muerto hexagonal
  4x6 @ 90 kg   RIR 2
  desc 180s

ACCESORIO (12') superserie
2a Remo mancuerna
   3x10 @ 30 kg  RIR 2
2b Press militar mancuernas
   3x8 @ 20 kg   RIR 3
   desc 90s

FINISHER (8')
3 Farmer walk    3x40 m @ 28 kg

Hoy toca tirón vertical y hinge:
5 días sin espalda. Volumen algo
bajo porque dormiste 5h.
```

---

## 10. Ingesta de Apple Health

### 10.1 Mecanismo

HealthKit **no tiene API de servidor** y no puede consultarse desde el backend. El dato
lo empuja el teléfono. Opción recomendada: **Health Auto Export** (app de iOS, ~5 €),
que permite automatizaciones del tipo "cada día a las 7:00, POST este JSON a esta URL"
con cabeceras personalizadas. Alternativa gratuita: Atajos de iOS (más frágil y con
menos métricas accesibles). Una app nativa propia requiere Xcode y cuenta de
desarrollador: desproporcionado.

### 10.2 Endpoint

```
POST /api/health/ingest
Authorization: Bearer <TOKEN>
```

El cuerpo lo define la app exportadora, no nosotros. **Implementar un adaptador
tolerante**: normalizar a la forma interna, ignorar métricas desconocidas, aceptar lotes
solapados y llegadas desordenadas, e **idempotencia por (fecha, tipo_métrica)**.

> Verificar el esquema real contra un envío de prueba antes de escribir el parser.
> No dar por buena una estructura asumida: registrar el primer payload crudo en disco
> para inspeccionarlo.

Forma interna normalizada:

```json
{"metrics": [{"fecha": "2026-09-01", "tipo": "hrv", "valor": 42.1, "unidad": "ms"}],
 "workouts": [{"inicio": "2026-09-01T18:00:00Z", "tipo": "rowing",
               "minutos": 32, "fc_media": 138}]}
```

### 10.3 Métricas útiles

| Métrica | Uso |
|---|---|
| VO2máx ("Capacidad cardiovascular") | Es directamente el objetivo 3, medido sin tests |
| FC en reposo, HRV (SDNN) | **Readiness automática** (§4.4) |
| Sueño | Readiness |
| Entrenamientos (tipo, minutos, FC media) | Alimenta `z2` y `vo2` sin registro manual |
| Peso | Contexto |

**El beneficio principal no es la gráfica de VO2: es que la readiness deja de pedir
interacción.** Si el sistema sabe que se durmió 5 h y el HRV está un 20 % bajo la línea
base, recorta el volumen solo.

**Limitación importante:** el VO2máx de Apple **solo se actualiza en caminata, carrera o
senderismo al aire libre** con el Watch. Remo, bici estática y assault bike no lo tocan.
Como el cardio recomendado aquí es mayoritariamente de bajo impacto e indoor, el test
manual mensual (§4.6) sigue siendo necesario para ver moverse el objetivo 3.

---

## 11. Revisión periódica con IA

### 11.1 Qué es

Un job semanal que lee las últimas 4 semanas (logs, feedback, agujetas, notas,
tendencias de e1RM, readiness) y emite un **parche de política**: ajustes de prioridades
y τ, rotación de anchors, ejercicios a marcar como problemáticos, propuesta de descarga,
y 5 líneas en castellano explicando qué ha visto y qué cambia.

Es el uso interesante del razonamiento alto: está **fuera del camino crítico**, puede
tardar minutos y puede costar lo que haga falta.

### 11.2 Ejecución

Cron de OpenClaw (domingo). OpenClaw ya tiene agente, planificador y canal de entrega,
así que no hace falta un cron aparte con `claude -p` en el host. El resumen llega por
Telegram. Alternativa equivalente: `POST /api/reviews/run` disparado por cron del host.

### 11.3 Contrato de salida (validado, no confiado)

```json
{
  "resumen": "texto en castellano, máx. 6 líneas",
  "cambios_prioridad": {"pull_vertical": 0.95},
  "cambios_tau":       {"hinge": 4.5},
  "rotar_anchor":      [{"de": "front_squat", "a": "goblet_squat", "motivo": "..."}],
  "marcar_problematico":[{"slug": "press_militar_barra", "motivo": "molestia hombro"}],
  "proponer_descarga": true,
  "ejercicios_sugeridos": [{"slug": "...", "motivo": "..."}]
}
```

**Validación antes de aplicar** (esto no es opcional):

1. Todos los `slug` deben existir en el catálogo. Los que no, se descartan.
2. Prioridades en [0, 1]; τ en [0.5, 14]. Fuera de rango → se descarta el campo.
3. **La prioridad de las cualidades del objetivo 1 (core y espalda) no puede bajar de
   0.80.** El objetivo fundamental no es negociable por un LLM.
4. `ejercicios_sugeridos` **no** entra al catálogo automáticamente: va a una cola de
   aprobación manual.
5. Si el JSON no valida, se descarta entero y se registra el fallo. La política anterior
   sigue vigente. Nunca se aplica un parche parcial silenciosamente.

Cada revisión crea una **versión nueva** de `policy`, de modo que se puede revertir.

---

## 12. Despliegue

### 12.1 Contenedor

Imagen única. `docker-compose.yml` + plantilla de unraid. Un volumen `/data` con la BD
SQLite y los payloads crudos de Health. Variables: `COACH_TOKEN`, `ANTHROPIC_API_KEY`
(opcional, solo para funciones de IA degradables), `TZ`.

### 12.2 Red

Pensado para LAN o Tailscale. Sin autenticación de usuario; token compartido en
cabecera. **No exponer a internet sin proxy inverso con TLS.**

### 12.3 Configuración

**Todas** las constantes de §4 (prioridades, τ, `DAMAGE_CAP`, `FATIGUE_GATE`, vida media
de fatiga, multiplicadores, plantillas de tiempo) viven en un único módulo
`coach/config.py` con valores por defecto, sobreescribibles por la tabla `policy`.
Ninguna constante numérica de metodología puede estar incrustada en la lógica.

### 12.4 Mini-web de registro (válvula de escape, P3)

Registrar 15 series por chat puede resultar insufrible. Si tras 2–3 semanas de uso real
lo es, el bot envía junto a la tabla un enlace por sesión (`http://coach.local/s/{token}`)
a **una única pantalla**: la tabla con checkboxes, cargas preplaceadas con las de la
última vez y un temporizador de descanso. Conversación para pedir y ajustar, web para
registrar. Es aproximadamente 1/10 del trabajo de una PWA completa y probablemente sea
el punto óptimo del producto.

No implementar en P0. Es una respuesta a un problema que puede no darse.

---

## 13. Invariantes y testing

El motor es determinista, así que es testeable de verdad. Estos invariantes se cubren
con property tests (hypothesis) generando estados aleatorios de histórico, fatiga y
readiness. **Si una decisión de implementación entra en conflicto con un invariante,
gana el invariante.**

1. **Tiempo.** `tiempo_estimado(sesión) ≤ minutos_solicitados`, para todo input.
2. **Equipamiento.** Ninguna sesión con `lugar="casa"` contiene un ejercicio que
   requiera equipamiento. Ninguna sesión contiene equipamiento no disponible en su lugar.
3. **Daño.** El daño rodante de 7 días por grupo nunca supera `DAMAGE_CAP` tras aplicar
   la sesión generada.
4. **Novedad.** Como máximo un ejercicio con `novelty_mult > 1.0` por sesión, y su
   volumen es ≤ 60 % del nominal.
5. **Core siempre.** Toda sesión de ≥ 15 min contiene al menos un slot de `core_*`.
6. **Prioridad al recortar.** Al recortar por tiempo, nunca se elimina una cualidad del
   objetivo 1 mientras quede en la sesión una del objetivo 3.
7. **Cardio.** Nunca dos sesiones con `vo2` en menos de 48 h. Nunca `vo2` dentro de las
   24 h posteriores a un `hinge` pesado.
8. **Readiness baja.** Con `readiness < 40`, la sesión no contiene `power`, `vo2` ni
   series con RIR ≤ 1.
9. **Fatiga.** Ningún grupo con `fatiga > FATIGUE_GATE` recibe trabajo de alto daño.
10. **Determinismo.** Dos llamadas con el mismo estado y la misma semilla producen
    sesiones idénticas.
11. **Explicabilidad.** Todo `session_item` tiene una razón registrada en
    `generation_meta`.
12. **Degradación.** Con el LLM inaccesible, `generate_session` sigue devolviendo una
    sesión válida (test con la API de IA simulada como caída).
13. **Contrato de revisión.** Un parche de política inválido nunca se aplica ni
    parcialmente; la prioridad de core y espalda nunca baja de 0.80.
14. **Idempotencia.** `log_sets` y `/api/health/ingest` aplicados dos veces con el mismo
    contenido no duplican datos.
15. **Levantamientos olímpicos.** Ningún ejercicio con `tipo_progresion: olimpico` se
    prescribe con más de 3 repeticiones por serie, fuera del primer bloque de trabajo,
    con `readiness < 60`, ni en la misma sesión después de un `squat` o `hinge` pesado.
16. **Escalones.** Ningún ejercicio con `requiere_escalon: true` se prescribe si su
    escalón previo no está consolidado.
17. **Penalizaciones.** Ningún ejercicio con `penalizacion_usuario.factor == 0` aparece
    en una sesión generada. Los de factor 0.4 solo aparecen si su patrón no tiene
    alternativa disponible.

Además: tests de carga del catálogo (todo `slug` en `progresion_de`/`progresion_a` debe
existir; toda cualidad prioritaria debe tener ≥ 6 ejercicios en gimnasio y ≥ 4 en casa).

---

## 14. Fases

| Fase | Alcance | Criterio de aceptación |
|---|---|---|
| **P0** | Catálogo semilla (120–150 ejercicios), motor determinista completo (§6), plantillas de tiempo, servidor MCP con `generate_session` / `list_exercises`, SQLite, contenedor. Sin registro, sin IA. | Pedir una sesión por MCP devuelve una tabla válida que cumple los invariantes 1–9 |
| **P1** | `log_sets`, `finish_session`, histórico, cargas sugeridas, anchors, e1RM, `get_status`. Agente OpenClaw + Telegram con `SOUL.md`. | Ciclo completo por Telegram: pedir → entrenar → registrar → que la siguiente sesión use el dato |
| **P2** | Modelo de fatiga y daño con `record_soreness` y calibración de `doms_risk_personal`. `swap_exercise`. Readiness subjetiva. Detección de meseta y descarga automática. | Tras 3 semanas de uso, `doms_risk_personal` diverge del base en ≥ 10 ejercicios |
| **P3** | Ingesta de Apple Health y readiness automática. Revisión semanal con IA y parche de política validado. `render_chart`. Mini-web de registro **solo si hace falta**. | La readiness se calcula sin preguntar. Una revisión semanal llega por Telegram y aplica un parche válido |
| **P4** | Tests de VO2 y su seguimiento, exportación/importación, modo `fuera`, sugerencia de ejercicios nuevos con aprobación manual. | |

**P0 debe ser usable el primer día.** No es un esqueleto: incluye el catálogo completo y
el motor entero. Lo que falta en P0 es memoria (registro) y conversación, no calidad de
la sesión.

---

## 15. Decisiones tomadas y alternativas descartadas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Motor determinista, IA fuera del camino crítico | Agente LLM que programa la sesión | Un LLM no controla el volumen acumulado: propone 25 series de espalda un día y cero el resto. Además hace imposible garantizar los invariantes de §13 |
| Canal Telegram vía OpenClaw | PWA mobile-first | La entrada natural del producto es una frase ("voy a entrenar, 45 min, gimnasio"). El chat la hace nativa, permite proactividad que iOS no da a una PWA, y elimina todo el trabajo de frontend. Riesgo asumido: registrar series por chat (mitigado en §12.4) |
| Modelo de frescura | Cuotas semanales rodantes | Con entrenamiento oportunista, las cuotas generan deuda que se intenta compensar a martillazos — el mecanismo exacto que produce agujetas — o se agotan y el motor repite |
| Anchors fijos + accesorios rotatorios | Rotación total, o programa fijo tipo 5x5 | Rotar todo hace la progresión inmedible; no rotar nada aburre y estanca. La separación en dos capas resuelve ambas cosas |
| SQLite | PostgreSQL | Un usuario. Backup = copiar un fichero. Postgres es complejidad sin retorno en unraid |
| Repositorio propio | Subcarpeta de `hari2` | El proyecto no tiene relación con HARI más allá del autor |
| Cron de OpenClaw para la revisión | `claude -p` por cron en el host | OpenClaw ya aporta agente, planificador y canal de entrega. Menos piezas |
| Apple Health por push del teléfono | Consultar HealthKit desde el backend | HealthKit no tiene API de servidor y una PWA no puede leerlo. El único camino es que el teléfono empuje |
| Peso libre por defecto, máquinas penalizadas | Neutralidad ante el equipamiento | Preferencia explícita del usuario |
| Sin autenticación de usuario | Login | Un solo usuario, red privada |

---

## 16. Glosario

- **Anchor**: ejercicio fijo durante 8–12 semanas que sirve como métrica de progreso.
- **Cualidad (`quality`)**: capacidad o patrón entrenable (§4.1). Unidad de decisión del
  motor.
- **Frescura**: cuánto ha caducado una cualidad desde su última exposición.
- **DOMS**: agujetas (*delayed onset muscle soreness*).
- **`doms_risk`**: propensión de un ejercicio a producir agujetas (1–5), con una versión
  personal calibrada por el feedback del usuario.
- **Doble progresión**: subir repeticiones dentro de un rango antes de subir la carga.
- **e1RM**: 1RM estimado a partir de carga, repeticiones y RIR.
- **RIR** (*reps in reserve*): repeticiones que quedan en el depósito al acabar la serie.
- **Readiness**: disposición para entrenar hoy, derivada de HRV, FC de reposo, sueño y
  percepción subjetiva.
- **Descarga (*deload*)**: semana de volumen reducido manteniendo la intensidad.
- **Z2**: zona aeróbica baja, conversacional.
- **McGill Big 3**: curl-up, side plank y bird dog. Base de la resiliencia lumbar.
