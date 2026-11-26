"""Verifica que las oraciones de ``fase2/prompts/few_shot.txt`` no aparezcan
en ``fase2/pruebas/oraciones.jsonl`` ni sean una variación mínima de una de
ellas, y que los árboles de los ejemplos aceptados coincidan con los que
produce ``parser_es.py``.

Variación mínima: dos oraciones que, tras normalizar espacios, mayúsculas y
puntuación, comparten más del 70 % de las palabras (índice de Jaccard sobre
el conjunto de lemas aproximados por minúsculas). El umbral se eligió para
que el ejemplo *Un gato pequeño saltó.* no choque con *El perro negro
corre.*, pero sí marcaría un clon como *Pedro camina al casa* vs *Pedro
camina al parque*.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.parser_es import analizar  # noqa: E402

RUTA_SET = _RAIZ / 'fase2' / 'pruebas' / 'oraciones.jsonl'
RUTA_FEW = _RAIZ / 'fase2' / 'prompts' / 'few_shot.txt'

UMBRAL_JACCARD = 0.70


# --- Utilidades ---------------------------------------------------------

def _normalizar(oracion: str) -> str:
    """Minúsculas, sin puntos ni comas, espacios colapsados."""
    o = oracion.lower()
    o = re.sub(r'[.,¿?¡!]', ' ', o)
    o = re.sub(r'\s+', ' ', o).strip()
    return o


def _palabras(oracion: str) -> set[str]:
    return set(_normalizar(oracion).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --- Extracción de ejemplos del archivo ---------------------------------

def _leer_ejemplos_few_shot(ruta: Path):
    """Extrae los pares (oración, respuesta JSON) de la sección ``Ejemplos``."""
    texto = ruta.read_text(encoding='utf-8')
    pares = []
    # Las líneas vienen en pares ``Oración: ...`` + ``{...}`` separados por
    # una línea en blanco. Se detiene al llegar al marcador ``{ORACION}``.
    bloques = re.findall(
        r'Oración:\s*(.+?)\n(\{.*?\})\s*(?=\n\nOración|\Z)',
        texto, flags=re.DOTALL)
    for oracion, respuesta in bloques:
        oracion = oracion.strip()
        if oracion == '{ORACION}':
            continue
        try:
            datos = json.loads(respuesta)
        except json.JSONDecodeError as e:
            print(f'[ERROR] JSON inválido en ejemplo "{oracion}": {e}')
            continue
        pares.append((oracion, datos))
    return pares


def _leer_set(ruta: Path):
    out = []
    with ruta.open(encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            out.append(json.loads(linea))
    return out


# --- Verificación -------------------------------------------------------

def verificar():
    ejemplos = _leer_ejemplos_few_shot(RUTA_FEW)
    conjunto = _leer_set(RUTA_SET)
    set_norm = {_normalizar(r['oracion']): r['id'] for r in conjunto}

    errores = []
    print(f'Verificando {len(ejemplos)} ejemplos contra {len(conjunto)} oraciones del set...\n')

    for oracion, datos in ejemplos:
        norma = _normalizar(oracion)
        # 1) Coincidencia exacta.
        if norma in set_norm:
            errores.append(f'[EXACTA] "{oracion}" coincide con {set_norm[norma]}')
            continue
        # 2) Variación mínima: Jaccard > umbral con alguna oración del set.
        pal_ej = _palabras(oracion)
        parecidos = []
        for r in conjunto:
            j = _jaccard(pal_ej, _palabras(r['oracion']))
            if j >= UMBRAL_JACCARD:
                parecidos.append((j, r['id'], r['oracion']))
        if parecidos:
            parecidos.sort(reverse=True)
            msg = (f'[VARIACION] "{oracion}" se parece a: '
                   + ', '.join(f'{rid} ({j:.0%} "{s}")'
                               for j, rid, s in parecidos[:3]))
            errores.append(msg)

    # 3) Para los ejemplos aceptados, comparar el árbol con el del parser.
    print('Verificando árboles de los ejemplos aceptados con parser_es.py...\n')
    for oracion, datos in ejemplos:
        if not datos.get('aceptada'):
            continue
        res = analizar(oracion)
        if not res.aceptada:
            errores.append(
                f'[ARBOL] "{oracion}" el parser la rechaza: {res.mensajes}')
            continue
        esperado = re.sub(r'\s+', ' ', datos['arbol']).strip()
        obtenido = re.sub(r'\s+', ' ', res.arbol_str).strip()
        if esperado != obtenido:
            errores.append(
                f'[ARBOL] "{oracion}"\n  esperado: {esperado}\n  obtenido: {obtenido}')

    if errores:
        print('ERRORES:')
        for e in errores:
            print(' -', e)
        sys.exit(1)
    print('OK: ningún ejemplo coincide con el set ni es variación mínima;')
    print('los árboles de los ejemplos aceptados concuerdan con el parser.')


if __name__ == '__main__':
    verificar()
