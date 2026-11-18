"""Pruebas unitarias con pytest para lexer.py.

Cubre:
- El ejemplo de la sección "Ejemplo de tokenización" (21 tokens exactos).
- El ejemplo con 3 errores de la misma sección.
- Que los dos archivos válidos no produzcan errores.
- Cada uno de los 10 errores léxicos, con su línea, columna y mensaje.
- Casos de borde pedidos: reservadas vs identificadores, literales numéricos,
  OP_PUNTO vs LIT_FLOAT, los tres niveles de operadores de <, <<, <<=, las
  variantes de -, >> dentro de plantillas, comentario de bloque multilínea.
"""

from pathlib import Path

import pytest

import lexer
from lexer import (
    Token, ErrorLexico, tokenizar,
    KW_FOR, KW_INT, KW_LONG, KW_CONST, KW_RETURN, KW_WHILE, KW_IF,
    KW_USING, KW_NAMESPACE, KW_TYPEDEF, KW_STRUCT, KW_NEW, KW_DELETE,
    KW_THIS, KW_OPERATOR,
    ID, LIT_INT, LIT_HEX, LIT_FLOAT, LIT_CHAR, LIT_STRING,
    LIT_BOOL, LIT_NULLPTR,
    OP_ASIG, OP_INC, OP_DEC, OP_RESTA_ASIG, OP_SHL, OP_SHR, OP_SHL_ASIG,
    OP_MENOR, OP_MAYOR, OP_MENOR_IG, OP_MAYOR_IG,
    OP_SUMA, OP_RESTA, OP_MULT, OP_FLECHA, OP_PUNTO, OP_MOD,
    OP_AND_BIT,
    PAR_IZQ, PAR_DER, COR_IZQ, COR_DER, LLAVE_IZQ, LLAVE_DER,
    PUNTO_COMA, COMA, DOS_PUNTOS,
    DIR_INCLUDE, DIR_DEFINE,
    EOF,
)


PRUEBAS = Path(__file__).parent / 'pruebas' / 'lexer'


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def tipos_y_lexemas(tokens):
    """Lista de (tipo, lexema) ignorando el EOF para comparaciones cortas."""
    return [(t.tipo, t.lexema) for t in tokens if t.tipo != EOF]


# ---------------------------------------------------------------------------
# 1) Ejemplo de la sección "Ejemplo de tokenización".
# ---------------------------------------------------------------------------

def test_ejemplo_for_linea_5():
    # La línea pedida debe quedar en la línea 5: 4 líneas vacías antes.
    codigo = '\n' * 4 + '    for (int i = 0; i < n; i++) cin >> a[i];\n'
    tokens, errores = tokenizar(codigo)
    assert errores == []

    esperados = [
        (KW_FOR,      'for', 5, 5),
        (PAR_IZQ,     '(',   5, 9),
        (KW_INT,      'int', 5, 10),
        (ID,          'i',   5, 14),
        (OP_ASIG,     '=',   5, 16),
        (LIT_INT,     '0',   5, 18),
        (PUNTO_COMA,  ';',   5, 19),
        (ID,          'i',   5, 21),
        (OP_MENOR,    '<',   5, 23),
        (ID,          'n',   5, 25),
        (PUNTO_COMA,  ';',   5, 26),
        (ID,          'i',   5, 28),
        (OP_INC,      '++',  5, 29),
        (PAR_DER,     ')',   5, 31),
        (ID,          'cin', 5, 33),
        (OP_SHR,      '>>',  5, 37),
        (ID,          'a',   5, 40),
        (COR_IZQ,     '[',   5, 41),
        (ID,          'i',   5, 42),
        (COR_DER,     ']',   5, 43),
        (PUNTO_COMA,  ';',   5, 44),
    ]
    # Excluimos el EOF final para comparar los 21 tokens exactos.
    sin_eof = [t for t in tokens if t.tipo != EOF]
    assert len(sin_eof) == 21
    for t, (tipo, lex, ln, col) in zip(sin_eof, esperados):
        assert (t.tipo, t.lexema, t.linea, t.columna) == (tipo, lex, ln, col)


# ---------------------------------------------------------------------------
# 2) Ejemplo con errores: int x@ = 08 + 'ab'; en la línea 7.
# ---------------------------------------------------------------------------

def test_ejemplo_errores_linea_7():
    codigo = '\n' * 6 + "int x@ = 08 + 'ab';\n"
    _, errores = tokenizar(codigo)
    assert len(errores) == 3
    assert (errores[0].linea, errores[0].columna, errores[0].mensaje) == (
        7, 6, "carácter inválido '@'",
    )
    assert (errores[1].linea, errores[1].columna, errores[1].mensaje) == (
        7, 10, "literales octales no soportados '08'",
    )
    assert (errores[2].linea, errores[2].columna, errores[2].mensaje) == (
        7, 15, 'literal de carácter con varios caracteres',
    )
    # El formato del __str__ debe ser el exacto de la especificación.
    assert str(errores[0]) == "Error léxico [línea 7, col 6]: carácter inválido '@'"


# ---------------------------------------------------------------------------
# 3) Los dos archivos válidos deben tokenizar sin errores.
# ---------------------------------------------------------------------------

def test_valido_basico_sin_errores():
    codigo = (PRUEBAS / 'valido_basico.cpp').read_text(encoding='utf-8')
    tokens, errores = tokenizar(codigo)
    assert errores == []
    # Prueba de cordura: debe contener el #include y los tokens principales.
    tipos = [t.tipo for t in tokens]
    assert DIR_INCLUDE in tipos
    assert DIR_DEFINE in tipos
    assert KW_USING in tipos
    assert KW_NAMESPACE in tipos
    assert KW_TYPEDEF in tipos
    assert LIT_FLOAT in tipos  # 1e18
    assert LIT_NULLPTR in tipos


def test_valido_structs_sin_errores():
    codigo = (PRUEBAS / 'valido_structs.cpp').read_text(encoding='utf-8')
    tokens, errores = tokenizar(codigo)
    assert errores == []
    tipos = [t.tipo for t in tokens]
    assert KW_STRUCT in tipos
    assert KW_OPERATOR in tipos
    assert KW_NEW in tipos
    assert KW_THIS not in tipos   # El ejemplo no usa this, pero sí nullptr.
    assert LIT_NULLPTR in tipos
    assert OP_FLECHA in tipos     # r->val, r->izq, etc.


# ---------------------------------------------------------------------------
# 4) Cada uno de los 10 errores léxicos.
# ---------------------------------------------------------------------------

def _tokenizar_archivo(nombre: str):
    return tokenizar((PRUEBAS / nombre).read_text(encoding='utf-8'))


def test_error_01_caracter_invalido():
    _, errs = _tokenizar_archivo('error_01_caracter.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 10
    assert errs[0].mensaje == "carácter inválido '@'"


def test_error_02_numero_malformado():
    _, errs = _tokenizar_archivo('error_02_numero.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 13
    assert errs[0].mensaje == "número mal formado '123abc'"


def test_error_03_octal():
    _, errs = _tokenizar_archivo('error_03_octal.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 13
    assert errs[0].mensaje == "literales octales no soportados '017'"


def test_error_04_cadena_sin_cerrar():
    _, errs = _tokenizar_archivo('error_04_cadena_sin_cerrar.cpp')
    assert len(errs) >= 1
    assert errs[0].linea == 2 and errs[0].columna == 13
    assert errs[0].mensaje == 'cadena sin cerrar'


def test_error_05_escape_invalido():
    _, errs = _tokenizar_archivo('error_05_escape_invalido.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 13
    assert errs[0].mensaje == r"secuencia de escape inválida '\q'"


def test_error_06_caracter_sin_cerrar():
    _, errs = _tokenizar_archivo('error_06_caracter_sin_cerrar.cpp')
    assert len(errs) >= 1
    assert errs[0].linea == 2 and errs[0].columna == 14
    assert errs[0].mensaje == 'literal de carácter sin cerrar'


def test_error_07_caracter_vacio():
    _, errs = _tokenizar_archivo('error_07_caracter_vacio.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 14
    assert errs[0].mensaje == 'literal de carácter vacío'


def test_error_08_varios_caracteres():
    _, errs = _tokenizar_archivo('error_08_varios_caracteres.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 14
    assert errs[0].mensaje == 'literal de carácter con varios caracteres'


def test_error_09_comentario_sin_cerrar():
    _, errs = _tokenizar_archivo('error_09_comentario_sin_cerrar.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 2 and errs[0].columna == 5
    assert errs[0].mensaje == 'comentario sin cerrar (abierto en línea 2)'


def test_error_10_directiva_no_soportada():
    _, errs = _tokenizar_archivo('error_10_directiva.cpp')
    assert len(errs) == 1
    assert errs[0].linea == 1 and errs[0].columna == 1
    assert errs[0].mensaje == "directiva no soportada '#pragma'"


# ---------------------------------------------------------------------------
# 5) Casos de borde pedidos explícitamente.
# ---------------------------------------------------------------------------

def test_reservada_vs_identificador():
    tokens, errs = tokenizar('int intx;')
    assert errs == []
    assert tipos_y_lexemas(tokens) == [
        (KW_INT, 'int'),
        (ID, 'intx'),
        (PUNTO_COMA, ';'),
    ]


def test_1e9_y_1LL_vs_123abc():
    tokens, errs = tokenizar('1e9 1LL 123abc')
    # 1e9 y 1LL son válidos; 123abc es número mal formado.
    assert len(errs) == 1
    assert errs[0].mensaje == "número mal formado '123abc'"
    assert tipos_y_lexemas(tokens) == [
        (LIT_FLOAT, '1e9'),
        (LIT_INT, '1LL'),
    ]
    # Valores convertidos.
    valores = {t.lexema: t.valor for t in tokens if t.tipo != EOF}
    assert valores['1e9'] == 1e9
    assert valores['1LL'] == 1


def test_punto_decimal_vs_punto_acceso():
    # .5 es LIT_FLOAT; a.size() tiene OP_PUNTO en medio.
    tokens, errs = tokenizar('.5 a.size()')
    assert errs == []
    assert tipos_y_lexemas(tokens) == [
        (LIT_FLOAT, '.5'),
        (ID, 'a'),
        (OP_PUNTO, '.'),
        (ID, 'size'),
        (PAR_IZQ, '('),
        (PAR_DER, ')'),
    ]


def test_menor_versiones():
    # <<=, << y < deben ser tres tokens distintos.
    tokens, errs = tokenizar('<<= << <')
    assert errs == []
    assert tipos_y_lexemas(tokens) == [
        (OP_SHL_ASIG, '<<='),
        (OP_SHL, '<<'),
        (OP_MENOR, '<'),
    ]


def test_resta_variantes():
    # ->, --, -=: ninguno debe partirse en dos tokens.
    tokens, errs = tokenizar('-> -- -=')
    assert errs == []
    assert tipos_y_lexemas(tokens) == [
        (OP_FLECHA, '->'),
        (OP_DEC, '--'),
        (OP_RESTA_ASIG, '-='),
    ]


def test_vector_vector_int_produce_shr():
    # vector<vector<int>> debe cerrar con OP_SHR, no con dos OP_MAYOR.
    tokens, errs = tokenizar('vector<vector<int>>')
    assert errs == []
    assert tipos_y_lexemas(tokens) == [
        (ID, 'vector'),
        (OP_MENOR, '<'),
        (ID, 'vector'),
        (OP_MENOR, '<'),
        (KW_INT, 'int'),
        (OP_SHR, '>>'),
    ]


def test_comentario_bloque_multilinea_actualiza_linea_y_columna():
    # Tres líneas de comentario y un identificador en la línea 3, col 4.
    codigo = '/* a\nb\nc */x\n'
    tokens, errs = tokenizar(codigo)
    assert errs == []
    sin_eof = [t for t in tokens if t.tipo != EOF]
    assert len(sin_eof) == 1
    assert sin_eof[0].tipo == ID
    assert sin_eof[0].lexema == 'x'
    assert sin_eof[0].linea == 3
    # El comentario termina en "c */" que ocupa 4 cols en la línea 3, por
    # lo que el siguiente token empieza en la columna 5.
    assert sin_eof[0].columna == 5


# ---------------------------------------------------------------------------
# 6) Extras pequeños útiles para validar decodificación.
# ---------------------------------------------------------------------------

def test_decodificacion_cadena_y_caracter():
    tokens, errs = tokenizar(r'"a\nb" ' + r"'\t'" + ' "\\\\"')
    # Valores: "a\nb" (4 chars tras decode), '\t', "\\" (1 char tras decode).
    assert errs == []
    cadenas = [t for t in tokens if t.tipo in (LIT_STRING, LIT_CHAR)]
    assert cadenas[0].valor == 'a\nb'
    assert cadenas[1].valor == '\t'
    assert cadenas[2].valor == '\\'


def test_dir_include_y_define_valores():
    codigo = '#include <bits/stdc++.h>\n#define MOD 1000000007\n'
    tokens, errs = tokenizar(codigo)
    assert errs == []
    inc = next(t for t in tokens if t.tipo == DIR_INCLUDE)
    assert inc.valor == 'bits/stdc++.h'
    defi = next(t for t in tokens if t.tipo == DIR_DEFINE)
    assert defi.valor == ('MOD', '1000000007')


def test_hexadecimal_y_booleano():
    tokens, errs = tokenizar('0xFF true false nullptr')
    assert errs == []
    valores = [(t.tipo, t.valor) for t in tokens if t.tipo != EOF]
    assert valores == [
        (LIT_HEX, 255),
        (LIT_BOOL, True),
        (LIT_BOOL, False),
        (LIT_NULLPTR, None),
    ]


def test_recuperacion_sigue_tras_error():
    # Tres errores distintos en una sola línea; al final queda el PUNTO_COMA.
    _, errs = tokenizar("x@ + 08 + 'ab';\n")
    tipos_err = [(e.mensaje.split()[0], e.columna) for e in errs]
    assert len(errs) == 3
    # El lexer no se detuvo: si se hubiera detenido al primer error, no
    # habríamos visto el error del octal ni el del carácter.
    assert tipos_err[0][1] < tipos_err[1][1] < tipos_err[2][1]
