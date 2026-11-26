"""Verifica que las cifras citadas en hallazgos.md (y en informe.md) coincidan
con las fuentes CSV/JSONL del repositorio.

Enfoque: en vez de parsear el texto, recalculamos las cifras principales desde
los archivos fuente y mostramos lado a lado (valor esperado por el documento,
valor recalculado). Si coinciden, OK; si no, se lista como discrepancia. Los
valores que no son reproducibles se marcan como "NO VERIFICABLE".

Uso:
    python -m fase2.analisis.verificar_hallazgos
    python -m fase2.analisis.verificar_hallazgos --informe

El modo `--informe` comprueba además que los numeros citados textualmente en
fase2/informe/informe.md aparezcan tambien en fase2/analisis/hallazgos.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

_RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
_FASE2 = _RAIZ / "fase2"
_RES = _FASE2 / "resultados"
_ANA = _FASE2 / "analisis"


def _leer_csv(path: pathlib.Path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f))


def _leer_jsonl(path: pathlib.Path):
    out = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                out.append(json.loads(linea))
    return out


def recalcular():
    """Devuelve dict {clave_corta: valor_recalculado}."""
    r = {}

    # Set de prueba
    oraciones = _leer_jsonl(_FASE2 / "pruebas" / "oraciones.jsonl")
    r["n_oraciones"] = len(oraciones)
    r["n_aceptada_esperado"] = sum(1 for o in oraciones if o["esperado"] == "aceptada")
    r["n_rechazo_esperado"] = sum(1 for o in oraciones
                                   if o["esperado"].startswith("rechazo"))
    r["n_ambig"] = sum(1 for o in oraciones
                       if o.get("fenomeno") and "ambig" in o["fenomeno"].lower())

    # metricas.csv (parser/spacy/hf/llm)
    lineas = _leer_csv(_RES / "metricas.csv")
    bloques = {}
    actual = None
    for row in lineas:
        if not row:
            continue
        if len(row) == 1:
            actual = row[0]
            bloques[actual] = []
            continue
        bloques[actual].append(row)

    # UPOS totales
    upos = bloques["Exactitud UPOS por nivel y sistema"]
    cab = upos[0]
    for fila in upos[1:]:
        d = dict(zip(cab, fila))
        nivel = d["nivel"]
        for sis in ("parser", "spacy", "hf", "llm-few_shot", "llm-zero_shot"):
            r[f"upos_{sis}_{nivel}"] = float(d[sis]) * 100

    # UAS LAS
    uaslas = bloques["UAS y LAS por nivel"]
    cab = uaslas[0]
    for fila in uaslas[1:]:
        d = dict(zip(cab, fila))
        nivel = d["nivel"]
        r[f"parser_uas_{nivel}"] = float(d["parser_UAS"]) * 100
        r[f"parser_las_{nivel}"] = float(d["parser_LAS"]) * 100
        r[f"spacy_uas_{nivel}"] = float(d["spacy_UAS"]) * 100
        r[f"spacy_las_{nivel}"] = float(d["spacy_LAS"]) * 100

    # Aceptacion
    acept = bloques["Aceptación (parser y LLM)"]
    cab = acept[0]
    for fila in acept[1:]:
        d = dict(zip(cab, fila))
        sis = d["sistema"]
        r[f"{sis}_vp"] = int(d["VP"])
        r[f"{sis}_vn"] = int(d["VN"])
        r[f"{sis}_fn"] = int(d["FN"])
        r[f"{sis}_fp"] = int(d["FP"])
        r[f"{sis}_precision"] = float(d["precision"]) * 100
        r[f"{sis}_cobertura"] = float(d["cobertura"]) * 100

    # Costo (tiempos)
    costo = bloques["Costo: tiempo promedio por oración y tamaño del modelo"]
    cab = costo[0]
    for fila in costo[1:]:
        d = dict(zip(cab, fila))
        sis = d["sistema"]
        r[f"{sis}_tiempo_s"] = float(d["tiempo_prom_s"])
        r[f"{sis}_tamano_mb"] = float(d["tamano_MB"])

    # metricas_llm.csv
    lineas = _leer_csv(_RES / "metricas_llm.csv")
    # formato libre; buscamos filas conocidas
    for row in lineas:
        if not row:
            continue
        if row[0] == "Formato inválido (%)" and len(row) >= 3:
            r["llm_formato_zero"] = float(row[1])
            r["llm_formato_few"] = float(row[2])
        if row[0] == "Consistencia (%)" and len(row) >= 3:
            r["llm_consistencia_zero"] = float(row[1]) * 100
            r["llm_consistencia_few"] = float(row[2]) * 100
        if row[0] == "Desviación español (%)" and len(row) >= 3:
            r["llm_desv_zero"] = float(row[1]) * 100
            r["llm_desv_few"] = float(row[2]) * 100
        if row[0] == "R12 (%)" and len(row) >= 3:
            r["llm_r12_zero"] = float(row[1]) * 100
            r["llm_r12_few"] = float(row[2]) * 100
        if row[0] == "zero_shot" and len(row) >= 5:
            try:
                r["llm_zero_tokens_in"] = int(row[1])
                r["llm_zero_tokens_out"] = int(row[2])
                r["llm_zero_usd"] = float(row[3])
                r["llm_zero_latencia"] = float(row[4])
            except ValueError:
                pass
        if row[0] == "few_shot" and len(row) >= 5:
            try:
                r["llm_few_tokens_in"] = int(row[1])
                r["llm_few_tokens_out"] = int(row[2])
                r["llm_few_usd"] = float(row[3])
                r["llm_few_latencia"] = float(row[4])
            except ValueError:
                pass

    # analisis/robustez.csv
    with open(_ANA / "robustez.csv", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            tipo = row["tipo"]
            r[f"rob_{tipo}_parser_pct"] = float(row["parser_aceptacion_pct"])
            r[f"rob_{tipo}_parser_upos"] = float(row["parser_upos_pct"])
            r[f"rob_{tipo}_spacy_upos"] = float(row["spacy_upos_pct"])
            r[f"rob_{tipo}_hf_upos"] = float(row["hf_upos_pct"])

    # gramatica_concordancia_resumen.csv
    with open(_ANA / "gramatica_concordancia_resumen.csv", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            r[f"gram_{row['metrica']}"] = row["valor"]

    # escalabilidad_tiempo.csv (dos puntos tipicos)
    with open(_ANA / "escalabilidad_tiempo.csv", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
    por_id = {row["id"]: row for row in rows}
    for id_, clave in [("N1-01", "esc_n1_01_ms"),
                        ("N1-06", "esc_n1_06_ms"),
                        ("coord-4", "esc_coord4_ms"),
                        ("coord-8", "esc_coord8_ms"),
                        ("coord-16", "esc_coord16_ms"),
                        ("de-16", "esc_de16_ms")]:
        if id_ in por_id:
            r[clave] = round(float(por_id[id_]["mediana_ms"]), 4)

    # costo_ampliacion.csv: tokens prompt promedio
    with open(_ANA / "costo_ampliacion.csv", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            if row["enfoque"].startswith("LLM (zero"):
                r["llm_zero_tokens_prompt_prom"] = float(row["tokens_prompt_prom"])
            if row["enfoque"].startswith("LLM (few"):
                r["llm_few_tokens_prompt_prom"] = float(row["tokens_prompt_prom"])

    return r


# ---------------------------------------------------------------------------
# Cifras citadas (manuales): clave corta -> (texto_esperado, valor_esperado)
# ---------------------------------------------------------------------------

def tabla_citas():
    """Lista de afirmaciones a verificar: (etiqueta_descriptiva, clave_rec,
    valor_citado). `tol` se compara con tolerancia 0.05 por si cambia el
    redondeo."""
    return [
        ("§1 oraciones del set", "n_oraciones", 60),
        ("§1 n aceptadas esperadas", "n_aceptada_esperado", 34),
        ("§3 n ambiguedad fenomeno", "n_ambig", 4),

        ("§1 UPOS parser total", "upos_parser_total", 100.0),
        ("§1 UPOS spaCy total", "upos_spacy_total", 95.5),
        ("§1 UPOS HF total", "upos_hf_total", 53.8),

        ("§1 UAS parser total", "parser_uas_total", 100.0),
        ("§1 LAS parser total", "parser_las_total", 100.0),
        ("§1 UAS spaCy total", "spacy_uas_total", 96.2),
        ("§1 LAS spaCy total", "spacy_las_total", 77.6),

        ("§1 parser VP",       "parser_vp", 33),
        ("§1 parser VN",       "parser_vn", 26),
        ("§1 parser FN",       "parser_fn", 1),
        ("§1 parser FP",       "parser_fp", 0),

        ("§2 UPOS parser N1",  "upos_parser_1", 100.0),
        ("§2 UPOS parser N2",  "upos_parser_2", 100.0),
        ("§2 UPOS parser N3",  "upos_parser_3", 100.0),
        ("§2 UPOS spaCy N1",   "upos_spacy_1", 96.5),
        ("§2 UPOS spaCy N2",   "upos_spacy_2", 97.4),
        ("§2 UPOS spaCy N3",   "upos_spacy_3", 93.1),
        ("§2 UPOS HF N1",      "upos_hf_1", 41.2),
        ("§2 UPOS HF N2",      "upos_hf_2", 57.4),
        ("§2 UPOS HF N3",      "upos_hf_3", 58.8),

        # Robustez
        ("§2 robustez parser sin_tildes %",       "rob_sin_tildes_parser_pct", 0.0),
        ("§2 robustez parser mayusculas %",       "rob_mayusculas_parser_pct", 100.0),
        ("§2 robustez parser palabra_oov %",      "rob_palabra_oov_parser_pct", 0.0),
        ("§2 robustez spaCy sin_tildes UPOS",     "rob_sin_tildes_spacy_upos", 80.0),
        ("§2 robustez spaCy mayusculas UPOS",     "rob_mayusculas_spacy_upos", 57.1),
        ("§2 robustez spaCy palabra_oov UPOS",    "rob_palabra_oov_spacy_upos", 100.0),
        ("§2 robustez HF sin_tildes UPOS",        "rob_sin_tildes_hf_upos", 75.0),
        ("§2 robustez HF mayusculas UPOS",        "rob_mayusculas_hf_upos", 42.9),
        ("§2 robustez HF palabra_oov UPOS",       "rob_palabra_oov_hf_upos", 82.8),

        # Ambiguedad / LLM R12
        ("§3 R12 zero %",      "llm_r12_zero", 100.0),
        ("§3 R12 few %",       "llm_r12_few",  75.0),

        # Escalabilidad
        ("§4 esc N1-01 ms",    "esc_n1_01_ms", 0.0109),
        ("§4 esc coord-4 ms",  "esc_coord4_ms", 0.0157),
        ("§4 esc coord-8 ms",  "esc_coord8_ms", 0.0151),
        ("§4 esc coord-16 ms", "esc_coord16_ms", 0.0268),
        ("§4 esc de-16 ms",    "esc_de16_ms", 0.0507),
        ("§4 reglas CFG con concordancia", "gram_reglas_con_concordancia_cfg", "120"),
        ("§4 factor x",         "gram_factor_multiplicacion", "5.0"),

        # Costo
        ("§5 spaCy MB",         "spacy_tamano_mb", 601.99),
        ("§5 HF MB",            "hf_tamano_mb", 962.74),
        ("§5 LLM zero tokens in", "llm_zero_tokens_in", 394617),
        ("§5 LLM few tokens in",  "llm_few_tokens_in",  576237),
        ("§5 LLM zero USD",     "llm_zero_usd", 0.160548),
        ("§5 LLM few USD",      "llm_few_usd",  0.142860),
        ("§5 LLM zero tokens prompt prom", "llm_zero_tokens_prompt_prom", 2192.3),
        ("§5 LLM few tokens prompt prom",  "llm_few_tokens_prompt_prom",  3201.3),

        # LLM behavior
        ("§6 desviacion zero", "llm_desv_zero", 0.0),
        ("§6 desviacion few",  "llm_desv_few",  0.0),
        ("§6 formato zero",    "llm_formato_zero", 0.0),
        ("§6 formato few",     "llm_formato_few",  0.0),
        ("§6 consistencia zero", "llm_consistencia_zero", 91.6666666),
        ("§6 consistencia few",  "llm_consistencia_few",  100.0),
    ]


def verificar_hallazgos():
    recalc = recalcular()
    ok = 0
    ko = 0
    no_ver = 0
    detalles = []
    for etiqueta, clave, esperado in tabla_citas():
        if clave not in recalc:
            no_ver += 1
            detalles.append((etiqueta, clave, esperado, None, "NO VERIFICABLE"))
            continue
        obtenido = recalc[clave]
        try:
            if isinstance(esperado, (int, float)) and isinstance(obtenido, (int, float)):
                coincide = abs(float(obtenido) - float(esperado)) < 0.05
            else:
                coincide = str(obtenido).strip() == str(esperado).strip()
        except Exception:
            coincide = False
        if coincide:
            ok += 1
            detalles.append((etiqueta, clave, esperado, obtenido, "OK"))
        else:
            ko += 1
            detalles.append((etiqueta, clave, esperado, obtenido, "DISCREPA"))

    # Reporte
    print("Verificacion de hallazgos.md")
    print("=" * 70)
    for etiqueta, clave, esp, obt, estado in detalles:
        print(f"  [{estado:11s}] {etiqueta:40s} esp={esp}  obt={obt}")
    print("-" * 70)
    print(f"Total: {len(detalles)} cifras  |  OK: {ok}  "
          f"DISCREPA: {ko}  NO VERIFICABLE: {no_ver}")
    return detalles, ok, ko, no_ver


# ---------------------------------------------------------------------------
# Comprobar que todo numero del informe este en hallazgos.md
# ---------------------------------------------------------------------------

def _extraer_numeros(texto: str):
    """Devuelve conjunto de numeros (como strings) de texto."""
    # Numero: entero con posibles comas o puntos como separadores, opcional %
    pat = re.compile(r"\b\d[\d.,]*\b")
    out = set()
    for m in pat.finditer(texto):
        s = m.group(0)
        # Normalizar
        s = s.replace(",", "")
        try:
            v = float(s)
        except ValueError:
            continue
        out.add(round(v, 4))
    return out


def verificar_informe():
    ruta_h = _ANA / "hallazgos.md"
    ruta_i = _FASE2 / "informe" / "informe.md"
    if not ruta_i.exists():
        print("fase2/informe/informe.md no existe aun; nada que verificar.")
        return
    h = ruta_h.read_text(encoding="utf-8")
    i = ruta_i.read_text(encoding="utf-8")
    nh = _extraer_numeros(h)
    ni = _extraer_numeros(i)
    faltan = sorted([n for n in ni if n not in nh])
    comunes = sorted([n for n in ni if n in nh])
    print("Verificacion informe.md vs hallazgos.md")
    print("=" * 70)
    print(f"Numeros del informe presentes en hallazgos: {len(comunes)}")
    print(f"Numeros del informe NO presentes en hallazgos ({len(faltan)}):")
    for n in faltan:
        print(f"  - {n}")
    return faltan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--informe", action="store_true")
    args = ap.parse_args()
    verificar_hallazgos()
    if args.informe:
        print()
        verificar_informe()


if __name__ == "__main__":
    main()
