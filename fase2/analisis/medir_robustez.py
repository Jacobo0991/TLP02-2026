"""Mide la robustez del parser, spaCy y HuggingFace frente a tres tipos de
variantes de oraciones del set: sin tildes, con mayusculas irregulares y con
una palabra fuera del lexico.

Entrada: fase2/pruebas/oraciones.jsonl.
Salida:
  - fase2/analisis/variantes_robustez.jsonl (las variantes generadas)
  - fase2/analisis/robustez_resultados.jsonl (resultado de cada sistema por variante)
  - fase2/analisis/robustez.csv (metricas agregadas)
  - fase2/analisis/graficas/robustez_aceptacion.png
  - fase2/analisis/graficas/robustez_upos.png

Se eligen las primeras 5 oraciones aceptadas con tildes para "sin_tildes", las
primeras 5 oraciones restantes para "mayusculas" y otras 5 para "palabra_oov"
sustituyendo un sustantivo del lexico por una palabra espanola comun pero
fuera del lexico.

Nota: el LLM no se vuelve a correr aqui por costo; si se quiere se puede
agregar con --con-llm. Por defecto queda registrado como DATO FALTANTE para
el LLM.

Uso:
    python -m fase2.analisis.medir_robustez
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import time
import unicodedata

_RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.parser_es import analizar  # noqa: E402

_ANALISIS = pathlib.Path(__file__).resolve().parent
_GRAFICAS = _ANALISIS / "graficas"
_GRAFICAS.mkdir(exist_ok=True)

_ORACIONES = _RAIZ / "fase2" / "pruebas" / "oraciones.jsonl"


# ---------------------------------------------------------------------------
# Generacion de variantes
# ---------------------------------------------------------------------------

def _quitar_tildes(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _mayus_irregulares(texto: str) -> str:
    """Alterna mayusculas y minusculas en las palabras (no en la puntuacion)."""
    out = []
    for i, ch in enumerate(texto):
        if ch.isalpha():
            if (i // 2) % 2 == 0:
                out.append(ch.upper())
            else:
                out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


# Sustituciones: sustantivo del lexico -> palabra comun fuera del lexico.
_OOV_SUST = {
    "pan": "arroz",       # arroz no esta en el lexico
    "manzana": "pera",    # pera no esta en el lexico
    "manzanas": "peras",
    "libros": "cuadernos",
    "cartas": "notas",
    "ventana": "puerta",
    "casa": "oficina",
    "coche": "bicicleta",
    "jardin": "patio",
    "parque": "estadio",
    "profesora": "doctora",
    "profesor": "doctor",
}


def _oov_sustituir(texto: str):
    """Sustituye el primer sustantivo del diccionario que aparezca.

    Devuelve (nuevo_texto, palabra_original, palabra_nueva) o None si no hubo
    reemplazo.
    """
    palabras = texto.split()
    for i, p in enumerate(palabras):
        limpia = p.strip(".,")
        suf = ""
        if p.endswith(".") or p.endswith(","):
            suf = p[-1]
        if limpia.lower() in _OOV_SUST:
            nueva = _OOV_SUST[limpia.lower()]
            if limpia[0].isupper():
                nueva = nueva.capitalize()
            palabras[i] = nueva + suf
            return " ".join(palabras), limpia, nueva
    return None


def _oraciones_aceptadas_gramaticales():
    """Devuelve las oraciones del set que debian aceptarse."""
    items = []
    with open(_ORACIONES, encoding="utf-8") as f:
        for linea in f:
            d = json.loads(linea)
            if d["esperado"] == "aceptada":
                items.append(d)
    return items


def generar_variantes():
    """Crea 15 variantes: 5 sin tildes, 5 mayusculas irregulares, 5 OOV.

    Devuelve lista de dicts con: id_var, id_original, tipo, oracion_original,
    oracion_variante, upos_esperado, nota.
    """
    aceptadas = _oraciones_aceptadas_gramaticales()

    # Filtramos candidatas con tilde para "sin_tildes".
    con_tilde = [o for o in aceptadas if _quitar_tildes(o["oracion"]) != o["oracion"]]
    sin_tilde = [o for o in aceptadas if _quitar_tildes(o["oracion"]) == o["oracion"]]

    variantes = []

    # 1) sin_tildes: 5 oraciones con tilde.
    for orig in con_tilde[:5]:
        var = _quitar_tildes(orig["oracion"])
        variantes.append({
            "id_var": f"{orig['id']}-sin_tildes",
            "id_original": orig["id"],
            "tipo": "sin_tildes",
            "oracion_original": orig["oracion"],
            "oracion_variante": var,
            "upos_esperado": orig["upos"],
            "nota": "Se retiraron los diacriticos; la ortografia deja de ser valida.",
        })

    # 2) mayusculas_irregulares: 5 oraciones.
    usadas = {v["id_original"] for v in variantes}
    candidatas = [o for o in aceptadas if o["id"] not in usadas]
    for orig in candidatas[:5]:
        var = _mayus_irregulares(orig["oracion"])
        variantes.append({
            "id_var": f"{orig['id']}-mayusculas",
            "id_original": orig["id"],
            "tipo": "mayusculas",
            "oracion_original": orig["oracion"],
            "oracion_variante": var,
            "upos_esperado": orig["upos"],
            "nota": "Alternancia caotica de mayusculas y minusculas.",
        })

    # 3) palabra_oov: buscar 5 oraciones donde se pueda hacer la sustitucion.
    usadas = {v["id_original"] for v in variantes}
    candidatas = [o for o in aceptadas if o["id"] not in usadas]
    recogidas = 0
    for orig in candidatas:
        res = _oov_sustituir(orig["oracion"])
        if res is None:
            continue
        nuevo, vieja, nueva = res
        variantes.append({
            "id_var": f"{orig['id']}-oov",
            "id_original": orig["id"],
            "tipo": "palabra_oov",
            "oracion_original": orig["oracion"],
            "oracion_variante": nuevo,
            "upos_esperado": orig["upos"],
            "nota": f"'{vieja}' -> '{nueva}' (palabra espanola comun pero fuera del lexico)",
        })
        recogidas += 1
        if recogidas >= 5:
            break

    # Guardar
    ruta = _ANALISIS / "variantes_robustez.jsonl"
    with open(ruta, "w", encoding="utf-8") as f:
        for v in variantes:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    print(f"  variantes generadas: {len(variantes)} -> {ruta}")
    return variantes


# ---------------------------------------------------------------------------
# Correr los sistemas sobre las variantes
# ---------------------------------------------------------------------------

def _cargar_semantico():
    from fase2.semantico_es import verificar
    return verificar


def _parser(oracion: str):
    semantico = _cargar_semantico()
    res = analizar(oracion, semantico=semantico)
    return res


def _spacy_proc(nlp, oracion: str, n_esperado: int):
    from fase2.correr_spacy import _tokens_para_spacy
    from spacy.tokens import Doc

    palabras, modo = _tokens_para_spacy(oracion, n_esperado)
    doc = Doc(nlp.vocab, words=palabras)
    for nombre, componente in nlp.pipeline:
        doc = componente(doc)
    upos = [t.pos_ for t in doc]
    return palabras, upos


def _hf_proc(modelo_hf, oracion: str, n_esperado: int):
    """Corre HF sobre tokens ya partidos. Devuelve (palabras, upos)."""
    from fase2.correr_spacy import _tokens_para_spacy
    tok, model, id2label = modelo_hf
    palabras, _modo = _tokens_para_spacy(oracion, n_esperado)
    enc = tok(palabras, is_split_into_words=True, return_tensors="pt",
              truncation=True)
    import torch
    with torch.no_grad():
        out = model(**enc)
    preds = out.logits.argmax(-1)[0].tolist()
    word_ids = enc.word_ids()
    upos_por_palabra = [None] * len(palabras)
    for pos, wid in enumerate(word_ids):
        if wid is None:
            continue
        if upos_por_palabra[wid] is None:
            etiqueta = id2label[preds[pos]]
            if etiqueta == "O":
                etiqueta = "X"
            upos_por_palabra[wid] = etiqueta
    return palabras, upos_por_palabra


def _cargar_hf():
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    nombre = "mrm8488/RuPERTa-base-finetuned-pos"
    tok = AutoTokenizer.from_pretrained(nombre)
    model = AutoModelForTokenClassification.from_pretrained(nombre)
    id2label = model.config.id2label
    return tok, model, id2label


def _exactitud_upos(pred, esp):
    """Exactitud posicion a posicion, truncando al menor largo."""
    if not pred or not esp:
        return 0, 0
    n = min(len(pred), len(esp))
    ok = sum(1 for i in range(n) if pred[i] == esp[i])
    return ok, len(esp)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def correr_robustez():
    print("[1/3] Generando variantes...")
    variantes = generar_variantes()

    print("[2/3] Cargando spaCy y HF...")
    import spacy
    import spacy.util
    nlp = spacy.load(spacy.util.get_installed_models()[0])
    hf = _cargar_hf()

    print("[3/3] Pasando variantes por parser, spaCy y HF...")
    resultados = []
    for v in variantes:
        oracion = v["oracion_variante"]
        esp = v["upos_esperado"]

        # Parser
        t0 = time.perf_counter()
        pres = _parser(oracion)
        t_parser = time.perf_counter() - t0
        # Convertir categorias parser -> UPOS para comparar.
        cat_a_upos = {
            "DET": "DET", "SUST": "NOUN", "NPROP": "PROPN", "PRON": "PRON",
            "ADJ": "ADJ", "VERBO": "VERB", "COP": "AUX",
            "ADV": "ADV", "INTENS": "ADV", "NEG": "ADV",
            "PREP": "ADP", "PREP_DE": "ADP", "CONTR_A": "ADP", "CONTR_DE": "ADP",
            "CONJ": "CCONJ", "COMA": "PUNCT", "PUNTO": "PUNCT",
        }
        upos_parser = [cat_a_upos.get(c, "X") for c in pres.categorias]
        ok_p, n_p = _exactitud_upos(upos_parser, esp)

        # spaCy
        try:
            _p, upos_sp = _spacy_proc(nlp, oracion, len(esp))
            ok_s, n_s = _exactitud_upos(upos_sp, esp)
        except Exception as e:
            upos_sp, ok_s, n_s = [], 0, len(esp)
            print(f"  warn spacy {v['id_var']}: {e}")

        # HF
        try:
            _p, upos_hf = _hf_proc(hf, oracion, len(esp))
            ok_h, n_h = _exactitud_upos([u for u in upos_hf if u is not None], esp)
        except Exception as e:
            upos_hf, ok_h, n_h = [], 0, len(esp)
            print(f"  warn hf {v['id_var']}: {e}")

        resultados.append({
            "id_var": v["id_var"],
            "tipo": v["tipo"],
            "oracion": oracion,
            "parser_aceptada": pres.aceptada,
            "parser_etapa": pres.etapa,
            "parser_upos_ok": ok_p,
            "parser_upos_total": n_p,
            "spacy_upos_ok": ok_s,
            "spacy_upos_total": n_s,
            "hf_upos_ok": ok_h,
            "hf_upos_total": n_h,
            "upos_esperado": esp,
            "upos_parser": upos_parser,
            "upos_spacy": upos_sp,
            "upos_hf": upos_hf,
        })

    # Guardar resultados crudos
    ruta_r = _ANALISIS / "robustez_resultados.jsonl"
    with open(ruta_r, "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Agregar por tipo
    por_tipo = {}
    for r in resultados:
        d = por_tipo.setdefault(r["tipo"], {
            "n": 0,
            "parser_aceptadas": 0,
            "parser_rechazo_lexico": 0,
            "parser_rechazo_sintactico": 0,
            "parser_rechazo_semantico": 0,
            "parser_upos_ok": 0, "parser_upos_total": 0,
            "spacy_upos_ok": 0, "spacy_upos_total": 0,
            "hf_upos_ok": 0, "hf_upos_total": 0,
        })
        d["n"] += 1
        if r["parser_aceptada"]:
            d["parser_aceptadas"] += 1
        else:
            etapa = r["parser_etapa"] or ""
            d[f"parser_rechazo_{etapa}"] = d.get(f"parser_rechazo_{etapa}", 0) + 1
        d["parser_upos_ok"] += r["parser_upos_ok"]
        d["parser_upos_total"] += r["parser_upos_total"]
        d["spacy_upos_ok"] += r["spacy_upos_ok"]
        d["spacy_upos_total"] += r["spacy_upos_total"]
        d["hf_upos_ok"] += r["hf_upos_ok"]
        d["hf_upos_total"] += r["hf_upos_total"]

    filas = []
    for tipo, d in por_tipo.items():
        fila = {
            "tipo": tipo,
            "n": d["n"],
            "parser_aceptacion_pct": round(100 * d["parser_aceptadas"] / d["n"], 1),
            "parser_rechazo_lexico": d.get("parser_rechazo_lexico", 0),
            "parser_rechazo_sintactico": d.get("parser_rechazo_sintactico", 0),
            "parser_rechazo_semantico": d.get("parser_rechazo_semantico", 0),
            "parser_upos_pct": round(100 * d["parser_upos_ok"] / d["parser_upos_total"], 1) if d["parser_upos_total"] else 0.0,
            "spacy_upos_pct": round(100 * d["spacy_upos_ok"] / d["spacy_upos_total"], 1) if d["spacy_upos_total"] else 0.0,
            "hf_upos_pct":    round(100 * d["hf_upos_ok"]    / d["hf_upos_total"],    1) if d["hf_upos_total"] else 0.0,
            "llm_upos_pct": "DATO FALTANTE",
            "llm_aceptacion_pct": "DATO FALTANTE",
        }
        filas.append(fila)

    # Total
    tot = {"tipo": "total", "n": 0,
           "parser_aceptadas": 0,
           "parser_upos_ok": 0, "parser_upos_total": 0,
           "spacy_upos_ok": 0, "spacy_upos_total": 0,
           "hf_upos_ok": 0, "hf_upos_total": 0}
    for r in resultados:
        tot["n"] += 1
        if r["parser_aceptada"]:
            tot["parser_aceptadas"] += 1
        tot["parser_upos_ok"] += r["parser_upos_ok"]
        tot["parser_upos_total"] += r["parser_upos_total"]
        tot["spacy_upos_ok"] += r["spacy_upos_ok"]
        tot["spacy_upos_total"] += r["spacy_upos_total"]
        tot["hf_upos_ok"] += r["hf_upos_ok"]
        tot["hf_upos_total"] += r["hf_upos_total"]
    filas.append({
        "tipo": "total",
        "n": tot["n"],
        "parser_aceptacion_pct": round(100 * tot["parser_aceptadas"] / tot["n"], 1),
        "parser_rechazo_lexico": sum(f.get("parser_rechazo_lexico", 0) for f in filas),
        "parser_rechazo_sintactico": sum(f.get("parser_rechazo_sintactico", 0) for f in filas),
        "parser_rechazo_semantico": sum(f.get("parser_rechazo_semantico", 0) for f in filas),
        "parser_upos_pct": round(100 * tot["parser_upos_ok"] / tot["parser_upos_total"], 1),
        "spacy_upos_pct": round(100 * tot["spacy_upos_ok"] / tot["spacy_upos_total"], 1),
        "hf_upos_pct":    round(100 * tot["hf_upos_ok"]    / tot["hf_upos_total"],    1),
        "llm_upos_pct": "DATO FALTANTE",
        "llm_aceptacion_pct": "DATO FALTANTE",
    })

    csv_path = _ANALISIS / "robustez.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"  -> {csv_path}")

    _graficar(filas)
    return filas


def _graficar(filas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    filas_tipo = [f for f in filas if f["tipo"] != "total"]
    tipos = [f["tipo"] for f in filas_tipo]

    # Aceptacion del parser por tipo
    plt.figure(figsize=(6.5, 4))
    acept = [f["parser_aceptacion_pct"] for f in filas_tipo]
    plt.bar(tipos, acept, color="#4e79a7")
    for i, v in enumerate(acept):
        plt.text(i, v + 1, f"{v}%", ha="center")
    plt.ylim(0, 110)
    plt.ylabel("% aceptada por el parser")
    plt.title("Robustez - aceptacion del parser por tipo de variante")
    plt.tight_layout()
    plt.savefig(_GRAFICAS / "robustez_aceptacion.png", dpi=120)
    plt.close()

    # Exactitud UPOS por tipo
    plt.figure(figsize=(8, 4.5))
    x = range(len(tipos))
    ancho = 0.25
    plt.bar([i - ancho for i in x], [f["parser_upos_pct"] for f in filas_tipo], ancho, label="parser")
    plt.bar(list(x),                 [f["spacy_upos_pct"]  for f in filas_tipo], ancho, label="spaCy")
    plt.bar([i + ancho for i in x], [f["hf_upos_pct"]     for f in filas_tipo], ancho, label="HF")
    plt.xticks(list(x), tipos)
    plt.ylim(0, 110)
    plt.ylabel("% exactitud UPOS")
    plt.title("Robustez - exactitud UPOS por tipo de variante")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_GRAFICAS / "robustez_upos.png", dpi=120)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="(reservado) limite para LLM")
    ap.parse_args()
    correr_robustez()


if __name__ == "__main__":
    main()
