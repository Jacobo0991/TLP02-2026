"""Pruebas de la Fase 2: analizador semántico del español.

Se ejecutan con ``pytest fase2/test_semantico_es.py -v``.

Las pruebas usan directamente ``fase2.semantico_es.verificar`` sobre el
árbol que produce ``parser_es.analizar`` (sin pasar por la consola), y
también comprueban la integración de ``analizar(..., semantico=verificar)``
en al menos un caso de cada rama.
"""

from __future__ import annotations

import pytest

from fase2.parser_es import analizar
from fase2.semantico_es import (
    ErrorSemantico,
    verificar,
    verificar_c1, verificar_c2, verificar_c3, verificar_c4,
    verificar_c5, verificar_c6, verificar_c7, verificar_c8,
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _arbol(oracion: str):
    """Obtiene el árbol del parser; falla la prueba si no es aceptable."""
    r = analizar(oracion)
    assert r.aceptada, (
        f"la oración {oracion!r} no la acepta el parser "
        f"(etapa={r.etapa}, mensajes={r.mensajes})"
    )
    return r.arbol


def _errores(oracion: str) -> list[ErrorSemantico]:
    return verificar(_arbol(oracion))


def _reglas(oracion: str) -> list[str]:
    return [e.regla for e in _errores(oracion)]


# ---------------------------------------------------------------------------
# 1. Un par Correcta / Con error para cada regla.
#    Las correctas no dan ningún error semántico; las erróneas dan
#    EXACTAMENTE la regla esperada (puede repetirse, pero no otras).
# ---------------------------------------------------------------------------

CORRECTAS = [
    # C1 — las casas blancas (dentro de una oración completa).
    'Las casas son blancas.',
    # C2 — al perro.
    'Pedro camina al perro.',
    # C3 — Ana y yo comemos.
    'Ana y yo comemos.',
    # C4 — La casa es blanca.
    'La casa es blanca.',
    # C5 — Ana corre (intr) y Ana compra pan (trans + OD).
    'Ana corre.',
    'Ana compra pan.',
    # C6 — Ana camina con ella.
    'Ana camina con ella.',
    # C7 — Los perros comen pan.
    'Los perros comen pan.',
    # C8 — Ayer comimos. y Ana comerá pronto.
    'Ayer comimos.',
    'Ana comerá pronto.',
]


@pytest.mark.parametrize('oracion', CORRECTAS)
def test_sin_errores_para_correctas(oracion):
    assert _errores(oracion) == []


# (oración, regla esperada) — en todos los casos debe aparecer SOLO esa regla.
ERRONEAS = [
    # C1
    ('El perro negras corre.', 'C1'),
    ('Un casa es blanca.',     'C1'),
    # C2
    ('Pedro camina al casa.',  'C2'),
    # C3
    ('Ana comen pan.',         'C3'),
    ('Los niños come.',        'C3'),
    # C4
    ('La casa es blanco.',     'C4'),
    ('Ana es profesoras.',     'C4'),
    # C5
    ('Ana corre manzanas.',    'C5'),
    ('Ana compra.',            'C5'),
    # C6
    ('Ana mira él.',           'C6'),
    ('Ana camina con yo.',     'C6'),
    # C7
    ('Perros comen pan.',      'C7'),
    # C8
    ('Ana comerá ayer.',       'C8'),
]


@pytest.mark.parametrize('oracion, regla', ERRONEAS)
def test_regla_exacta_para_erroneas(oracion, regla):
    reglas = _reglas(oracion)
    assert reglas, f"se esperaba al menos un error para {oracion!r}"
    assert set(reglas) == {regla}, (
        f"para {oracion!r} se esperaba SOLO {regla}, se obtuvieron {reglas}"
    )


# ---------------------------------------------------------------------------
# 2. Resolución de rasgos del sujeto (C3, C4).
# ---------------------------------------------------------------------------

def test_coord_primera_persona_concuerda():
    # 'Ana y yo' → 1.ª pl; 'comemos' es 1.ª pl.
    assert _errores('Ana y yo comemos.') == []


def test_coord_primera_persona_discuerda_c3():
    # 'Ana y yo' → 1.ª pl; 'comen' es 3.ª pl.
    assert _reglas('Ana y yo comen.') == ['C3']


def test_coord_genero_mixto_prefiere_masculino():
    # 'Ana y Luis' tiene un miembro masculino → género del grupo = m.
    # 'altos' es m. pl. → concuerda. No hay error C4.
    assert _errores('Ana y Luis son altos.') == []


def test_coord_todas_femeninas_rechaza_masculino():
    # 'Ana y María' son todas femeninas → género del grupo = f. 'altos'
    # es m. pl. → C4.
    assert _reglas('Ana y María son altos.') == ['C4']


def test_coord_todas_femeninas_acepta_femenino():
    assert _errores('Ana y María son altas.') == []


def test_sujeto_tacito_genero_libre_1():
    # 'Somos' es 1.ª pl; sujeto tácito → género libre, número = pl.
    assert _errores('Somos altas.') == []


def test_sujeto_tacito_genero_libre_2():
    assert _errores('Somos altos.') == []


# ---------------------------------------------------------------------------
# 3. Tiempos con dos valores (-ar/-ir nosotros: 'caminamos', 'vivimos').
# ---------------------------------------------------------------------------

def test_tiempo_doble_con_ayer():
    # 'caminamos' lleva tiempo = [pres, pret]; 'ayer' pide pret → C8 OK.
    assert _errores('Ayer caminamos en el parque.') == []


# ---------------------------------------------------------------------------
# 4. Casos del nivel 3 del documento.
# ---------------------------------------------------------------------------

def test_n3_pan_come_ana_falla_c7():
    # OVS: la CFG parsea 'Pan' como sujeto escueto → C7.
    assert _reglas('Pan come Ana.') == ['C7']


def test_n3_perro_de_ana_y_luis_falla_c3():
    # 'El perro de Ana y Luis' se coordina fuera del SP (sujeto plural);
    # 'come' es 3.ª sg → C3.
    assert _reglas('El perro de Ana y Luis come.') == ['C3']


# ---------------------------------------------------------------------------
# 5. Errores dentro de un SP.
# ---------------------------------------------------------------------------

def test_c1_dentro_de_sp():
    # 'la niño': DET f. sg. con SUST m. sg. → C1.
    assert _reglas('Ana camina con la niño.') == ['C1']


def test_c2_dentro_de_sp():
    # 'al casa': CONTR_A con SUST f. sg. → C2.
    assert _reglas('Ana camina al casa.') == ['C2']


# ---------------------------------------------------------------------------
# 6. Varias reglas distintas en una misma oración.
# ---------------------------------------------------------------------------

def test_dos_errores_distintos_en_orden():
    # 'Los perros come manzanas rojo.':
    #   - 'come' (3.ª sg.) no concuerda con 'perros' (3.ª pl.) → C3, col 12
    #   - 'rojo' (m. sg.) no concuerda con 'manzanas' (f. pl.) → C1, col 23
    errs = _errores('Los perros come manzanas rojo.')
    assert [e.regla for e in errs] == ['C3', 'C1'], errs
    assert errs[0].columna < errs[1].columna
    assert 'come' in errs[0].mensaje
    assert 'rojo' in errs[1].mensaje


# ---------------------------------------------------------------------------
# 7. Formato y columna de los mensajes (al menos tres distintos).
# ---------------------------------------------------------------------------

def test_formato_y_columna_c4_blanco():
    errs = _errores('La casa es blanco.')
    assert len(errs) == 1
    e = errs[0]
    assert e.regla == 'C4'
    assert e.columna == 12
    assert str(e) == (
        "Error semántico [col 12]: el atributo 'blanco' (m. sg.) "
        "no concuerda con el sujeto (f. sg.)"
    )


def test_formato_y_columna_c3_come():
    # 'Los perros come.': 'Los '=cols 1-4, 'perros '=cols 5-11, 'come'=col 12.
    errs = _errores('Los perros come.')
    assert len(errs) == 1
    e = errs[0]
    assert e.regla == 'C3'
    assert e.columna == 12
    assert str(e) == (
        "Error semántico [col 12]: el verbo 'come' (3.ª sg.) no concuerda "
        "con el sujeto (3.ª pl.)"
    )


def test_formato_y_columna_c7_perros():
    errs = _errores('Perros comen pan.')
    assert len(errs) == 1
    e = errs[0]
    assert e.regla == 'C7'
    assert e.columna == 1
    assert str(e) == (
        "Error semántico [col 1]: el sujeto 'Perros' necesita un determinante"
    )


# ---------------------------------------------------------------------------
# 8. Integración: analizar(..., semantico=verificar) devuelve etapa correcta.
# ---------------------------------------------------------------------------

def test_integracion_semantico_rechaza():
    r = analizar('La casa es blanco.', semantico=verificar)
    assert not r.aceptada
    assert r.etapa == 'semantico'
    assert any("'blanco'" in m for m in r.mensajes)


def test_integracion_semantico_acepta_sin_errores():
    r = analizar('La casa es blanca.', semantico=verificar)
    assert r.aceptada
    assert r.etapa is None
    assert r.mensajes == []


def test_integracion_semantico_no_se_ejecuta_si_hay_error_lexico():
    # 'lo' no está en el léxico → corte antes del semántico.
    r = analizar('Ana lo come.', semantico=verificar)
    assert not r.aceptada
    assert r.etapa == 'lexico'


def test_integracion_semantico_no_se_ejecuta_si_hay_error_sintactico():
    # 'Ayer Ana comió pan.' rechaza sintácticamente en 'Ana'.
    r = analizar('Ayer Ana comió pan.', semantico=verificar)
    assert not r.aceptada
    assert r.etapa == 'sintactico'


# ---------------------------------------------------------------------------
# 9. Reglas que NO deben confundirse (negativos puntuales).
# ---------------------------------------------------------------------------

def test_c6_permite_el_tras_preposicion():
    # 'con él' es correcto: él (PRON m sg) no está en {yo, tú}.
    assert _errores('Ana camina con él.') == []


def test_c5_ambos_sin_od_pasa():
    # 'comer' es 'ambos': puede ir sin OD.
    assert _errores('Ana come.') == []


def test_c5_ambos_con_od_pasa():
    assert _errores('Ana come pan.') == []


def test_c2_al_el_perro_falla():
    # 'a el perro' → debería ser 'al perro'.
    assert _reglas('Ana camina a el perro.') == ['C2']


def test_c2_de_el_profesor_falla():
    # 'de el profesor' → debería ser 'del profesor'. Ocurre dentro de
    # un SP del verbo (PREP_DE + DET el) y C2 lo detecta.
    assert 'C2' in _reglas('Ana camina de el parque a el jardín.')
