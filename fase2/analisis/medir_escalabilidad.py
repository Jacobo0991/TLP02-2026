"""Mediciones de escalabilidad para la Fase 2.

Produce tres salidas dentro de fase2/analisis/:

1. escalabilidad_tiempo.csv: tiempo (mediana en ms) del parser frente a la
   longitud de la oracion (numero de tokens). Se usan las oraciones aceptadas
   del set + oraciones sinteticas con coordinacion (2, 4, 8, 16 miembros) y
   cadenas de "de" (el libro de la nina de la profesora...).
2. gramatica_concordancia.csv: calculo de cuantas reglas resultarian si la
   concordancia de C1, C3 y C4 se escribiera dentro de la CFG dividiendo los
   no terminales por genero, numero y persona. El metodo de conteo esta
   explicado en la funcion `estimar_reglas_cfg_concordancia`.
3. costo_ampliacion.csv: cuanto cuesta ampliar cada enfoque: formas del
   lexico + reglas de la CFG, tamano de los modelos de spaCy y HF en disco,
   y tokens promedio del prompt del LLM (zero-shot y few-shot).

No modifica codigo ni datos existentes. Se corre con:

    python -m fase2.analisis.medir_escalabilidad
"""

from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys
import time
from typing import List, Tuple

# Rutas y configuracion global
_RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.parser_es import analizar  # noqa: E402
from fase2.lexer_es import LEXICO  # noqa: E402

_ANALISIS = pathlib.Path(__file__).resolve().parent
_GRAFICAS = _ANALISIS / "graficas"
_GRAFICAS.mkdir(exist_ok=True)

_ORACIONES = _RAIZ / "fase2" / "pruebas" / "oraciones.jsonl"
_LOGS_LLM = _RAIZ / "fase2" / "logs" / "llm"


# ---------------------------------------------------------------------------
# 1. Tiempo del parser frente a la longitud en tokens.
# ---------------------------------------------------------------------------

def _tokens(oracion: str) -> int:
    """Cuenta tokens aproximando por split de espacios + signos de puntuacion."""
    from fase2.lexer_es import tokenizar, EOF
    toks, _errs = tokenizar(oracion)
    return sum(1 for t in toks if t.tipo != EOF)


def _medir_tiempo(oracion: str, repeticiones: int = 15) -> float:
    """Devuelve la mediana en segundos sobre varias repeticiones."""
    tiempos = []
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        analizar(oracion)
        tiempos.append(time.perf_counter() - t0)
    return statistics.median(tiempos)


def _oraciones_aceptadas() -> List[Tuple[str, str]]:
    """Devuelve (id, oracion) para las oraciones del set que debian aceptarse."""
    items = []
    with open(_ORACIONES, encoding="utf-8") as f:
        for linea in f:
            d = json.loads(linea)
            if d["esperado"] == "aceptada":
                items.append((d["id"], d["oracion"]))
    return items


def _generar_coordinacion(n: int) -> str:
    """'Ana, Luis, Pedro, ... y Carlos comen manzanas.' con n miembros."""
    nombres = ["Ana", "Luis", "Pedro", "Carlos", "Maria", "Sofia"]
    miembros = []
    for i in range(n):
        miembros.append(nombres[i % len(nombres)])
    if n == 1:
        sujeto = miembros[0]
    else:
        sujeto = ", ".join(miembros[:-1]) + " y " + miembros[-1]
    return f"{sujeto} comen manzanas."


def _generar_de(n: int) -> str:
    """'El libro de la nina de la profesora ...' con n complementos con 'de'."""
    sust_f = ["nina", "profesora", "casa", "mesa", "escuela", "flor"]
    frase = "El libro"
    for i in range(n):
        frase += f" de la {sust_f[i % len(sust_f)]}"
    frase += " es nuevo."
    return frase


def medir_tiempo_parser():
    filas = []

    # Oraciones aceptadas del set.
    for id_, texto in _oraciones_aceptadas():
        n = _tokens(texto)
        t = _medir_tiempo(texto)
        filas.append({
            "id": id_,
            "fuente": "set",
            "n_tokens": n,
            "mediana_s": t,
            "mediana_ms": t * 1000,
            "oracion": texto,
        })

    # Coordinacion creciente.
    for n in (2, 4, 8, 16):
        texto = _generar_coordinacion(n)
        toks = _tokens(texto)
        t = _medir_tiempo(texto)
        filas.append({
            "id": f"coord-{n}",
            "fuente": "coordinacion",
            "n_tokens": toks,
            "mediana_s": t,
            "mediana_ms": t * 1000,
            "oracion": texto,
        })

    # Cadenas de 'de'.
    for n in (1, 2, 4, 8, 16):
        texto = _generar_de(n)
        toks = _tokens(texto)
        t = _medir_tiempo(texto)
        filas.append({
            "id": f"de-{n}",
            "fuente": "cadena_de",
            "n_tokens": toks,
            "mediana_s": t,
            "mediana_ms": t * 1000,
            "oracion": texto,
        })

    csv_path = _ANALISIS / "escalabilidad_tiempo.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)

    _graficar_tiempos(filas)
    return filas


def _graficar_tiempos(filas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grupos = {}
    for r in filas:
        grupos.setdefault(r["fuente"], []).append((r["n_tokens"], r["mediana_ms"]))

    plt.figure(figsize=(7, 4.5))
    for fuente, puntos in grupos.items():
        puntos.sort()
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        plt.plot(xs, ys, "o-", label=fuente)
    plt.xlabel("Numero de tokens")
    plt.ylabel("Tiempo mediano por oracion (ms)")
    plt.title("Escalabilidad del parser: tiempo vs. longitud")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(_GRAFICAS / "escalabilidad_tiempo.png", dpi=120)
    plt.close()


# ---------------------------------------------------------------------------
# 2. Tamano de la gramatica si la concordancia se escribiera en la CFG.
# ---------------------------------------------------------------------------

def estimar_reglas_cfg_concordancia():
    """Cuantas reglas producirian C1, C3 y C4 dentro de la CFG.

    Metodo de conteo (documentado tambien en el hallazgo correspondiente):

    - Se parte de las 24 reglas de la gramatica actual.
    - Para C1 (concordancia DET-ADJ-SUST dentro del SN) hay que dividir los
      no terminales nominales (SNS, NOMINAL, NUCLEO_N, ADJS, SADJ, COMP_N,
      SP_DE, SN, SUJ, OD, ATRIB, SP) por (genero * numero) = 2 * 2 = 4
      variantes. Las reglas que mencionan dos de estos a la vez deben
      multiplicarse una sola vez (la copia se identifica por la etiqueta
      del padre); por eso contamos: reglas de SN-world * 4.
    - Para C3 (concordancia sujeto-verbo) hay que dividir SV, PRED, VERBO y
      el OD_OPC por (persona * numero) = 3 * 2 = 6 variantes, y ademas
      cruzar con las 4 variantes del SUJ. Solo las reglas que fijan la
      interfaz sujeto-verbo se multiplican por 6; las internas al SV, por 6
      (persona, numero). El OD hereda el genero-numero del SN.
    - Para C4 (atributo concuerda en genero y numero con el sujeto cuando es
      SADJ y en numero cuando es SN): ATRIB y las copulativas se dividen en
      4 variantes.
    - Las reglas que no tocan ni nominales ni verbo ni atributo (p. ej. R2
      FIN) se dejan intactas.

    Devuelve un diccionario con el detalle por regla original y el total.
    """

    # Clasificamos a mano cada regla original por el efecto de concordancia
    # que recibiria si C1/C3/C4 estuvieran en la CFG.
    #
    # - nominal_4   : 4 copias (genero * numero) para C1.
    # - sv_6        : 6 copias (persona * numero) para C3.
    # - sv_24       : 24 copias (genero * numero * persona * numero) cuando la
    #                 regla cruza SUJ con SV (R1) o SV con ATRIB (parte de
    #                 R17 y R20 cuando el atributo es SADJ).
    # - atrib_4     : 4 copias (genero * numero) para C4 cuando el atributo
    #                 es SADJ.
    # - intacta     : no cambia.

    reglas = [
        ("R1",  "O -> SUJ SV FIN | SV FIN",            "sv_24"),
        ("R2",  "FIN -> PUNTO | eps",                   "intacta"),
        ("R3",  "SUJ -> SN",                            "nominal_4"),
        ("R4",  "SN -> SNS COORD",                      "nominal_4"),
        ("R5",  "COORD -> LISTA CONJ SNS | eps",        "nominal_4"),
        ("R6",  "LISTA -> COMA SNS LISTA | eps",        "nominal_4"),
        ("R7",  "SNS -> DET NOMINAL | NPROP | PRON | NUCLEO_N", "nominal_4"),
        ("R8",  "NOMINAL -> ADJ NUCLEO_N | NUCLEO_N",   "nominal_4"),
        ("R9",  "NUCLEO_N -> SUST ADJS COMP_N",         "nominal_4"),
        ("R10", "ADJS -> SADJ ADJS | eps",              "nominal_4"),
        ("R11", "SADJ -> INTENS ADJ | ADJ",             "nominal_4"),
        ("R12", "COMP_N -> SP_DE | eps",                "nominal_4"),
        ("R13", "SP_DE -> PREP_DE SNS | CONTR_DE NOMINAL", "nominal_4"),
        ("R14", "SV -> MOD_PRE NEG_OPC PRED CCS",       "sv_6"),
        ("R15", "MOD_PRE -> SADV | eps",                "intacta"),
        ("R16", "NEG_OPC -> NEG | eps",                 "intacta"),
        ("R17", "PRED -> VERBO OD_OPC | COP ATRIB",     "sv_24"),
        ("R18", "OD_OPC -> OD | eps",                   "nominal_4"),
        ("R19", "OD -> SN",                             "nominal_4"),
        ("R20", "ATRIB -> SADJ | SN",                   "atrib_4"),
        ("R21", "CCS -> CC CCS | eps",                  "intacta"),
        ("R22", "CC -> SADV | SP",                      "intacta"),
        ("R23", "SP -> PREP SNS | PREP_DE SNS | CONTR_A NOMINAL | CONTR_DE NOMINAL", "nominal_4"),
        ("R24", "SADV -> ADV",                          "intacta"),
    ]

    factor = {"nominal_4": 4, "sv_6": 6, "sv_24": 24, "atrib_4": 4, "intacta": 1}

    detalle = []
    total = 0
    for id_r, texto, cat in reglas:
        copias = factor[cat]
        detalle.append({
            "regla": id_r, "produccion": texto,
            "categoria": cat, "copias": copias,
        })
        total += copias

    csv_path = _ANALISIS / "gramatica_concordancia.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["regla", "produccion", "categoria", "copias"])
        w.writeheader()
        w.writerows(detalle)

    # Resumen
    resumen_path = _ANALISIS / "gramatica_concordancia_resumen.csv"
    with open(resumen_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metrica", "valor"])
        w.writerow(["reglas_originales", 24])
        w.writerow(["reglas_con_concordancia_cfg", total])
        w.writerow(["factor_multiplicacion", round(total / 24, 2)])
    return detalle, total


# ---------------------------------------------------------------------------
# 3. Costo de ampliacion de cada enfoque.
# ---------------------------------------------------------------------------

def _tam_modelo_spacy():
    try:
        import spacy
        import spacy.util
        nombres = spacy.util.get_installed_models()
        if not nombres:
            return "DATO FALTANTE", "sin modelo spaCy instalado"
        nombre = nombres[0]
        nlp = spacy.load(nombre)
        p = pathlib.Path(nlp.path)
        tam_mb = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024 / 1024
        return round(tam_mb, 1), nombre
    except Exception as exc:
        return "DATO FALTANTE", f"error spaCy: {exc}"


def _tam_modelo_hf():
    try:
        from huggingface_hub import scan_cache_dir
        info = scan_cache_dir()
        for r in info.repos:
            if "RuPERTa-base-finetuned-pos" in r.repo_id:
                return round(r.size_on_disk / 1024 / 1024, 1), r.repo_id
        return "DATO FALTANTE", "modelo HF no encontrado en cache"
    except Exception as exc:
        return "DATO FALTANTE", f"error HF: {exc}"


def _tokens_prompt_llm():
    """Promedio de tokens de prompt de entrada por oracion, en zero/few-shot.

    Toma los valores reales que registro cada corrida en los logs. Devuelve
    el promedio de `tokens_entrada` sobre todas las llamadas.
    """
    out = {}
    for condicion in ("zero_shot", "few_shot"):
        ruta = _LOGS_LLM / f"{condicion}.jsonl"
        if not ruta.exists():
            out[condicion] = None
            continue
        tokens_in = []
        tokens_out = []
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                d = json.loads(linea)
                tokens_in.append(d.get("tokens_entrada", 0))
                tokens_out.append(d.get("tokens_salida", 0))
        if tokens_in:
            out[condicion] = {
                "llamadas": len(tokens_in),
                "tokens_entrada_prom": round(sum(tokens_in) / len(tokens_in), 1),
                "tokens_entrada_total": sum(tokens_in),
                "tokens_salida_prom": round(sum(tokens_out) / len(tokens_out), 1),
                "tokens_salida_total": sum(tokens_out),
            }
    return out


def medir_costo_ampliacion():
    spacy_mb, spacy_nombre = _tam_modelo_spacy()
    hf_mb, hf_nombre = _tam_modelo_hf()
    llm = _tokens_prompt_llm()

    filas = []
    filas.append({
        "enfoque": "CFG (parser)",
        "formas_lexico": len(LEXICO),
        "reglas_cfg": 24,
        "tamano_modelo_MB": "-",
        "tokens_prompt_prom": "-",
        "notas": "ampliar = anadir forma al lexico o regla a la gramatica",
    })
    filas.append({
        "enfoque": f"spaCy ({spacy_nombre})",
        "formas_lexico": "-",
        "reglas_cfg": "-",
        "tamano_modelo_MB": spacy_mb,
        "tokens_prompt_prom": "-",
        "notas": "ampliar = anadir datos y reentrenar; peso en disco",
    })
    filas.append({
        "enfoque": f"HF ({hf_nombre})",
        "formas_lexico": "-",
        "reglas_cfg": "-",
        "tamano_modelo_MB": hf_mb,
        "tokens_prompt_prom": "-",
        "notas": "ampliar = fine-tuning; peso en disco",
    })
    for cond in ("zero_shot", "few_shot"):
        d = llm.get(cond) or {}
        filas.append({
            "enfoque": f"LLM ({cond})",
            "formas_lexico": "-",
            "reglas_cfg": "-",
            "tamano_modelo_MB": "-",
            "tokens_prompt_prom": d.get("tokens_entrada_prom", "DATO FALTANTE"),
            "notas": f"ampliar = reescribir el prompt; llamadas={d.get('llamadas','?')}",
        })

    csv_path = _ANALISIS / "costo_ampliacion.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    return filas


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print("[1/3] Midiendo tiempo del parser...")
    filas_t = medir_tiempo_parser()
    print(f"  -> {_ANALISIS / 'escalabilidad_tiempo.csv'} ({len(filas_t)} filas)")

    print("[2/3] Estimando reglas CFG si la concordancia estuviera dentro...")
    detalle, total = estimar_reglas_cfg_concordancia()
    print(f"  -> total estimado: {total} reglas (factor {total/24:.1f}x)")

    print("[3/3] Costo de ampliacion...")
    filas_c = medir_costo_ampliacion()
    print(f"  -> {_ANALISIS / 'costo_ampliacion.csv'} ({len(filas_c)} filas)")


if __name__ == "__main__":
    main()
