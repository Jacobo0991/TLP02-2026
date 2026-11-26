"""Pruebas de la Fase 2: léxico del español, parser LL(1) y notación de
árboles. Se ejecutan con `pytest fase2/test_parser_es.py -v`.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from fase2.lexer_es import LEXICO, tokenizar
from fase2.parser_es import analizar


# ---------------------------------------------------------------------------
# 1) Léxico: exactamente 400 formas y conteos por categoría.
# ---------------------------------------------------------------------------

def test_lexico_tiene_400_formas():
    assert len(LEXICO) == 400


def test_lexico_conteos_por_categoria():
    esperado = {
        'VERBO': 228,
        'ADJ': 52,
        'SUST': 40,
        'COP': 30,
        'ADV': 11,
        'PREP': 9,
        'DET': 8,
        'PRON': 8,
        'NPROP': 6,
        'INTENS': 2,
        'CONJ': 2,
        'NEG': 1,
        'PREP_DE': 1,
        'CONTR_A': 1,
        'CONTR_DE': 1,
    }
    c = Counter(cat for cat, _ in LEXICO.values())
    assert dict(c) == esperado


def test_lexico_ninguna_forma_en_dos_categorias():
    # LEXICO es dict[str, (cat, rasgos)], pero si una forma colisionara con
    # otra categoría, _construir_lexico habría lanzado CargaLexicoError. Aquí
    # lo validamos de forma independiente contando por clave.
    vistas = {}
    for forma, (cat, _) in LEXICO.items():
        assert forma not in vistas or vistas[forma] == cat
        vistas[forma] = cat


# ---------------------------------------------------------------------------
# 2) Los 4 árboles canónicos del documento, EXACTAMENTE.
# ---------------------------------------------------------------------------

def _norm(cadena: str) -> str:
    """Normaliza espacios para comparar cadenas de corchetes."""
    return re.sub(r'\s+', ' ', cadena).strip()


EJEMPLOS_ARBOLES = [
    (
        'El perro negro come manzanas.',
        '(O (SUJ (SN (DET El) (SUST perro) (SADJ (ADJ negro)))) '
        '(SV (VERBO come) (OD (SN (SUST manzanas)))) (PUNTO .))',
    ),
    (
        'Ana no compró los libros del profesor ayer.',
        '(O (SUJ (SN (NPROP Ana))) '
        '(SV (NEG no) (VERBO compró) '
        '(OD (SN (DET los) (SUST libros) '
        '(SP (CONTR_DE del) (SN (SUST profesor))))) '
        '(CC (SADV (ADV ayer)))) (PUNTO .))',
    ),
    (
        'Ana y Luis son muy altos.',
        '(O (SUJ (SN (SN (NPROP Ana)) (CONJ y) (SN (NPROP Luis)))) '
        '(SV (COP son) (ATRIB (SADJ (INTENS muy) (ADJ altos)))) (PUNTO .))',
    ),
    (
        'Siempre caminamos en el parque.',
        '(O (SV (SADV (ADV Siempre)) (VERBO caminamos) '
        '(CC (SP (PREP en) (SN (DET el) (SUST parque))))) (PUNTO .))',
    ),
]


@pytest.mark.parametrize('oracion, esperado', EJEMPLOS_ARBOLES)
def test_arbol_canonico(oracion, esperado):
    r = analizar(oracion)
    assert r.aceptada, r.mensajes
    assert _norm(r.arbol_str) == _norm(esperado)


# ---------------------------------------------------------------------------
# 3) Aceptaciones y rechazos del nivel 3 (tabla del documento).
# ---------------------------------------------------------------------------

ACEPTADAS_NIVEL3 = [
    'Pan come Ana.',
    'Ana mira al niño con el libro.',
    'Ana compró libros de María.',
    'El perro de Ana y Luis come.',
]


@pytest.mark.parametrize('oracion', ACEPTADAS_NIVEL3)
def test_nivel3_aceptadas(oracion):
    r = analizar(oracion)
    assert r.aceptada, r.mensajes


def test_libros_de_maria_une_al_sustantivo():
    # R12: 'de María' queda unido a 'libros' (SP dentro del OD, no como CC).
    r = analizar('Ana compró libros de María.')
    assert r.aceptada
    assert '(OD (SN (SUST libros) (SP (PREP_DE de)' in r.arbol_str


def test_perro_de_ana_y_luis_coordina_fuera():
    # 'Luis' se coordina con 'el perro de Ana', no con 'Ana'.
    r = analizar('El perro de Ana y Luis come.')
    assert r.aceptada
    assert r.arbol_str.startswith(
        '(O (SUJ (SN (SN (DET El) (SUST perro) '
        '(SP (PREP_DE de) (SN (NPROP Ana)))) '
        '(CONJ y) (SN (NPROP Luis))))'
    )


# Rechazos sintácticos: (oración, token donde falla, columna, categoría del
# token encontrado).
RECHAZOS_SINTAC = [
    ('Ayer Ana comió pan.',              'Ana',          6,  'NPROP'),
    ('Ana come y Luis bebe.',            'y',            10, 'CONJ'),
    ('Ana no siempre come pan.',         'siempre',      8,  'ADV'),
    ('Ana come pan muy rápidamente.',    'rápidamente',  18, 'ADV'),
    ('El libro sobre la mesa es nuevo.', 'sobre',        10, 'PREP'),
]


@pytest.mark.parametrize('oracion, palabra, col, cat', RECHAZOS_SINTAC)
def test_nivel3_rechazos_sintacticos(oracion, palabra, col, cat):
    r = analizar(oracion)
    assert not r.aceptada
    assert r.etapa == 'sintactico'
    assert len(r.mensajes) == 1
    msg = r.mensajes[0]
    assert f'[col {col}]' in msg
    assert f"'{palabra}'" in msg
    assert f'({cat})' in msg


# Palabras fuera del vocabulario → rechazo léxico.
RECHAZOS_LEXICOS = [
    ('El perro que corre es negro.',        'que'),
    ('Ana lo come.',                        'lo'),
    ('Ana ha comido pan.',                  'ha'),
    ('Ana va a comer pan.',                 'va'),
    ('Las manzanas fueron compradas por Ana.', 'compradas'),
    ('¿Ana come pan?',                      '¿'),
]


@pytest.mark.parametrize('oracion, forma', RECHAZOS_LEXICOS)
def test_nivel3_rechazos_lexicos(oracion, forma):
    r = analizar(oracion)
    assert not r.aceptada
    assert r.etapa == 'lexico'
    assert any(forma in m for m in r.mensajes)


# ---------------------------------------------------------------------------
# 4) Casos de cobertura (sujeto tácito, coord con comas, al/del, atributo
#    SN, OD sin determinante, ADJ antes del SUST, negación, tres tiempos,
#    oración sin punto final).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('oracion', [
    'Siempre caminamos en el parque.',        # sujeto tácito
    'Ana, Luis y Pedro comen pan.',           # coord con comas
    'Ana mira al niño.',                      # contracción 'al'
    'Ana compró el libro del profesor.',      # contracción 'del'
    'Ana es una profesora.',                  # atributo SN
    'Ana come manzanas.',                     # OD sin determinante
    'El pequeño perro corre.',                # ADJ antes del SUST
    'Ana no come.',                           # negación
    'Ana come pan.',                          # presente
    'Ana compró pan.',                        # pretérito
    'Ana comprará pan.',                      # futuro
    'Ana come pan',                           # sin punto final
])
def test_cobertura_aceptadas(oracion):
    r = analizar(oracion)
    assert r.aceptada, (oracion, r.mensajes)


def test_adjetivo_pre_sustantivo_se_emite_como_hoja():
    # NOMINAL → ADJ NUCLEO_N: el ADJ pre-nominal no se envuelve en SADJ.
    r = analizar('El pequeño perro corre.')
    assert r.aceptada
    assert '(SN (DET El) (ADJ pequeño) (SUST perro))' in r.arbol_str


def test_sujeto_tacito_no_emite_nodo_suj():
    r = analizar('Siempre caminamos en el parque.')
    assert r.aceptada
    # No hay SUJ en el árbol porque el sujeto es tácito.
    assert '(SUJ' not in r.arbol_str


def test_coordinacion_con_comas():
    r = analizar('Ana, Luis y Pedro comen pan.')
    assert r.aceptada
    assert r.arbol_str.startswith(
        '(O (SUJ (SN (SN (NPROP Ana)) (COMA ,) '
        '(SN (NPROP Luis)) (CONJ y) (SN (NPROP Pedro))))'
    )


# ---------------------------------------------------------------------------
# 5) El árbol se puede reconstruir con nltk.Tree.fromstring.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('oracion, _esperado', EJEMPLOS_ARBOLES)
def test_a_nltk_reconstruible(oracion, _esperado):
    import nltk

    r = analizar(oracion)
    assert r.aceptada
    arbol = nltk.Tree.fromstring(r.arbol_str)
    # fromstring devuelve un Tree; su label es la etiqueta raíz (O).
    assert arbol.label() == 'O'


# ---------------------------------------------------------------------------
# 6) Tokens de palabra conservan rasgos y lexema original.
# ---------------------------------------------------------------------------

def test_token_conserva_lexema_original():
    tokens, errores = tokenizar('Ana come.')
    assert not errores
    # 'Ana' se guarda con su mayúscula original.
    assert tokens[0].lexema == 'Ana'
    assert tokens[0].tipo == 'NPROP'
    # Y los rasgos sí vienen del diccionario (en minúsculas internamente).
    assert tokens[0].valor['genero'] == 'f'


def test_nosotros_presente_y_preterito_comparten_forma():
    # 'caminamos' y 'vivimos' deben llevar tiempo = [pres, pret].
    _, _ = tokenizar('caminamos vivimos')
    assert sorted(LEXICO['caminamos'][1]['tiempo']) == ['pres', 'pret']
    assert sorted(LEXICO['vivimos'][1]['tiempo']) == ['pres', 'pret']
