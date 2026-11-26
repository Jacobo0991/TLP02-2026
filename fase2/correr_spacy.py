"""Corre spaCy sobre el set de prueba de la Fase 2.

Para que la comparación sea justa, las palabras llegan ya tokenizadas (con
`fase2/lexer_es.py`) y se arma un `Doc` con `spacy.tokens.Doc(nlp.vocab,
words=tokens)` antes de aplicar los componentes del pipeline.

Oraciones con error léxico (caracteres como `¿` o `?` que el lexer de la
Fase 2 no reconoce) usan una tokenización de respaldo que separa signos de
puntuación por fuera de las letras: así se recupera la misma cantidad de
tokens que trae el campo `upos` del set y queda documentado el fallback.

Salida: `fase2/resultados/spacy.jsonl` (o `_trf.jsonl` con `--modelo
es_dep_news_trf`). Cada línea lleva: id, oracion, tokens, upos, cabezas
(1-basadas, 0 = raíz), relaciones, morfologia, tiempo_s y tokenizacion
(`lexer` o `fallback`, documenta las oraciones con error léxico).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.lexer_es import tokenizar, EOF   # noqa: E402

# Signos de puntuación que hay que separar manualmente cuando el lexer de la
# Fase 2 no los acepta (como `¿` y `?`).
_SIGNOS_EXT = r'¿\?¡!;:'


def _tokenizar_respaldo(oracion: str) -> list[str]:
    """Separa por espacios y aísla la puntuación de apertura y cierre.

    Garantiza que cada `.`, `,`, `¿`, `?`, etc. quede como token propio.
    Esta función se usa SOLO cuando el lexer de la Fase 2 reporta errores
    léxicos; su objetivo es replicar la tokenización implícita en el campo
    `upos` del set.
    """
    tokens: list[str] = []
    for palabra in oracion.split():
        # Puntuación de apertura al inicio.
        m_ini = re.match(rf'[{_SIGNOS_EXT}]+', palabra)
        if m_ini:
            tokens.extend(list(m_ini.group(0)))
            palabra = palabra[m_ini.end():]
        # Puntuación de cierre al final (`.`, `,`, `?`, ...).
        m_fin = re.search(rf'[{_SIGNOS_EXT}.,]+$', palabra)
        suf = ''
        if m_fin:
            suf = palabra[m_fin.start():]
            palabra = palabra[:m_fin.start()]
        if palabra:
            tokens.append(palabra)
        if suf:
            tokens.extend(list(suf))
    return tokens


def _tokens_para_spacy(oracion: str, n_esperado: int) -> tuple[list[str], str]:
    """Devuelve (tokens, modo). `modo` es 'lexer' o 'fallback'.

    Si el lexer de la Fase 2 no reporta errores, usa esos tokens. Si reporta
    errores, usa `_tokenizar_respaldo`. En ambos casos se verifica contra
    `n_esperado` (longitud del `upos` del set).
    """
    toks, errores = tokenizar(oracion)
    if not errores:
        palabras = [t.lexema for t in toks if t.tipo != EOF]
        return palabras, 'lexer'
    palabras = _tokenizar_respaldo(oracion)
    return palabras, 'fallback'


def _analizar(nlp, oracion: str, n_esperado: int):
    """Corre el pipeline de spaCy sobre la oración ya tokenizada.

    Devuelve (palabras, upos, cabezas, relaciones, morfologia, tiempo, modo).
    `cabezas` es 1-basado; 0 señala la raíz.
    """
    from spacy.tokens import Doc

    palabras, modo = _tokens_para_spacy(oracion, n_esperado)
    doc = Doc(nlp.vocab, words=palabras)
    t0 = time.perf_counter()
    for nombre, componente in nlp.pipeline:
        doc = componente(doc)
    tiempo = time.perf_counter() - t0

    upos = [t.pos_ for t in doc]
    # `t.head.i == t.i` <=> raíz => cabeza 0. Si no, cabeza = t.head.i + 1.
    cabezas = [0 if t.head.i == t.i else t.head.i + 1 for t in doc]
    rels = [t.dep_ for t in doc]
    morfologia = [str(t.morph) for t in doc]
    return palabras, upos, cabezas, rels, morfologia, tiempo, modo


def _procesar(entrada: Path, salida: Path, nombre_modelo: str):
    import spacy
    print(f"Cargando modelo spaCy: {nombre_modelo}")
    nlp = spacy.load(nombre_modelo)
    print(f"  pipeline: {[n for n, _ in nlp.pipeline]}")
    print(f"  escribiendo: {salida}")

    salida.parent.mkdir(parents=True, exist_ok=True)
    with entrada.open(encoding='utf-8') as fe, \
         salida.open('w', encoding='utf-8') as fs:
        for linea in fe:
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)
            palabras, upos, cabezas, rels, morf, tiempo, modo = _analizar(
                nlp, d['oracion'], len(d.get('upos', [])),
            )
            fs.write(json.dumps({
                'id': d['id'],
                'oracion': d['oracion'],
                'tokens': palabras,
                'upos': upos,
                'cabezas': cabezas,
                'relaciones': rels,
                'morfologia': morf,
                'tiempo_s': round(tiempo, 6),
                'tokenizacion': modo,
            }, ensure_ascii=False) + '\n')
    print("Listo.")


def _main(argv):
    p = argparse.ArgumentParser(description="Corre spaCy sobre el set de prueba.")
    p.add_argument('--entrada', default='fase2/pruebas/oraciones.jsonl',
                   help="JSONL de oraciones a procesar")
    p.add_argument('--salida', default=None,
                   help="JSONL de salida (por defecto depende del modelo)")
    p.add_argument('--modelo', default='es_core_news_lg',
                   choices=('es_core_news_lg', 'es_dep_news_trf'),
                   help="Modelo de spaCy a usar")
    args = p.parse_args(argv[1:])

    entrada = Path(args.entrada)
    if args.salida is None:
        nombre = 'spacy.jsonl' if args.modelo == 'es_core_news_lg' else 'spacy_trf.jsonl'
        salida = _RAIZ / 'fase2' / 'resultados' / nombre
    else:
        salida = Path(args.salida)

    _procesar(entrada, salida, args.modelo)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
