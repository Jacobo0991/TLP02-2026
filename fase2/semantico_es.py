"""Analizador semántico del español — Fase 2.

Recorre el árbol sintáctico que produce ``parser_es.py`` y aplica las 8
reglas de concordancia y restricciones C1-C8 definidas en la sección
"Concordancia y restricciones del semántico" de
``fase2/docs/gramatica_espanol.md``.

Nota sobre la tabla de símbolos de la Fase 1
--------------------------------------------
La clase ``TablaSimbolos`` de ``fase1/tabla_simbolos.py`` modela
declaraciones de C++: cada ``Simbolo`` arrastra un ``Tipo`` con
``nombre, punteros, argumentos, arreglo, constante, referencia`` y una
``clase`` (``variable``, ``parametro``, ``funcion``, ``tipo``, ``campo`` ...)
con ``campos``, ``parametros``, ``elemento_tipo``, ``definida``, etc.
Ninguno de esos campos modela los rasgos del español (``genero``,
``numero``, ``persona``, ``tiempo``, ``trans``, ``referencia`` temporal) y
las reglas C1-C8 no son consultas de "declaración antes de uso" en
ámbitos anidados, sino preguntas puntuales sobre los rasgos del sujeto,
el verbo y los adyacentes dentro de UNA oración; esos rasgos ya viajan
en ``token.valor``, donde los puso el lexer. Reutilizar ``TablaSimbolos``
exigiría o bien forzar los rasgos dentro de ``Simbolo.parametros`` /
``Simbolo.campos``, o bien inventar un ``Tipo`` por cada combinación de
rasgos; ninguna de las dos cosas es más clara que consultar directamente
``token.valor``. Por eso el análisis trabaja sobre el árbol y no sobre
una tabla de símbolos.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Permite ejecutar como módulo suelto.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# Nota: no hacemos `from fase2.parser_es import Nodo` ni
# `from fase1.lexer import Token`. Cuando `parser_es.py` se lanza como
# script (``python fase2/parser_es.py ...``), Python lo carga con el
# módulo ``__main__`` y al mismo tiempo este archivo importa
# ``fase2.parser_es``: el `Nodo` del script y el `Nodo` importado serían
# clases distintas y ``isinstance`` daría siempre ``False``. Trabajamos
# con duck typing sobre los dos atributos que distinguen un nodo de una
# hoja: los nodos tienen ``etiqueta`` y ``hijos``; las hojas (``Token``)
# tienen ``tipo``, ``lexema``, ``linea``, ``columna`` y ``valor``.


# ---------------------------------------------------------------------------
# Modelo de error.
# ---------------------------------------------------------------------------

@dataclass
class ErrorSemantico:
    """Error producido por el semántico. ``regla`` es ``C1``..``C8``."""

    mensaje: str
    regla: str
    linea: int
    columna: int

    def __str__(self) -> str:
        # Formato fijo del documento: Error semántico [col C]: <mensaje>
        return f"Error semántico [col {self.columna}]: {self.mensaje}"


# ---------------------------------------------------------------------------
# Utilidades de recorrido y de rasgos.
# ---------------------------------------------------------------------------

def _es_token(x) -> bool:
    """True si `x` es una hoja (Token-like)."""
    return hasattr(x, 'tipo') and hasattr(x, 'lexema') and not hasattr(x, 'hijos')


def _es_nodo(x, etiqueta: str | None = None) -> bool:
    """True si `x` es un nodo (Nodo-like) con la etiqueta pedida."""
    if not (hasattr(x, 'etiqueta') and hasattr(x, 'hijos')):
        return False
    return etiqueta is None or x.etiqueta == etiqueta


def _hojas(nodo):
    """Genera las hojas (Tokens) en orden de aparición."""
    if _es_token(nodo):
        yield nodo
        return
    for h in nodo.hijos:
        yield from _hojas(h)


def _recorrer(nodo, etiqueta: str):
    """Genera todos los descendientes (incluido el propio nodo) con esa
    etiqueta. Útil para "aplicar a todos los SN / SP / SADJ".
    """
    if _es_nodo(nodo):
        if nodo.etiqueta == etiqueta:
            yield nodo
        for h in nodo.hijos:
            yield from _recorrer(h, etiqueta)


# Traducciones compactas para los mensajes de error.
_LEG_GEN = {'m': 'm.', 'f': 'f.', 'c': 'c.'}
_LEG_NUM = {'sg': 'sg.', 'pl': 'pl.'}
_LEG_PERS = {1: '1.ª', 2: '2.ª', 3: '3.ª'}
_LEG_TIEMPO = {'pres': 'presente', 'pret': 'pretérito', 'fut': 'futuro'}


def _concuerda_gen(a: str | None, b: str | None) -> bool:
    """Compara dos rasgos de género. El género 'c' (común) acepta m y f."""
    if a is None or b is None:
        return True
    if a == 'c' or b == 'c':
        return True
    return a == b


def _concuerda_num(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return True
    return a == b


def _fmt_gnum(rasgos: dict) -> str:
    """Formatea 'm. sg.' / 'f. pl.' a partir del dict de rasgos. Si falta
    el género, devuelve solo el número (sujetos tácitos y similares).
    """
    g = _LEG_GEN.get((rasgos or {}).get('genero'))
    n = _LEG_NUM.get((rasgos or {}).get('numero'), '?')
    if g is None:
        return n
    return f"{g} {n}"


def _fmt_pernum(rasgos: dict) -> str:
    p = _LEG_PERS.get((rasgos or {}).get('persona'), '?')
    n = _LEG_NUM.get((rasgos or {}).get('numero'), '?')
    return f"{p} {n}"


def _fmt_tiempos(tiempos) -> str:
    return '/'.join(_LEG_TIEMPO.get(t, t) for t in tiempos)


# ---------------------------------------------------------------------------
# Localización de partes de la oración.
# ---------------------------------------------------------------------------

def _primer_hijo(nodo, etiqueta: str):
    for h in nodo.hijos:
        if _es_nodo(h, etiqueta):
            return h
    return None


def _primer_hijo_token(nodo, tipos):
    for h in nodo.hijos:
        if _es_token(h) and h.tipo in tipos:
            return h
    return None


def _suj(arbol):
    return _primer_hijo(arbol, 'SUJ')


def _sv(arbol):
    return _primer_hijo(arbol, 'SV')


def _sn_del_suj(suj):
    return _primer_hijo(suj, 'SN')


def _verbo_del_sv(sv):
    """Devuelve el Token VERBO o COP hijo directo del SV, o None."""
    return _primer_hijo_token(sv, ('VERBO', 'COP'))


def _od_del_sv(sv):
    return _primer_hijo(sv, 'OD')


def _atrib_del_sv(sv):
    return _primer_hijo(sv, 'ATRIB')


# ---------------------------------------------------------------------------
# Rasgos de los SN (simples y coordinados) y del sujeto.
# ---------------------------------------------------------------------------

def _es_sn_coordinado(sn_nodo) -> bool:
    """Un SN coordinado tiene al menos un hijo Nodo con etiqueta SN."""
    return any(_es_nodo(h, 'SN') for h in sn_nodo.hijos)


def _miembros_sn(sn_nodo):
    """Si el SN es coordinado, devuelve la lista de sus SN hijos; si no,
    devuelve ``[sn_nodo]``. Así C3/C4/C7 recorren todos los miembros con
    el mismo bucle sin distinguir el caso simple del coordinado.
    """
    if _es_sn_coordinado(sn_nodo):
        return [h for h in sn_nodo.hijos if _es_nodo(h, 'SN')]
    return [sn_nodo]


def _nucleo_sn_simple(sn_nodo):
    """Devuelve el Token-cabeza (SUST, NPROP o PRON) de un SN simple."""
    return _primer_hijo_token(sn_nodo, ('SUST', 'NPROP', 'PRON'))


def _det_sn_simple(sn_nodo):
    return _primer_hijo_token(sn_nodo, ('DET',))


def _rasgos_cabeza_simple(sn_nodo) -> dict | None:
    """Rasgos (persona, numero, genero) de la cabeza de un SN simple. Los
    SUST y NPROP son siempre 3.ª persona (los pronombres traen la suya).
    """
    cab = _nucleo_sn_simple(sn_nodo)
    if cab is None:
        return None
    r = cab.valor or {}
    return {
        'persona': r.get('persona', 3),
        'numero': r.get('numero'),
        'genero': r.get('genero'),
    }


def _rasgos_sujeto(sn_nodo) -> dict | None:
    """Rasgos del sujeto, siguiendo la sección "Rasgos del sujeto" del
    documento: SN simple toma los de su cabeza; SN coordinado es plural,
    persona = 1 si algún miembro es de 1.ª, 2 si alguno es de 2.ª, 3 si
    no; género = masculino si algún miembro es masculino, femenino solo
    si todos lo son.
    """
    if not _es_sn_coordinado(sn_nodo):
        return _rasgos_cabeza_simple(sn_nodo)

    miembros = []
    for m in _miembros_sn(sn_nodo):
        # Un miembro podría ser, en teoría, otro SN coordinado. La
        # gramática no lo produce, pero si lo hiciera tomamos sus rasgos
        # por recursión para no caer en ``None``.
        r = _rasgos_sujeto(m) if _es_sn_coordinado(m) else _rasgos_cabeza_simple(m)
        if r is not None:
            miembros.append(r)
    if not miembros:
        return None

    personas = {m['persona'] for m in miembros}
    if 1 in personas:
        persona = 1
    elif 2 in personas:
        persona = 2
    else:
        persona = 3

    gens = [m['genero'] for m in miembros]
    if any(g == 'm' for g in gens):
        genero = 'm'
    elif all(g == 'f' for g in gens if g is not None):
        genero = 'f'
    else:
        genero = None

    return {'persona': persona, 'numero': 'pl', 'genero': genero}


# ---------------------------------------------------------------------------
# Reglas C1 a C8. Cada función devuelve una lista de ErrorSemantico.
# El docstring copia el enunciado de la tabla del documento.
# ---------------------------------------------------------------------------

def verificar_c1(arbol) -> list[ErrorSemantico]:
    """C1: Dentro del SN, el DET y los ADJ concuerdan en género y número
    con el SUST (género ``c`` acepta ambos).

    Alcance: todos los SN simples del árbol con un SUST como cabeza,
    estén en el sujeto, en el OD, dentro de un atributo o dentro de un
    SP.
    """
    errores: list[ErrorSemantico] = []
    for sn in _recorrer(arbol, 'SN'):
        # Los SN coordinados agrupan otros SN; la concordancia C1 se
        # aplica a cada miembro cuando llega su propio SN.
        if _es_sn_coordinado(sn):
            continue
        sust = _primer_hijo_token(sn, ('SUST',))
        if sust is None:
            # NPROP / PRON: no hay SUST con el que concordar.
            continue
        g_s = sust.valor.get('genero')
        n_s = sust.valor.get('numero')

        # DET directo (R7: DET NOMINAL).
        for h in sn.hijos:
            if _es_token(h) and h.tipo == 'DET':
                g = h.valor.get('genero'); n = h.valor.get('numero')
                if not (_concuerda_gen(g, g_s) and _concuerda_num(n, n_s)):
                    errores.append(ErrorSemantico(
                        f"el determinante '{h.lexema}' ({_fmt_gnum(h.valor)}) "
                        f"no concuerda con '{sust.lexema}' "
                        f"({_fmt_gnum(sust.valor)})",
                        'C1', h.linea, h.columna))

        # ADJ hoja antes del SUST (R8: NOMINAL → ADJ NUCLEO_N).
        for h in sn.hijos:
            if _es_token(h) and h.tipo == 'ADJ':
                g = h.valor.get('genero'); n = h.valor.get('numero')
                if not (_concuerda_gen(g, g_s) and _concuerda_num(n, n_s)):
                    errores.append(ErrorSemantico(
                        f"el adjetivo '{h.lexema}' ({_fmt_gnum(h.valor)}) "
                        f"no concuerda con '{sust.lexema}' "
                        f"({_fmt_gnum(sust.valor)})",
                        'C1', h.linea, h.columna))

        # SADJ posteriores al SUST (R10-R11: ADJS → SADJ*).
        for h in sn.hijos:
            if _es_nodo(h, 'SADJ'):
                adj = _primer_hijo_token(h, ('ADJ',))
                if adj is None:
                    continue
                g = adj.valor.get('genero'); n = adj.valor.get('numero')
                if not (_concuerda_gen(g, g_s) and _concuerda_num(n, n_s)):
                    errores.append(ErrorSemantico(
                        f"el adjetivo '{adj.lexema}' ({_fmt_gnum(adj.valor)}) "
                        f"no concuerda con '{sust.lexema}' "
                        f"({_fmt_gnum(sust.valor)})",
                        'C1', adj.linea, adj.columna))
    return errores


def verificar_c2(arbol) -> list[ErrorSemantico]:
    """C2: ``al`` y ``del`` solo van con un nominal masculino singular;
    ``a el`` y ``de el`` deben contraerse.

    La segunda parte se detecta comparando la *categoría* del token, no
    solo el texto: 'el' DET no es lo mismo que 'él' PRON (R6).
    """
    errores: list[ErrorSemantico] = []
    for sp in _recorrer(arbol, 'SP'):
        if not sp.hijos:
            continue
        cab = sp.hijos[0]
        if not _es_token(cab):
            continue
        # SN interno (siempre viene envuelto como SN según la sección
        # "Árboles sintácticos" del documento).
        sn_interno = None
        for h in sp.hijos[1:]:
            if _es_nodo(h, 'SN'):
                sn_interno = h
                break

        if cab.tipo in ('CONTR_A', 'CONTR_DE'):
            # El nominal debe ser masculino singular.
            if sn_interno is None or _es_sn_coordinado(sn_interno):
                continue
            nuc = _nucleo_sn_simple(sn_interno)
            if nuc is None or nuc.tipo != 'SUST':
                # R23 solo permite NOMINAL (SUST) tras CONTR_A/CONTR_DE.
                continue
            g = nuc.valor.get('genero'); n = nuc.valor.get('numero')
            if g != 'm' or n != 'sg':
                errores.append(ErrorSemantico(
                    f"'{cab.lexema}' solo va con un nominal masculino "
                    f"singular, '{nuc.lexema}' es {_fmt_gnum(nuc.valor)}",
                    'C2', cab.linea, cab.columna))

        elif cab.tipo in ('PREP', 'PREP_DE'):
            # Debe contraerse si viene seguida de DET 'el'.
            if sn_interno is None or _es_sn_coordinado(sn_interno):
                continue
            lema = (cab.valor or {}).get('lema')
            # 'de' siempre es PREP_DE y su lema es 'de'. Para PREP, solo
            # nos interesa 'a'.
            if cab.tipo == 'PREP' and lema != 'a':
                continue
            det = _det_sn_simple(sn_interno)
            if det is None or det.lexema.lower() != 'el':
                continue
            # Nos aseguramos de que es un DET (no un PRON 'él').
            if det.tipo != 'DET':
                continue
            contraido = 'al' if cab.tipo == 'PREP' else 'del'
            base = f"{cab.lexema.lower()} {det.lexema.lower()}"
            errores.append(ErrorSemantico(
                f"'{base}' debe escribirse '{contraido}'",
                'C2', det.linea, det.columna))
    return errores


def verificar_c3(arbol) -> list[ErrorSemantico]:
    """C3: El verbo concuerda con el sujeto en persona y número.

    El sujeto tácito no se comprueba (así lo dice el documento: la
    persona y el número vienen del verbo y no hay nada con qué
    contrastar).
    """
    errores: list[ErrorSemantico] = []
    sv = _sv(arbol)
    if sv is None:
        return errores
    verbo = _verbo_del_sv(sv)
    if verbo is None:
        return errores
    suj = _suj(arbol)
    if suj is None:
        return errores  # sujeto tácito: C3 no aplica
    sn_suj = _sn_del_suj(suj)
    if sn_suj is None:
        return errores
    rsuj = _rasgos_sujeto(sn_suj)
    if rsuj is None:
        return errores
    rv = verbo.valor or {}
    if rsuj['persona'] != rv.get('persona') or rsuj['numero'] != rv.get('numero'):
        errores.append(ErrorSemantico(
            f"el verbo '{verbo.lexema}' ({_fmt_pernum(rv)}) no concuerda "
            f"con el sujeto ({_fmt_pernum(rsuj)})",
            'C3', verbo.linea, verbo.columna))
    return errores


def verificar_c4(arbol) -> list[ErrorSemantico]:
    """C4: El atributo concuerda con el sujeto: un SADJ en género y
    número; un SN, en número. Sujeto coordinado: masculino si algún
    miembro es masculino, femenino solo si todos lo son. Sujeto tácito:
    el número sale del verbo y el género queda libre.
    """
    errores: list[ErrorSemantico] = []
    sv = _sv(arbol)
    if sv is None:
        return errores
    verbo = _verbo_del_sv(sv)
    if verbo is None or verbo.tipo != 'COP':
        return errores  # C4 solo aplica a cópulas
    atrib = _atrib_del_sv(sv)
    if atrib is None or not atrib.hijos:
        return errores

    # Rasgos del sujeto, incluido el caso tácito.
    suj = _suj(arbol)
    if suj is not None:
        sn_suj = _sn_del_suj(suj)
        rsuj = _rasgos_sujeto(sn_suj) if sn_suj is not None else None
    else:
        rv = verbo.valor or {}
        # Sujeto tácito: número y persona vienen del verbo, género libre.
        rsuj = {'persona': rv.get('persona'),
                'numero': rv.get('numero'),
                'genero': None}
    if rsuj is None:
        return errores

    hijo = atrib.hijos[0]
    if _es_nodo(hijo, 'SADJ'):
        adj = _primer_hijo_token(hijo, ('ADJ',))
        if adj is None:
            return errores
        ga = adj.valor.get('genero')
        na = adj.valor.get('numero')
        # Solo evaluamos género cuando el sujeto tiene uno definido: con
        # sujeto tácito queda libre.
        if rsuj['genero'] is not None and not _concuerda_gen(ga, rsuj['genero']):
            errores.append(ErrorSemantico(
                f"el atributo '{adj.lexema}' ({_fmt_gnum(adj.valor)}) "
                f"no concuerda con el sujeto ({_fmt_gnum(rsuj)})",
                'C4', adj.linea, adj.columna))
        elif rsuj['numero'] is not None and na != rsuj['numero']:
            errores.append(ErrorSemantico(
                f"el atributo '{adj.lexema}' ({_fmt_gnum(adj.valor)}) "
                f"no concuerda con el sujeto ({_fmt_gnum(rsuj)})",
                'C4', adj.linea, adj.columna))
    elif _es_nodo(hijo, 'SN'):
        # Atributo SN: solo se comprueba el número.
        if _es_sn_coordinado(hijo):
            # Un atributo SN coordinado (poco común) toma número plural
            # y como cabeza para el mensaje usamos su primer miembro.
            miembros = _miembros_sn(hijo)
            cab = _nucleo_sn_simple(miembros[0]) if miembros else None
            na = 'pl'
        else:
            cab = _nucleo_sn_simple(hijo)
            na = (cab.valor or {}).get('numero') if cab else None
        if cab is None:
            return errores
        if rsuj['numero'] is not None and na != rsuj['numero']:
            errores.append(ErrorSemantico(
                f"el atributo '{cab.lexema}' ({_fmt_gnum(cab.valor)}) "
                f"no concuerda con el sujeto ({_fmt_gnum(rsuj)})",
                'C4', cab.linea, cab.columna))
    return errores


def verificar_c5(arbol) -> list[ErrorSemantico]:
    """C5: Un verbo intransitivo no lleva OD; uno transitivo lo necesita;
    ``ambos`` acepta las dos opciones.

    No se aplica a las cópulas (``COP``), que llevan atributo, no OD.
    """
    errores: list[ErrorSemantico] = []
    sv = _sv(arbol)
    if sv is None:
        return errores
    verbo = _verbo_del_sv(sv)
    if verbo is None or verbo.tipo != 'VERBO':
        return errores
    trans = (verbo.valor or {}).get('trans')
    lema = (verbo.valor or {}).get('lema', verbo.lexema)
    tiene_od = _od_del_sv(sv) is not None
    if trans == 'intr' and tiene_od:
        errores.append(ErrorSemantico(
            f"'{lema}' es intransitivo y no lleva objeto directo",
            'C5', verbo.linea, verbo.columna))
    elif trans == 'trans' and not tiene_od:
        errores.append(ErrorSemantico(
            f"'{lema}' es transitivo y requiere un objeto directo",
            'C5', verbo.linea, verbo.columna))
    return errores


def verificar_c6(arbol) -> list[ErrorSemantico]:
    """C6: Los pronombres de sujeto no funcionan como OD, y ``yo`` y
    ``tú`` no van después de preposición.

    "Pronombre en el OD" se interpreta como cualquier PRON hoja en
    cualquier parte del subárbol OD; "tras preposición" como cualquier
    PRON ``yo``/``tú`` hoja en cualquier parte del subárbol SP.
    """
    errores: list[ErrorSemantico] = []
    sv = _sv(arbol)
    if sv is not None:
        od = _od_del_sv(sv)
        if od is not None:
            for t in _hojas(od):
                if t.tipo == 'PRON':
                    errores.append(ErrorSemantico(
                        f"el pronombre '{t.lexema}' no puede ser objeto "
                        f"directo",
                        'C6', t.linea, t.columna))
    for sp in _recorrer(arbol, 'SP'):
        for t in _hojas(sp):
            if t.tipo == 'PRON' and t.lexema.lower() in ('yo', 'tú'):
                errores.append(ErrorSemantico(
                    f"'{t.lexema}' no puede ir después de una preposición",
                    'C6', t.linea, t.columna))
    return errores


def verificar_c7(arbol) -> list[ErrorSemantico]:
    """C7: Un sujeto con sustantivo común necesita determinante.

    Cada miembro del sujeto (simple o coordinado) se revisa por
    separado: si es un SN simple cuya cabeza es un SUST y no lleva DET,
    es error (los NPROP y los PRON no necesitan determinante).
    """
    errores: list[ErrorSemantico] = []
    suj = _suj(arbol)
    if suj is None:
        return errores  # sujeto tácito: no hay miembros que revisar
    sn = _sn_del_suj(suj)
    if sn is None:
        return errores
    for miembro in _miembros_sn(sn):
        if _es_sn_coordinado(miembro):
            # Coordinación anidada (no se produce con la gramática
            # actual, pero no estorba sostener la recursión).
            for sub in _miembros_sn(miembro):
                _marcar_c7(sub, errores)
        else:
            _marcar_c7(miembro, errores)
    return errores


def _marcar_c7(sn_simple, errores):
    sust = _primer_hijo_token(sn_simple, ('SUST',))
    if sust is None:
        return  # cabeza NPROP o PRON: no hace falta DET
    det = _det_sn_simple(sn_simple)
    if det is None:
        errores.append(ErrorSemantico(
            f"el sujeto '{sust.lexema}' necesita un determinante",
            'C7', sust.linea, sust.columna))


def verificar_c8(arbol) -> list[ErrorSemantico]:
    """C8: El adverbio temporal concuerda con el tiempo del verbo:
    ``ayer`` con pretérito, ``pronto`` con futuro. Si ``token.valor['tiempo']``
    es una lista (``caminamos``: ``[pres, pret]``), basta con que uno de
    los tiempos sea compatible.
    """
    errores: list[ErrorSemantico] = []
    sv = _sv(arbol)
    if sv is None:
        return errores
    verbo = _verbo_del_sv(sv)
    if verbo is None:
        return errores
    tiempo = (verbo.valor or {}).get('tiempo')
    if tiempo is None:
        return errores
    tiempos = list(tiempo) if isinstance(tiempo, (list, tuple)) else [tiempo]

    for t in _hojas(arbol):
        if t.tipo != 'ADV':
            continue
        ref = (t.valor or {}).get('referencia')
        if ref == 'pasado' and 'pret' not in tiempos:
            errores.append(ErrorSemantico(
                f"'{t.lexema}' (pasado) no es compatible con un verbo en "
                f"{_fmt_tiempos(tiempos)}",
                'C8', t.linea, t.columna))
        elif ref == 'futuro' and 'fut' not in tiempos:
            errores.append(ErrorSemantico(
                f"'{t.lexema}' (futuro) no es compatible con un verbo en "
                f"{_fmt_tiempos(tiempos)}",
                'C8', t.linea, t.columna))
    return errores


# ---------------------------------------------------------------------------
# API pública.
# ---------------------------------------------------------------------------

def verificar(arbol) -> list[ErrorSemantico]:
    """Aplica las 8 reglas al árbol y devuelve TODOS los errores
    encontrados, ordenados por aparición (línea, columna).
    """
    errores: list[ErrorSemantico] = []
    errores.extend(verificar_c1(arbol))
    errores.extend(verificar_c2(arbol))
    errores.extend(verificar_c3(arbol))
    errores.extend(verificar_c4(arbol))
    errores.extend(verificar_c5(arbol))
    errores.extend(verificar_c6(arbol))
    errores.extend(verificar_c7(arbol))
    errores.extend(verificar_c8(arbol))
    errores.sort(key=lambda e: (e.linea, e.columna))
    return errores
