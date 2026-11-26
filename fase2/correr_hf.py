"""Corre el etiquetador POS de HuggingFace sobre el set de prueba.

Modelo elegido: `mrm8488/RuPERTa-base-finetuned-pos` (RoBERTa en español
afinada sobre un treebank de UD). La especificación pedía usar
`PlanTL-GOB-ES/roberta-base-bne-capitel-pos`, pero ese repositorio fue
retirado de HuggingFace (devuelve 404) a fecha 2026-11-25. El reemplazo
expone un `id2label` casi idéntico (16 UPOS de UD más una etiqueta `O`
genérica para fuera-de-vocabulario, que mapeamos a `X`).

Antes de analizar las oraciones imprime `model.config.id2label` para
documentar en la corrida el mapeo que usará. Si las etiquetas no fueran
UPOS, el script se detendría y pediría definir un mapeo manual.

Entrada: las palabras ya tokenizadas (con `fase2/lexer_es.py` o con el
fallback para oraciones con error léxico). Se pasa `is_split_into_words=True`
al tokenizador y se asigna a cada palabra la etiqueta del primer subtoken,
usando `word_ids()`.

Salida: `fase2/resultados/hf.jsonl` con id, oracion, tokens, upos, tiempo_s
y tokenizacion (lexer/fallback).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.correr_spacy import _tokens_para_spacy   # noqa: E402

_MODELO = 'mrm8488/RuPERTa-base-finetuned-pos'

# UPOS válidas en Universal Dependencies; se usan para verificar que las
# etiquetas que devuelve el modelo coincidan con la convención.
_UPOS_VALIDAS = {
    'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 'NUM',
    'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 'VERB', 'X',
}

# Etiquetas que no son UPOS pero que acepta el modelo elegido. Se traducen
# al cargar el modelo para que la salida solo contenga UPOS.
_EQUIVALENCIAS = {
    'O': 'X',       # etiqueta "fuera" del modelo de mrm8488 → X.
}


def _verificar_etiquetas(id2label: dict) -> list[str]:
    """Verifica que las etiquetas del modelo sean UPOS y las devuelve en orden.

    Aplica además el mapeo `_EQUIVALENCIAS` para etiquetas que el modelo
    conoce pero no son UPOS "puras" (por ejemplo, la `O` de mrm8488 → `X`).
    """
    etiquetas = [id2label[i] for i in sorted(id2label)]
    print("Etiquetas del modelo (id2label):")
    for i, lab in sorted(id2label.items()):
        eq = _EQUIVALENCIAS.get(lab, lab)
        extra = f"  (reasignada a {eq})" if eq != lab else ""
        print(f"  {i:>3}: {lab}{extra}")
    extras = [e for e in etiquetas
              if _EQUIVALENCIAS.get(e, e) not in _UPOS_VALIDAS]
    if extras:
        raise RuntimeError(
            "Las etiquetas del modelo no son UPOS de UD. "
            f"Etiquetas no reconocidas: {extras!r}. "
            "Define un mapeo explícito antes de continuar."
        )
    print("  OK: todas las etiquetas son UPOS válidas de UD.\n")
    return etiquetas


def _analizar(tokenizer, modelo, palabras: list[str]):
    """Devuelve (upos, tiempo_s) para las palabras pre-tokenizadas.

    Alineación: cada palabra recibe la etiqueta del primer subtoken que la
    representa, usando `word_ids()` del tokenizador rápido.
    """
    import torch

    t0 = time.perf_counter()
    enc = tokenizer(
        palabras,
        is_split_into_words=True,
        return_tensors='pt',
        truncation=True,
    )
    with torch.no_grad():
        logits = modelo(**enc).logits[0]            # (n_subtokens, n_labels)
    ids = logits.argmax(dim=-1).tolist()
    word_ids = enc.word_ids(batch_index=0)

    id2label = modelo.config.id2label
    upos = [None] * len(palabras)
    vistos = set()
    for pos, wid in enumerate(word_ids):
        if wid is None or wid in vistos:
            continue
        vistos.add(wid)
        etiqueta = id2label[ids[pos]]
        upos[wid] = _EQUIVALENCIAS.get(etiqueta, etiqueta)
    tiempo = time.perf_counter() - t0
    return upos, tiempo


def _procesar(entrada: Path, salida: Path, modelo_nombre: str):
    # Import diferido para que el `--help` no cargue torch.
    from transformers import AutoTokenizer, AutoModelForTokenClassification

    print(f"Cargando modelo HuggingFace: {modelo_nombre}")
    # add_prefix_space=True es imprescindible para tokenizadores BBPE
    # (RoBERTa) cuando las palabras llegan pre-tokenizadas: sin él, cada
    # token se ve como principio de oración y el modelo etiqueta mal.
    tokenizer = AutoTokenizer.from_pretrained(
        modelo_nombre, add_prefix_space=True,
    )
    modelo = AutoModelForTokenClassification.from_pretrained(modelo_nombre)
    modelo.eval()

    _verificar_etiquetas(modelo.config.id2label)

    salida.parent.mkdir(parents=True, exist_ok=True)
    with entrada.open(encoding='utf-8') as fe, \
         salida.open('w', encoding='utf-8') as fs:
        for linea in fe:
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)
            palabras, modo = _tokens_para_spacy(d['oracion'],
                                                len(d.get('upos', [])))
            upos, tiempo = _analizar(tokenizer, modelo, palabras)
            fs.write(json.dumps({
                'id': d['id'],
                'oracion': d['oracion'],
                'tokens': palabras,
                'upos': upos,
                'tiempo_s': round(tiempo, 6),
                'tokenizacion': modo,
            }, ensure_ascii=False) + '\n')
    print(f"Listo. Salida: {salida}")


def _main(argv):
    p = argparse.ArgumentParser(description="Corre un POS tagger de HF.")
    p.add_argument('--entrada', default='fase2/pruebas/oraciones.jsonl',
                   help="JSONL de oraciones a procesar")
    p.add_argument('--salida', default='fase2/resultados/hf.jsonl',
                   help="JSONL de salida")
    p.add_argument('--modelo', default=_MODELO,
                   help="Identificador del modelo en HuggingFace Hub")
    args = p.parse_args(argv[1:])

    _procesar(Path(args.entrada), Path(args.salida), args.modelo)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
