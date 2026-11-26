"""Analizador léxico para el subconjunto controlado del español de la Fase 2.

Reutiliza el motor de la Fase 1 (fase1/lexer.py): las dataclasses Token y
ErrorLexico, el patrón de PATRONES + expresión maestra con grupos con nombre,
y el recorrido con re.finditer que mantiene línea y columna.

Diferencias respecto a la Fase 1: la tabla LEXICO reemplaza a RESERVADAS, y
los patrones se reducen a PALABRA, COMA, PUNTO, ESPACIO y CHAR_INVALIDO.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Permitimos importar fase1/ ejecutando este archivo como script directo.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase1.lexer import Token, ErrorLexico  # noqa: E402


# ---------------------------------------------------------------------------
# Constantes de categoría (terminales de la gramática, 17 + EOF).
# ---------------------------------------------------------------------------

DET = 'DET'
SUST = 'SUST'
NPROP = 'NPROP'
PRON = 'PRON'
ADJ = 'ADJ'
INTENS = 'INTENS'
VERBO = 'VERBO'
COP = 'COP'
NEG = 'NEG'
ADV = 'ADV'
PREP = 'PREP'
PREP_DE = 'PREP_DE'
CONTR_A = 'CONTR_A'
CONTR_DE = 'CONTR_DE'
CONJ = 'CONJ'
COMA = 'COMA'
PUNTO = 'PUNTO'
EOF = 'EOF'


# ---------------------------------------------------------------------------
# Construcción del léxico: 400 formas en 17 categorías.
# Cada forma vive en una sola categoría; eso es lo que mantiene regular el
# lexer y LL(1) el parser.
# ---------------------------------------------------------------------------

class CargaLexicoError(Exception):
    """Se dispara si una forma aparece en dos categorías distintas."""


def _agregar(lexico, forma, categoria, rasgos):
    """Agrega una forma al léxico y detecta colisiones de categoría."""
    clave = forma.lower()
    if clave in lexico:
        cat_previa, _ = lexico[clave]
        if cat_previa != categoria:
            raise CargaLexicoError(
                f"La forma '{forma}' aparece en {cat_previa} y {categoria}."
            )
        # Misma categoría repetida: sobrescribe (no debería pasar, pero
        # evita duplicados silenciosos).
    lexico[clave] = (categoria, rasgos)


def _cargar_det(lexico):
    # R: 8 formas; género y número.
    formas = [
        ('el',    {'genero': 'm', 'numero': 'sg'}),
        ('la',    {'genero': 'f', 'numero': 'sg'}),
        ('los',   {'genero': 'm', 'numero': 'pl'}),
        ('las',   {'genero': 'f', 'numero': 'pl'}),
        ('un',    {'genero': 'm', 'numero': 'sg'}),
        ('una',   {'genero': 'f', 'numero': 'sg'}),
        ('unos',  {'genero': 'm', 'numero': 'pl'}),
        ('unas',  {'genero': 'f', 'numero': 'pl'}),
    ]
    for forma, rasgos in formas:
        _agregar(lexico, forma, DET, rasgos)


def _cargar_sust(lexico):
    # 20 lemas × 2 formas (sg y pl) = 40.
    # Lemas masculinos con sus plurales explícitos del documento.
    masculinos = [
        ('perro', 'perros'),
        ('gato', 'gatos'),
        ('niño', 'niños'),
        ('libro', 'libros'),
        ('parque', 'parques'),
        ('árbol', 'árboles'),
        ('coche', 'coches'),
        ('pan', 'panes'),
        ('profesor', 'profesores'),
        ('jardín', 'jardines'),
    ]
    femeninos = [
        ('casa', 'casas'),
        ('niña', 'niñas'),
        ('manzana', 'manzanas'),
        ('mesa', 'mesas'),
        ('ciudad', 'ciudades'),
        ('escuela', 'escuelas'),
        ('flor', 'flores'),
        ('carta', 'cartas'),
        ('profesora', 'profesoras'),
        ('ventana', 'ventanas'),
    ]
    for sg, pl in masculinos:
        _agregar(lexico, sg, SUST,
                 {'lema': sg, 'genero': 'm', 'numero': 'sg'})
        _agregar(lexico, pl, SUST,
                 {'lema': sg, 'genero': 'm', 'numero': 'pl'})
    for sg, pl in femeninos:
        _agregar(lexico, sg, SUST,
                 {'lema': sg, 'genero': 'f', 'numero': 'sg'})
        _agregar(lexico, pl, SUST,
                 {'lema': sg, 'genero': 'f', 'numero': 'pl'})


def _cargar_nprop(lexico):
    # 6 nombres propios; número = sg, persona = 3.
    nombres = [
        ('Ana', 'f'),
        ('María', 'f'),
        ('Sofía', 'f'),
        ('Luis', 'm'),
        ('Pedro', 'm'),
        ('Carlos', 'm'),
    ]
    for nombre, genero in nombres:
        _agregar(lexico, nombre, NPROP,
                 {'lema': nombre, 'genero': genero,
                  'numero': 'sg', 'persona': 3})


def _cargar_pron(lexico):
    # 8 pronombres personales. Género "c" = común.
    formas = [
        ('yo',        {'persona': 1, 'numero': 'sg', 'genero': 'c'}),
        ('tú',        {'persona': 2, 'numero': 'sg', 'genero': 'c'}),
        ('él',        {'persona': 3, 'numero': 'sg', 'genero': 'm'}),
        ('ella',      {'persona': 3, 'numero': 'sg', 'genero': 'f'}),
        ('nosotros',  {'persona': 1, 'numero': 'pl', 'genero': 'm'}),
        ('nosotras',  {'persona': 1, 'numero': 'pl', 'genero': 'f'}),
        ('ellos',     {'persona': 3, 'numero': 'pl', 'genero': 'm'}),
        ('ellas',     {'persona': 3, 'numero': 'pl', 'genero': 'f'}),
    ]
    for forma, rasgos in formas:
        _agregar(lexico, forma, PRON, rasgos)


def _cargar_adj(lexico):
    # 10 lemas variables × 4 formas (o, a, os, as) = 40.
    # Los lemas tienen una vocal temática: reemplazamos la 'o' final.
    variables = [
        'alto', 'bajo', 'rojo', 'negro', 'blanco',
        'pequeño', 'nuevo', 'viejo', 'bonito', 'rápido',
    ]
    for lema in variables:
        raiz = lema[:-1]  # Quitamos la 'o' final.
        formas = [
            (raiz + 'o',  'm', 'sg'),
            (raiz + 'a',  'f', 'sg'),
            (raiz + 'os', 'm', 'pl'),
            (raiz + 'as', 'f', 'pl'),
        ]
        for forma, genero, numero in formas:
            _agregar(lexico, forma, ADJ,
                     {'lema': lema, 'genero': genero, 'numero': numero})

    # 6 lemas de género común (acepta m y f) con sg y pl explícitos.
    comunes = [
        ('grande', 'grandes'),
        ('feliz', 'felices'),
        ('inteligente', 'inteligentes'),
        ('verde', 'verdes'),
        ('azul', 'azules'),
        ('joven', 'jóvenes'),
    ]
    for sg, pl in comunes:
        _agregar(lexico, sg, ADJ,
                 {'lema': sg, 'genero': 'c', 'numero': 'sg'})
        _agregar(lexico, pl, ADJ,
                 {'lema': sg, 'genero': 'c', 'numero': 'pl'})


def _cargar_intens(lexico):
    for forma in ('muy', 'bastante'):
        _agregar(lexico, forma, INTENS, {'lema': forma})


def _cargar_adv(lexico):
    # 11 adverbios; referencia temporal para C8.
    formas = [
        ('ayer',        'pasado'),
        ('pronto',      'futuro'),
        ('hoy',         'libre'),
        ('siempre',     'libre'),
        ('nunca',       'libre'),
        ('rápidamente', 'libre'),
        ('lentamente',  'libre'),
        ('bien',        'libre'),
        ('mal',         'libre'),
        ('aquí',        'libre'),
        ('allí',        'libre'),
    ]
    for forma, referencia in formas:
        _agregar(lexico, forma, ADV,
                 {'lema': forma, 'referencia': referencia})


def _cargar_neg(lexico):
    _agregar(lexico, 'no', NEG, {'lema': 'no'})


def _cargar_prep(lexico):
    # 9 preposiciones.
    for forma in ('a', 'en', 'con', 'por', 'para',
                  'sobre', 'desde', 'hacia', 'sin'):
        _agregar(lexico, forma, PREP, {'lema': forma})


def _cargar_contracciones_y_de(lexico):
    # PREP_DE, CONTR_A y CONTR_DE: una forma cada una.
    _agregar(lexico, 'de',  PREP_DE,  {'lema': 'de'})
    _agregar(lexico, 'al',  CONTR_A,  {'lema': 'a',  'genero': 'm', 'numero': 'sg'})
    _agregar(lexico, 'del', CONTR_DE, {'lema': 'de', 'genero': 'm', 'numero': 'sg'})


def _cargar_conj(lexico):
    for forma in ('y', 'o'):
        _agregar(lexico, forma, CONJ, {'lema': forma})


def _cargar_cop(lexico):
    # 30 formas irregulares de ser y estar (presente, pretérito, futuro).
    # Clave del valor: (lema, persona, numero, tiempo).
    ser = [
        ('soy',   1, 'sg', 'pres'),
        ('eres',  2, 'sg', 'pres'),
        ('es',    3, 'sg', 'pres'),
        ('somos', 1, 'pl', 'pres'),
        ('son',   3, 'pl', 'pres'),
        ('fui',     1, 'sg', 'pret'),
        ('fuiste',  2, 'sg', 'pret'),
        ('fue',     3, 'sg', 'pret'),
        ('fuimos',  1, 'pl', 'pret'),
        ('fueron',  3, 'pl', 'pret'),
        ('seré',    1, 'sg', 'fut'),
        ('serás',   2, 'sg', 'fut'),
        ('será',    3, 'sg', 'fut'),
        ('seremos', 1, 'pl', 'fut'),
        ('serán',   3, 'pl', 'fut'),
    ]
    estar = [
        ('estoy',   1, 'sg', 'pres'),
        ('estás',   2, 'sg', 'pres'),
        ('está',    3, 'sg', 'pres'),
        ('estamos', 1, 'pl', 'pres'),
        ('están',   3, 'pl', 'pres'),
        ('estuve',     1, 'sg', 'pret'),
        ('estuviste',  2, 'sg', 'pret'),
        ('estuvo',     3, 'sg', 'pret'),
        ('estuvimos',  1, 'pl', 'pret'),
        ('estuvieron', 3, 'pl', 'pret'),
        ('estaré',    1, 'sg', 'fut'),
        ('estarás',   2, 'sg', 'fut'),
        ('estará',    3, 'sg', 'fut'),
        ('estaremos', 1, 'pl', 'fut'),
        ('estarán',   3, 'pl', 'fut'),
    ]
    for forma, persona, numero, tiempo in ser:
        _agregar(lexico, forma, COP,
                 {'lema': 'ser', 'persona': persona,
                  'numero': numero, 'tiempo': tiempo})
    for forma, persona, numero, tiempo in estar:
        _agregar(lexico, forma, COP,
                 {'lema': 'estar', 'persona': persona,
                  'numero': numero, 'tiempo': tiempo})


# Terminaciones regulares por conjugación. Cada entrada mapea (persona, tiempo)
# a la terminación que se adosa a la raíz, menos los futuros, que se adosan
# al infinitivo.
_PERSONAS = [(1, 'sg'), (2, 'sg'), (3, 'sg'), (1, 'pl'), (3, 'pl')]

_TERMS_RAIZ = {
    'ar': {
        'pres': ['o',  'as', 'a',  'amos', 'an'],
        'pret': ['é',  'aste', 'ó', 'amos', 'aron'],
    },
    'er': {
        'pres': ['o',  'es', 'e',  'emos', 'en'],
        'pret': ['í',  'iste', 'ió', 'imos', 'ieron'],
    },
    'ir': {
        'pres': ['o',  'es', 'e',  'imos', 'en'],
        'pret': ['í',  'iste', 'ió', 'imos', 'ieron'],
    },
}

_TERMS_FUT = ['é', 'ás', 'á', 'emos', 'án']   # Se añaden al infinitivo entero.


def _generar_formas_verbo(lema, trans):
    """Devuelve una lista [(forma, rasgos)] para el verbo `lema`.

    Si una forma se repite entre presente y pretérito (caso -ar/-ir
    nosotros), se devuelve **una sola entrada** con `tiempo = [...]`.
    """
    terminacion = lema[-2:]          # 'ar', 'er' o 'ir'
    raiz = lema[:-2]
    tabla_raiz = _TERMS_RAIZ[terminacion]

    # Acumulamos por forma para fusionar tiempos repetidos.
    por_forma = {}                   # forma -> dict rasgos acumulado

    def _acumular(forma, persona, numero, tiempo):
        if forma in por_forma:
            prev = por_forma[forma]
            # Fusionamos el tiempo: cadena -> lista.
            t_prev = prev['tiempo']
            if isinstance(t_prev, str):
                if t_prev != tiempo:
                    prev['tiempo'] = [t_prev, tiempo]
            else:
                if tiempo not in t_prev:
                    t_prev.append(tiempo)
        else:
            por_forma[forma] = {
                'lema': lema, 'persona': persona,
                'numero': numero, 'tiempo': tiempo, 'trans': trans,
            }

    # Presente y pretérito.
    for tiempo in ('pres', 'pret'):
        for (persona, numero), suf in zip(_PERSONAS, tabla_raiz[tiempo]):
            _acumular(raiz + suf, persona, numero, tiempo)

    # Futuro: se añade al infinitivo completo, igual para -ar, -er, -ir.
    for (persona, numero), suf in zip(_PERSONAS, _TERMS_FUT):
        _acumular(lema + suf, persona, numero, 'fut')

    return list(por_forma.items())


def _cargar_verbos(lexico):
    # 16 verbos regulares con su transitividad.
    transitivos = ['comprar', 'mirar', 'lavar', 'abrir']
    ambos = ['comer', 'beber', 'aprender', 'escribir', 'cocinar', 'pintar']
    intransitivos = ['correr', 'caminar', 'vivir', 'saltar', 'trabajar', 'nadar']

    def _cargar(lemas, trans):
        for lema in lemas:
            for forma, rasgos in _generar_formas_verbo(lema, trans):
                _agregar(lexico, forma, VERBO, rasgos)

    _cargar(transitivos, 'trans')
    _cargar(ambos, 'ambos')
    _cargar(intransitivos, 'intr')


def _construir_lexico():
    """Construye el diccionario LEXICO: forma -> (categoría, rasgos)."""
    lexico = {}
    _cargar_det(lexico)
    _cargar_sust(lexico)
    _cargar_nprop(lexico)
    _cargar_pron(lexico)
    _cargar_adj(lexico)
    _cargar_intens(lexico)
    _cargar_adv(lexico)
    _cargar_neg(lexico)
    _cargar_prep(lexico)
    _cargar_contracciones_y_de(lexico)
    _cargar_conj(lexico)
    _cargar_cop(lexico)
    _cargar_verbos(lexico)
    return lexico


LEXICO = _construir_lexico()


# ---------------------------------------------------------------------------
# Patrones léxicos (la especificación de la sección "Léxico" del documento).
# ---------------------------------------------------------------------------

PATRONES = [
    # Una palabra: letras del alfabeto español, incluidas las tildes y la ñ.
    ('PALABRA',       r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+'),
    ('COMA',          r','),
    ('PUNTO',         r'\.'),
    ('ESPACIO',       r'[ \t\r\n]+'),
    # Siempre al final: cualquier carácter que no coincidió arriba.
    ('CHAR_INVALIDO', r'.'),
]

# Expresión regular maestra con grupos con nombre; re.finditer dirá cuál
# alternativa coincidió en m.lastgroup.
_MAESTRA = re.compile(
    '|'.join(f'(?P<{nombre}>{patron})' for nombre, patron in PATRONES)
)


# ---------------------------------------------------------------------------
# Motor principal.
# ---------------------------------------------------------------------------

def tokenizar(texto: str) -> tuple[list[Token], list[ErrorLexico]]:
    """Analiza léxicamente `texto` y devuelve (tokens, errores).

    - Ignora espacios (pero mantiene línea y columna).
    - Las palabras se buscan en minúsculas contra LEXICO; el lexema original
      se conserva en el token (con mayúsculas y tildes).
    - Palabras fuera del léxico: error 'palabra fuera del vocabulario ...'.
    - Caracteres no previstos: 'carácter inválido ...'.
    - Siempre añade Token(EOF, '', linea, col) al final.
    """
    tokens: list[Token] = []
    errores: list[ErrorLexico] = []
    linea = 1
    col = 1

    for m in _MAESTRA.finditer(texto):
        tipo = m.lastgroup
        lexema = m.group()
        t_linea, t_col = linea, col

        if tipo == 'ESPACIO':
            pass  # Se ignora pero más abajo actualiza línea y columna.

        elif tipo == 'PALABRA':
            clave = lexema.lower()
            if clave in LEXICO:
                categoria, rasgos = LEXICO[clave]
                tokens.append(Token(categoria, lexema, t_linea, t_col, rasgos))
            else:
                errores.append(ErrorLexico(
                    f"palabra fuera del vocabulario '{lexema}'",
                    t_linea, t_col,
                ))

        elif tipo == 'COMA':
            tokens.append(Token(COMA, lexema, t_linea, t_col, {}))

        elif tipo == 'PUNTO':
            tokens.append(Token(PUNTO, lexema, t_linea, t_col, {}))

        elif tipo == 'CHAR_INVALIDO':
            errores.append(ErrorLexico(
                f"carácter inválido '{lexema}'", t_linea, t_col,
            ))

        # Avanza línea y columna sobre el lexema consumido.
        nls = lexema.count('\n')
        if nls:
            linea += nls
            col = len(lexema) - lexema.rfind('\n')
        else:
            col += len(lexema)

    tokens.append(Token(EOF, '', linea, col, {}))
    return tokens, errores


# ---------------------------------------------------------------------------
# Punto de entrada por consola (depuración).
# ---------------------------------------------------------------------------

def _main(argv):
    if len(argv) != 2:
        print("Uso: python lexer_es.py '<oración>'", file=sys.stderr)
        return 1
    tokens, errores = tokenizar(argv[1])
    for t in tokens:
        print(f"{t.tipo:<10} {t.lexema!r:<20} línea {t.linea}, col {t.columna}")
    for e in errores:
        print(e)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
