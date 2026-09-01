#!/usr/bin/env python3
"""Validación del catálogo semilla. Ver DESIGN.md §5 y §13.

Comprueba las referencias cruzadas y la densidad mínima por cualidad y lugar.
Sin densidad suficiente, el índice de hastío (§4.2) no tiene de dónde elegir
y el sistema se vuelve repetitivo — el fallo del 5x5 que hay que evitar.
"""
import sys, glob, yaml
from collections import defaultdict

CUALIDADES_P1 = {"core_antiext", "core_antirot", "core_antilat",
                 "pull_horizontal", "pull_vertical", "hinge", "carry"}
CUALIDADES = CUALIDADES_P1 | {"mobility", "power", "agility", "vo2", "z2",
                              "squat", "lunge", "push_horizontal", "push_vertical",
                              "balance"}
MIN_GIMNASIO, MIN_CASA = 6, 4
TIPOS_PROGRESION = {"doble", "olimpico", "densidad", "movilidad"}

ejercicios, errores, avisos = {}, [], []

for f in sorted(glob.glob("exercises/*.yaml")):
    for e in yaml.safe_load(open(f)) or []:
        if e["slug"] in ejercicios:
            errores.append(f"slug duplicado: {e['slug']}")
        e["_file"] = f
        ejercicios[e["slug"]] = e

for slug, e in ejercicios.items():
    for campo in ("nombre", "patrones", "lugares", "doms_risk", "skill"):
        if campo not in e:
            errores.append(f"{slug}: falta campo obligatorio '{campo}'")
    for p in e.get("patrones", []):
        if p not in CUALIDADES:
            errores.append(f"{slug}: cualidad desconocida '{p}'")
    if not 1 <= e.get("doms_risk", 0) <= 5:
        errores.append(f"{slug}: doms_risk fuera de rango")
    if e.get("tipo_progresion", "doble") not in TIPOS_PROGRESION:
        errores.append(f"{slug}: tipo_progresion inválido")
    for campo in ("progresion_de", "progresion_a"):
        for ref in e.get(campo, []):
            if ref not in ejercicios:
                errores.append(f"{slug}: {campo} apunta a slug inexistente '{ref}'")
    # invariante 18: techo de carga incompatible con doble progresión
    if e.get("carga_max_pct_peso") and e.get("tipo_progresion") == "doble":
        errores.append(f"{slug}: carga_max_pct_peso con tipo_progresion 'doble'")
    # casa = cero equipamiento
    # casa = cero equipamiento. `equipamiento_opcional` no descalifica: son
    # ejercicios que funcionan con peso corporal y admiten carga si la hay.
    if "casa" in e.get("lugares", []) and e.get("equipamiento"):
        errores.append(f"{slug}: en 'casa' pero requiere {e['equipamiento']}")
    # doms_risk alto sin aviso al usuario
    if e.get("doms_risk", 0) >= 4 and not e.get("cues_siempre"):
        avisos.append(f"{slug}: doms_risk {e['doms_risk']} sin cue de aviso")

# --- repertorio activo (§5.7) ---
rep = yaml.safe_load(open("repertorio.yaml"))
activos = [s for grupo in rep["activos"].values() for s in grupo]
if len(activos) != len(set(activos)):
    errores.append("repertorio: slugs duplicados")
if len(activos) > rep["limite"]:
    errores.append(f"repertorio: {len(activos)} activos supera el límite {rep['limite']}")
for slug in activos + [c["slug"] for c in rep.get("proximos_candidatos", [])]:
    if slug not in ejercicios:
        errores.append(f"repertorio: slug inexistente '{slug}'")
for slug in activos:
    e = ejercicios.get(slug, {})
    if e.get("prerrequisito"):
        errores.append(f"repertorio: '{slug}' está activo pero tiene prerrequisito sin cumplir")

densidad = defaultdict(lambda: defaultdict(int))
for e in ejercicios.values():
    for p in e.get("patrones", []):
        for lugar in e.get("lugares", []):
            densidad[p][lugar] += 1

print(f"{len(ejercicios)} ejercicios en {len(glob.glob('exercises/*.yaml'))} ficheros\n")
dens_act = defaultdict(lambda: defaultdict(int))
for slug in activos:
    e = ejercicios.get(slug, {})
    for p in e.get("patrones", []):
        for lugar in e.get("lugares", []):
            dens_act[p][lugar] += 1

print(f"repertorio activo: {len(activos)} de {len(ejercicios)} (límite {rep['limite']})\n")
print(f"{'cualidad':<18} {'activo:gim':>11} {'activo:casa':>12} {'catálogo':>9}")
print("-" * 53)
for c in sorted(CUALIDADES):
    print(f"{c:<18} {dens_act[c]['gimnasio']:>11} {dens_act[c]['casa']:>12} "
          f"{densidad[c]['gimnasio'] + densidad[c]['casa']:>9}")
    if c in CUALIDADES_P1 and dens_act[c]["gimnasio"] < 2:
        avisos.append(f"repertorio: {c} solo tiene {dens_act[c]['gimnasio']} activo en gimnasio")
print()
print(f"{'cualidad':<18} {'gimnasio':>9} {'casa':>6} {'fuera':>6}")
print("-" * 43)
for c in sorted(CUALIDADES):
    g, ca, fu = densidad[c]["gimnasio"], densidad[c]["casa"], densidad[c]["fuera"]
    marca = ""
    if c in CUALIDADES_P1:
        if g < MIN_GIMNASIO:
            marca = f"  ← gimnasio < {MIN_GIMNASIO}"
            avisos.append(f"densidad baja: {c} tiene {g} en gimnasio (mínimo {MIN_GIMNASIO})")
        elif ca < MIN_CASA and c not in ("pull_vertical", "carry"):
            marca = f"  ← casa < {MIN_CASA}"
            avisos.append(f"densidad baja: {c} tiene {ca} en casa (mínimo {MIN_CASA})")
    print(f"{c:<18} {g:>9} {ca:>6} {fu:>6}{marca}")

riesgo = defaultdict(int)
for e in ejercicios.values():
    riesgo[e["doms_risk"]] += 1
print("\ndoms_risk:", " ".join(f"{k}:{riesgo[k]}" for k in sorted(riesgo)))
bloqueados = [s for s, e in ejercicios.items() if e.get("prerrequisito")]
penalizados = [s for s, e in ejercicios.items()
               if e.get("penalizacion_usuario", {}).get("factor", 1.0) < 1.0]
print("con prerrequisito:", ", ".join(bloqueados) or "ninguno")
print("penalizados:", ", ".join(penalizados) or "ninguno")

if avisos:
    print("\nAVISOS")
    for a in avisos: print(" ·", a)
if errores:
    print("\nERRORES")
    for e in errores: print(" ✗", e)
    sys.exit(1)
print("\nCatálogo válido.")
