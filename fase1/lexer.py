"""Analizador léxico para un subconjunto de C++ orientado a programación competitiva.

Implementación de la Fase 1 del proyecto de Teoría de Lenguajes.
La especificación completa está en docs/especificacion_tokens.md.

Arquitectura:
- PATRONES: lista ordenada de (nombre_de_tipo, regex). Es la fuente de datos
  que separa la tabla léxica del motor. En la Fase 2 solo cambia esta tabla.
- _MAESTRA: expresión regular maestra construida a partir de PATRONES, con
  grupos con nombre. El orden importa: Python prueba las alternativas en
  orden y se queda con la primera que coincide (no con la más larga).
- tokenizar(codigo): aplica la maestra con re.finditer, lleva línea y columna,
  valida en código los errores 4 a 8 (cadenas y caracteres) y hace recuperación
  en modo pánico: reporta cada error y sigue tokenizando.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Tipos de token (constantes de módulo, importables desde semantico.py).
# ---------------------------------------------------------------------------

# Palabras reservadas: tipos primitivos.
KW_INT = 'KW_INT'
KW_LONG = 'KW_LONG'
KW_SHORT = 'KW_SHORT'
KW_CHAR = 'KW_CHAR'
KW_BOOL = 'KW_BOOL'
KW_FLOAT = 'KW_FLOAT'
KW_DOUBLE = 'KW_DOUBLE'
KW_VOID = 'KW_VOID'
KW_AUTO = 'KW_AUTO'

# Palabras reservadas: modificadores.
KW_UNSIGNED = 'KW_UNSIGNED'
KW_SIGNED = 'KW_SIGNED'
KW_CONST = 'KW_CONST'
KW_CONSTEXPR = 'KW_CONSTEXPR'
KW_STATIC = 'KW_STATIC'

# Palabras reservadas: control de flujo.
KW_IF = 'KW_IF'
KW_ELSE = 'KW_ELSE'
KW_FOR = 'KW_FOR'
KW_WHILE = 'KW_WHILE'
KW_DO = 'KW_DO'
KW_SWITCH = 'KW_SWITCH'
KW_CASE = 'KW_CASE'
KW_DEFAULT = 'KW_DEFAULT'
KW_BREAK = 'KW_BREAK'
KW_CONTINUE = 'KW_CONTINUE'
KW_RETURN = 'KW_RETURN'

# Palabras reservadas: declaraciones.
KW_USING = 'KW_USING'
KW_NAMESPACE = 'KW_NAMESPACE'
KW_TYPEDEF = 'KW_TYPEDEF'
KW_STRUCT = 'KW_STRUCT'

# Palabras reservadas: punteros / memoria.
KW_NEW = 'KW_NEW'
KW_DELETE = 'KW_DELETE'
KW_THIS = 'KW_THIS'

# Palabras reservadas: otras.
KW_SIZEOF = 'KW_SIZEOF'
KW_OPERATOR = 'KW_OPERATOR'

# Identificadores y literales.
ID = 'ID'
LIT_INT = 'LIT_INT'
LIT_HEX = 'LIT_HEX'
LIT_FLOAT = 'LIT_FLOAT'
LIT_CHAR = 'LIT_CHAR'
LIT_STRING = 'LIT_STRING'
LIT_BOOL = 'LIT_BOOL'
LIT_NULLPTR = 'LIT_NULLPTR'

# Operadores aritméticos.
OP_SUMA = 'OP_SUMA'
OP_RESTA = 'OP_RESTA'
OP_MULT = 'OP_MULT'
OP_DIV = 'OP_DIV'
OP_MOD = 'OP_MOD'

# Incremento / decremento.
OP_INC = 'OP_INC'
OP_DEC = 'OP_DEC'

# Relacionales.
OP_IGUAL = 'OP_IGUAL'
OP_DIST = 'OP_DIST'
OP_MENOR = 'OP_MENOR'
OP_MAYOR = 'OP_MAYOR'
OP_MENOR_IG = 'OP_MENOR_IG'
OP_MAYOR_IG = 'OP_MAYOR_IG'

# Lógicos.
OP_AND = 'OP_AND'
OP_OR = 'OP_OR'
OP_NOT = 'OP_NOT'

# De bits.
OP_AND_BIT = 'OP_AND_BIT'
OP_OR_BIT = 'OP_OR_BIT'
OP_XOR = 'OP_XOR'
OP_NOT_BIT = 'OP_NOT_BIT'
OP_SHL = 'OP_SHL'
OP_SHR = 'OP_SHR'

# Asignación (simple y compuesta).
OP_ASIG = 'OP_ASIG'
OP_SUMA_ASIG = 'OP_SUMA_ASIG'
OP_RESTA_ASIG = 'OP_RESTA_ASIG'
OP_MULT_ASIG = 'OP_MULT_ASIG'
OP_DIV_ASIG = 'OP_DIV_ASIG'
OP_MOD_ASIG = 'OP_MOD_ASIG'
OP_AND_ASIG = 'OP_AND_ASIG'
OP_OR_ASIG = 'OP_OR_ASIG'
OP_XOR_ASIG = 'OP_XOR_ASIG'
OP_SHL_ASIG = 'OP_SHL_ASIG'
OP_SHR_ASIG = 'OP_SHR_ASIG'

# Ternario, ámbito y acceso.
OP_TERNARIO = 'OP_TERNARIO'
DOS_PUNTOS = 'DOS_PUNTOS'
OP_AMBITO = 'OP_AMBITO'
OP_PUNTO = 'OP_PUNTO'
OP_FLECHA = 'OP_FLECHA'

# Delimitadores.
PAR_IZQ = 'PAR_IZQ'
PAR_DER = 'PAR_DER'
COR_IZQ = 'COR_IZQ'
COR_DER = 'COR_DER'
LLAVE_IZQ = 'LLAVE_IZQ'
LLAVE_DER = 'LLAVE_DER'
PUNTO_COMA = 'PUNTO_COMA'
COMA = 'COMA'

# Directivas.
DIR_INCLUDE = 'DIR_INCLUDE'
DIR_DEFINE = 'DIR_DEFINE'

# Fin de archivo.
EOF = 'EOF'


# ---------------------------------------------------------------------------
# Dataclasses expuestas.
# ---------------------------------------------------------------------------

@dataclass
class Token:
    tipo: str
    lexema: str
    linea: int
    columna: int
    valor: object = None


@dataclass
class ErrorLexico:
    mensaje: str
    linea: int
    columna: int

    def __str__(self) -> str:
        return f"Error léxico [línea {self.linea}, col {self.columna}]: {self.mensaje}"


# ---------------------------------------------------------------------------
# Diccionario de palabras reservadas (37 entradas).
# Cada entrada es (tipo_de_token, valor_asociado).
# Las palabras true/false/nullptr son literales con nombre: emiten LIT_BOOL o
# LIT_NULLPTR en lugar de un token KW_*.
# ---------------------------------------------------------------------------

RESERVADAS: dict[str, tuple[str, object]] = {
    'int': (KW_INT, None),
    'long': (KW_LONG, None),
    'short': (KW_SHORT, None),
    'char': (KW_CHAR, None),
    'bool': (KW_BOOL, None),
    'float': (KW_FLOAT, None),
    'double': (KW_DOUBLE, None),
    'void': (KW_VOID, None),
    'auto': (KW_AUTO, None),
    'unsigned': (KW_UNSIGNED, None),
    'signed': (KW_SIGNED, None),
    'const': (KW_CONST, None),
    'constexpr': (KW_CONSTEXPR, None),
    'static': (KW_STATIC, None),
    'if': (KW_IF, None),
    'else': (KW_ELSE, None),
    'for': (KW_FOR, None),
    'while': (KW_WHILE, None),
    'do': (KW_DO, None),
    'switch': (KW_SWITCH, None),
    'case': (KW_CASE, None),
    'default': (KW_DEFAULT, None),
    'break': (KW_BREAK, None),
    'continue': (KW_CONTINUE, None),
    'return': (KW_RETURN, None),
    'using': (KW_USING, None),
    'namespace': (KW_NAMESPACE, None),
    'typedef': (KW_TYPEDEF, None),
    'struct': (KW_STRUCT, None),
    'new': (KW_NEW, None),
    'delete': (KW_DELETE, None),
    'this': (KW_THIS, None),
    'sizeof': (KW_SIZEOF, None),
    'operator': (KW_OPERATOR, None),
    'true': (LIT_BOOL, True),
    'false': (LIT_BOOL, False),
    'nullptr': (LIT_NULLPTR, None),
}


# ---------------------------------------------------------------------------
# Tabla de patrones (DATOS). En Fase 2 cambiamos esto y el motor se reutiliza.
# El orden es parte de la especificación: alternancia en Python prueba las
# alternativas en orden y se queda con la primera que coincide.
# ---------------------------------------------------------------------------

# Fragmento auxiliar: el sufijo entero (u, l, ll o combinaciones).
# Nota: dentro de (ll|LL|l|L) ponemos las dos letras ANTES de la sola, para
# que "LL" no se parta en "L" + "L".
_SUF_ENT = r'(?:[uU](?:ll|LL|l|L)?|(?:ll|LL|l|L)[uU]?)'

PATRONES: list[tuple[str, str]] = [
    # 1) Comentarios. El válido va antes que el no cerrado para que, cuando
    #    haya cierre, lo tome. Ambos van antes que OP_DIV.
    ('COMENTARIO_BLOQUE',            r'/\*[\s\S]*?\*/'),
    ('COMENTARIO_LINEA',             r'//[^\n]*'),
    ('COMENTARIO_BLOQUE_NO_CERRADO', r'/\*[\s\S]*'),

    # 2) Directivas. La inválida va al final para no robarle el match a las válidas.
    ('DIR_INCLUDE',  r'\#[ \t]*include[ \t]*(?:<[^>\n]+>|"[^"\n]+")'),
    ('DIR_DEFINE',   r'\#[ \t]*define[ \t]+[A-Za-z_][A-Za-z_0-9]*[^\n]*'),
    ('DIR_INVALIDA', r'\#[^\n]*'),

    # 3) Literales de texto. Aceptamos el literal aunque esté sin cerrar,
    #    vacío o largo; el código valida después y emite el mensaje correcto.
    ('LIT_STRING', r'"(?:[^"\\\n]|\\.)*"?'),
    ('LIT_CHAR',   r"'(?:[^'\\\n]|\\.)*'?"),

    # 4) Literales numéricos. Cada uno termina con (?![\w.]) para que
    #    "123abc" o "1.2.3" no se corten en "123"+"abc" o "1.2"+".3".
    ('LIT_HEX',   r'0[xX][0-9A-Fa-f]+' + _SUF_ENT + r'?(?![\w.])'),
    ('LIT_FLOAT', r'(?:\d+\.\d*(?:[eE][+-]?\d+)?'
                  r'|\.\d+(?:[eE][+-]?\d+)?'
                  r'|\d+[eE][+-]?\d+)'
                  r'[fFlL]?(?![\w.])'),
    ('LIT_OCTAL', r'0\d+(?![\w.])'),
    ('LIT_INT',   r'\d+' + _SUF_ENT + r'?(?![\w.])'),

    # 5) Número mal formado (va después de los numéricos válidos).
    ('NUM_MALFORMADO', r'\d[\w.]*'),

    # 6) Identificador. Después se cruza contra RESERVADAS.
    ('ID', r'[A-Za-z_][A-Za-z_0-9]*'),

    # 7) Operadores de 3 caracteres (antes que los de 2).
    ('OP_SHL_ASIG', r'<<='),
    ('OP_SHR_ASIG', r'>>='),

    # 8) Operadores de 2 caracteres (antes que los de 1).
    ('OP_IGUAL',      r'=='),
    ('OP_DIST',       r'!='),
    ('OP_MENOR_IG',   r'<='),
    ('OP_MAYOR_IG',   r'>='),
    ('OP_AND',        r'&&'),
    ('OP_OR',         r'\|\|'),
    ('OP_SHL',        r'<<'),
    ('OP_SHR',        r'>>'),
    ('OP_SUMA_ASIG',  r'\+='),
    ('OP_RESTA_ASIG', r'-='),
    ('OP_MULT_ASIG',  r'\*='),
    ('OP_DIV_ASIG',   r'/='),
    ('OP_MOD_ASIG',   r'%='),
    ('OP_AND_ASIG',   r'&='),
    ('OP_OR_ASIG',    r'\|='),
    ('OP_XOR_ASIG',   r'\^='),
    ('OP_AMBITO',     r'::'),
    ('OP_FLECHA',     r'->'),
    ('OP_INC',        r'\+\+'),
    ('OP_DEC',        r'--'),

    # 9) Operadores de 1 carácter y delimitadores.
    #    OP_PUNTO va después de LIT_FLOAT (ya lo está arriba) para que ".5"
    #    sea número y "a.b" sea punto.
    ('OP_SUMA',     r'\+'),
    ('OP_RESTA',    r'-'),
    ('OP_MULT',     r'\*'),
    ('OP_DIV',      r'/'),
    ('OP_MOD',      r'%'),
    ('OP_MENOR',    r'<'),
    ('OP_MAYOR',    r'>'),
    ('OP_ASIG',     r'='),
    ('OP_AND_BIT',  r'&'),
    ('OP_OR_BIT',   r'\|'),
    ('OP_XOR',      r'\^'),
    ('OP_NOT_BIT',  r'~'),
    ('OP_NOT',      r'!'),
    ('OP_TERNARIO', r'\?'),
    ('DOS_PUNTOS',  r':'),
    ('OP_PUNTO',    r'\.'),
    ('PAR_IZQ',     r'\('),
    ('PAR_DER',     r'\)'),
    ('COR_IZQ',     r'\['),
    ('COR_DER',     r'\]'),
    ('LLAVE_IZQ',   r'\{'),
    ('LLAVE_DER',   r'\}'),
    ('PUNTO_COMA',  r';'),
    ('COMA',        r','),

    # 10) Espacios y saltos de línea.
    ('ESPACIO',     r'[ \t\r]+'),
    ('NUEVA_LINEA', r'\n'),

    # 11) Carácter inválido. Siempre al final: captura cualquier cosa
    #     que no haya coincidido antes.
    ('CHAR_INVALIDO', r'.'),
]


# Expresión regular maestra: una sola con grupos con nombre. re.finditer
# nos dará el tipo del match en m.lastgroup.
_MAESTRA = re.compile(
    '|'.join(f'(?P<{nombre}>{patron})' for nombre, patron in PATRONES)
)


# ---------------------------------------------------------------------------
# Utilidades de decodificación para LIT_CHAR y LIT_STRING.
# ---------------------------------------------------------------------------

# Escapes aceptados según la especificación.
_ESCAPES = {
    'n': '\n', 't': '\t', 'r': '\r', '0': '\0',
    '\\': '\\', "'": "'", '"': '"',
}


def _decodificar(contenido: str) -> tuple[str, list[str]]:
    """Decodifica los escapes de un literal.

    Devuelve (texto_decodificado, lista_de_escapes_invalidos). Un escape
    inválido se registra como la secuencia literal "\\x" para el mensaje.
    """
    resultado: list[str] = []
    invalidos: list[str] = []
    i = 0
    while i < len(contenido):
        c = contenido[i]
        if c == '\\' and i + 1 < len(contenido):
            sig = contenido[i + 1]
            if sig in _ESCAPES:
                resultado.append(_ESCAPES[sig])
            else:
                # Guardamos la secuencia tal cual (dos caracteres).
                invalidos.append('\\' + sig)
                resultado.append(sig)
            i += 2
        else:
            resultado.append(c)
            i += 1
    return ''.join(resultado), invalidos


def _contar_chars_logicos(contenido: str) -> int:
    """Cuenta "caracteres lógicos": cada escape \\x cuenta como uno solo."""
    n = 0
    i = 0
    while i < len(contenido):
        if contenido[i] == '\\' and i + 1 < len(contenido):
            i += 2
        else:
            i += 1
        n += 1
    return n


# ---------------------------------------------------------------------------
# Extractores para DIR_INCLUDE y DIR_DEFINE.
# ---------------------------------------------------------------------------

_RE_INCLUDE = re.compile(r'<([^>\n]+)>|"([^"\n]+)"')
_RE_DEFINE = re.compile(
    r'\#[ \t]*define[ \t]+([A-Za-z_][A-Za-z_0-9]*)([ \t]+(.*))?\Z'
)


def _extraer_include(lexema: str) -> str:
    m = _RE_INCLUDE.search(lexema)
    # Uno de los dos grupos siempre está presente por construcción del patrón.
    return m.group(1) if m.group(1) is not None else m.group(2)


def _extraer_define(lexema: str) -> tuple[str, str]:
    m = _RE_DEFINE.match(lexema)
    nombre = m.group(1)
    reemplazo = (m.group(3) or '').strip()
    return nombre, reemplazo


# ---------------------------------------------------------------------------
# Conversión de valores numéricos.
# ---------------------------------------------------------------------------

# Expresión para quitar el sufijo entero al final de un lexema numérico.
_RE_SUF_ENT = re.compile(_SUF_ENT + r'$')


def _convertir_hex(lexema: str) -> int:
    # Quitar prefijo 0x/0X y sufijo entero.
    s = _RE_SUF_ENT.sub('', lexema[2:])
    return int(s, 16)


def _convertir_int(lexema: str) -> int:
    s = _RE_SUF_ENT.sub('', lexema)
    return int(s)


def _convertir_float(lexema: str) -> float:
    # Quitar el sufijo de punto flotante (f, F, l, L) si existe.
    if lexema and lexema[-1] in 'fFlL':
        lexema = lexema[:-1]
    # float('2.') funciona en Python como 2.0, no hay que tratarlo aparte.
    return float(lexema)


# ---------------------------------------------------------------------------
# Procesamiento de literales de texto (validación en código, errores 4 a 8).
# ---------------------------------------------------------------------------

def _procesar_cadena(lexema: str, linea: int, col: int,
                     tokens: list[Token], errores: list[ErrorLexico]) -> None:
    # El patrón acepta cadenas sin cerrar: aquí decidimos si lo está.
    # Debe tener al menos dos caracteres (las dos comillas) y terminar en ".
    if len(lexema) < 2 or not lexema.endswith('"'):
        errores.append(ErrorLexico('cadena sin cerrar', linea, col))
        return
    contenido = lexema[1:-1]
    valor, invalidos = _decodificar(contenido)
    if invalidos:
        # Reportamos el primer escape inválido.
        errores.append(ErrorLexico(
            f"secuencia de escape inválida '{invalidos[0]}'", linea, col,
        ))
        return
    tokens.append(Token(LIT_STRING, lexema, linea, col, valor))


def _procesar_caracter(lexema: str, linea: int, col: int,
                       tokens: list[Token], errores: list[ErrorLexico]) -> None:
    if len(lexema) < 2 or not lexema.endswith("'"):
        errores.append(ErrorLexico('literal de carácter sin cerrar', linea, col))
        return
    contenido = lexema[1:-1]
    n = _contar_chars_logicos(contenido)
    if n == 0:
        errores.append(ErrorLexico('literal de carácter vacío', linea, col))
        return
    if n > 1:
        errores.append(ErrorLexico(
            'literal de carácter con varios caracteres', linea, col,
        ))
        return
    valor, invalidos = _decodificar(contenido)
    if invalidos:
        errores.append(ErrorLexico(
            f"secuencia de escape inválida '{invalidos[0]}'", linea, col,
        ))
        return
    tokens.append(Token(LIT_CHAR, lexema, linea, col, valor))


# ---------------------------------------------------------------------------
# Motor principal.
# ---------------------------------------------------------------------------

def tokenizar(codigo: str) -> tuple[list[Token], list[ErrorLexico]]:
    """Analiza léxicamente `codigo` y devuelve (tokens, errores).

    - Ignora espacios y comentarios.
    - Columnas comienzan en 1. Un comentario de bloque de varias líneas
      actualiza bien la línea y la columna porque contamos los '\\n' del lexema.
    - Agrega siempre un token EOF al final.
    - Recuperación en modo pánico: ante un error, reporta, salta el lexema y sigue.
    """
    tokens: list[Token] = []
    errores: list[ErrorLexico] = []
    linea = 1
    col = 1

    for m in _MAESTRA.finditer(codigo):
        tipo = m.lastgroup
        lexema = m.group()
        t_linea, t_col = linea, col

        if tipo in ('ESPACIO', 'NUEVA_LINEA',
                    'COMENTARIO_LINEA', 'COMENTARIO_BLOQUE'):
            pass  # Se ignoran, pero sí actualizan línea/columna más abajo.

        elif tipo == 'COMENTARIO_BLOQUE_NO_CERRADO':
            errores.append(ErrorLexico(
                f'comentario sin cerrar (abierto en línea {t_linea})',
                t_linea, t_col,
            ))

        elif tipo == 'DIR_INCLUDE':
            tokens.append(Token(DIR_INCLUDE, lexema, t_linea, t_col,
                                _extraer_include(lexema)))

        elif tipo == 'DIR_DEFINE':
            nombre, reemplazo = _extraer_define(lexema)
            tokens.append(Token(DIR_DEFINE, lexema, t_linea, t_col,
                                (nombre, reemplazo)))

        elif tipo == 'DIR_INVALIDA':
            # Tomamos la primera "palabra" de la directiva para el mensaje.
            partes = lexema.split(None, 1)
            primera = partes[0] if partes else lexema
            errores.append(ErrorLexico(
                f"directiva no soportada '{primera}'", t_linea, t_col,
            ))

        elif tipo == 'LIT_STRING':
            _procesar_cadena(lexema, t_linea, t_col, tokens, errores)

        elif tipo == 'LIT_CHAR':
            _procesar_caracter(lexema, t_linea, t_col, tokens, errores)

        elif tipo == 'LIT_HEX':
            tokens.append(Token(LIT_HEX, lexema, t_linea, t_col,
                                _convertir_hex(lexema)))

        elif tipo == 'LIT_FLOAT':
            tokens.append(Token(LIT_FLOAT, lexema, t_linea, t_col,
                                _convertir_float(lexema)))

        elif tipo == 'LIT_OCTAL':
            errores.append(ErrorLexico(
                f"literales octales no soportados '{lexema}'",
                t_linea, t_col,
            ))

        elif tipo == 'LIT_INT':
            tokens.append(Token(LIT_INT, lexema, t_linea, t_col,
                                _convertir_int(lexema)))

        elif tipo == 'NUM_MALFORMADO':
            errores.append(ErrorLexico(
                f"número mal formado '{lexema}'", t_linea, t_col,
            ))

        elif tipo == 'ID':
            if lexema in RESERVADAS:
                tipo_tok, valor = RESERVADAS[lexema]
                tokens.append(Token(tipo_tok, lexema, t_linea, t_col, valor))
            else:
                tokens.append(Token(ID, lexema, t_linea, t_col, lexema))

        elif tipo == 'CHAR_INVALIDO':
            errores.append(ErrorLexico(
                f"carácter inválido '{lexema}'", t_linea, t_col,
            ))

        else:
            # Operador o delimitador: el nombre del grupo es el tipo de token.
            tokens.append(Token(tipo, lexema, t_linea, t_col))

        # Avanzar línea y columna sobre el lexema consumido.
        nls = lexema.count('\n')
        if nls:
            linea += nls
            # Columna = cantidad de caracteres después del último '\n', +1.
            col = len(lexema) - lexema.rfind('\n')
        else:
            col += len(lexema)

    tokens.append(Token(EOF, '', linea, col))
    return tokens, errores


# ---------------------------------------------------------------------------
# Uso por consola: python lexer.py <archivo>
# ---------------------------------------------------------------------------

def _imprimir_tabla(tokens: list[Token]) -> None:
    encabezados = ('Tipo', 'Lexema', 'Línea', 'Col')
    filas = [(t.tipo, t.lexema, str(t.linea), str(t.columna)) for t in tokens]
    anchos = [max(len(f[i]) for f in [encabezados] + filas) for i in range(4)]

    def linea_fmt(fila: tuple[str, str, str, str]) -> str:
        return ' | '.join(fila[i].ljust(anchos[i]) for i in range(4))

    print(linea_fmt(encabezados))
    print('-+-'.join('-' * a for a in anchos))
    for f in filas:
        print(linea_fmt(f))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Uso: python lexer.py <archivo>', file=sys.stderr)
        return 1
    with open(argv[1], encoding='utf-8') as f:
        codigo = f.read()
    tokens, errores = tokenizar(codigo)
    _imprimir_tabla(tokens)
    print()
    if errores:
        for e in errores:
            print(e)
    else:
        print('Sin errores léxicos')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
