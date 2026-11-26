"""Conversión del árbol sintáctico del parser al formato Universal Dependencies.

Recibe un árbol en la notación con corchetes (la misma que produce el parser
descendente recursivo y la que trae el set de prueba) y devuelve, por cada
token, su UPOS, su cabeza (índice 1-basado; 0 = raíz) y su relación UD.

Las decisiones vienen de la sección "Equivalencias con Universal Dependencies"
del documento: en copulativas la raíz es el núcleo del ATRIB, la cópula va
`cop` y el sujeto `nsubj` sobre esa misma raíz. El núcleo de un SN es su
SUST / NPROP / PRON, y el de un SN coordinado es su primer miembro.
"""

from __future__ import annotations

import nltk


# Categorías del lexer (preterminales que aparecen como hojas del árbol).
CATEGORIAS = frozenset({
    'DET', 'SUST', 'NPROP', 'PRON', 'ADJ', 'INTENS',
    'VERBO', 'COP', 'NEG', 'ADV',
    'PREP', 'PREP_DE', 'CONTR_A', 'CONTR_DE',
    'CONJ', 'COMA', 'PUNTO',
})

# Mapeo categoría -> UPOS de UD (tabla del documento).
CAT_A_UPOS = {
    'DET': 'DET',
    'SUST': 'NOUN',
    'NPROP': 'PROPN',
    'PRON': 'PRON',
    'ADJ': 'ADJ',
    'INTENS': 'ADV',
    'VERBO': 'VERB',
    'COP': 'AUX',
    'NEG': 'ADV',
    'ADV': 'ADV',
    'PREP': 'ADP',
    'PREP_DE': 'ADP',
    'CONTR_A': 'ADP',
    'CONTR_DE': 'ADP',
    'CONJ': 'CCONJ',
    'COMA': 'PUNCT',
    'PUNTO': 'PUNCT',
}


# ---------------------------------------------------------------------------
# Utilidades para recorrer árboles NLTK.
# ---------------------------------------------------------------------------

def _es_preterm(t):
    """Un preterminal es un `nltk.Tree` cuya etiqueta es una categoría del
    lexer y cuyo único hijo es la cadena del lexema."""
    return isinstance(t, nltk.Tree) and t.label() in CATEGORIAS


def _recolectar_preterms(t, lista):
    """DFS in-orden: añade a `lista` los preterminales en orden de aparición."""
    if _es_preterm(t):
        lista.append(t)
        return
    for h in t:
        _recolectar_preterms(h, lista)


def _preterm_hijo(t, etiquetas):
    """Primer preterminal hijo directo de `t` cuya etiqueta esté en el
    conjunto `etiquetas` (o cadena). Devuelve None si no existe."""
    if isinstance(etiquetas, str):
        etiquetas = (etiquetas,)
    for h in t:
        if _es_preterm(h) and h.label() in etiquetas:
            return h
    return None


def _arbol_hijo(t, etiqueta):
    """Primer hijo directo de `t` que sea un árbol con `etiqueta`."""
    for h in t:
        if isinstance(h, nltk.Tree) and h.label() == etiqueta:
            return h
    return None


def _arboles_hijos(t, etiqueta):
    """Todos los hijos directos de `t` que son árboles con `etiqueta`."""
    return [h for h in t if isinstance(h, nltk.Tree) and h.label() == etiqueta]


# ---------------------------------------------------------------------------
# Conversión principal.
# ---------------------------------------------------------------------------

def arbol_a_dependencias(arbol_str: str) -> dict:
    """Convierte un árbol en corchetes a una representación tipo UD.

    Devuelve un diccionario con:
      - `tokens`       : lista de palabras en el orden de la oración.
      - `categorias`   : etiqueta del lexer para cada token.
      - `upos`         : UPOS equivalente.
      - `cabezas`      : índice 1-basado de la cabeza (0 = raíz).
      - `relaciones`   : relación UD.
    """
    arbol = nltk.Tree.fromstring(arbol_str)

    preterms = []
    _recolectar_preterms(arbol, preterms)
    # id(preterm) -> índice 1-basado. Usamos id() porque los preterminales
    # son objetos únicos en el árbol.
    idx_de = {id(p): i + 1 for i, p in enumerate(preterms)}

    def i(p):                     # Índice 1-basado de un preterminal.
        return idx_de[id(p)]

    n = len(preterms)
    tokens = [p[0] for p in preterms]
    categorias = [p.label() for p in preterms]
    upos = [CAT_A_UPOS[c] for c in categorias]
    cabezas = [None] * n
    rels = [None] * n

    # ----------------------------------------------------------------
    # Cabezas ("núcleos") de cada tipo de constituyente.
    # ----------------------------------------------------------------

    def head_sn(sn):
        """Devuelve el índice del núcleo de un SN (simple o coordinado)."""
        # Si contiene hijos SN, es coordinado: núcleo del primer miembro.
        sn_hijos = _arboles_hijos(sn, 'SN')
        if sn_hijos:
            return head_sn(sn_hijos[0])
        # SN simple: el primer SUST/NPROP/PRON entre hijos directos.
        p = _preterm_hijo(sn, ('SUST', 'NPROP', 'PRON'))
        if p is None:
            raise ValueError(f"SN sin núcleo nominal: {sn}")
        return i(p)

    def head_sp(sp):
        inner = _arbol_hijo(sp, 'SN')
        return head_sn(inner)

    def head_sadj(s):
        return i(_preterm_hijo(s, 'ADJ'))

    def head_sadv(s):
        return i(_preterm_hijo(s, 'ADV'))

    def head_atrib(a):
        c = a[0]
        if c.label() == 'SADJ':
            return head_sadj(c)
        return head_sn(c)

    def head_sv(sv):
        verbo = _preterm_hijo(sv, 'VERBO')
        if verbo is not None:
            return i(verbo)
        # Copulativa: la raíz es el núcleo del ATRIB.
        atrib = _arbol_hijo(sv, 'ATRIB')
        return head_atrib(atrib)

    # ----------------------------------------------------------------
    # Resolución de dependencias internas de un SN, SP, SADJ.
    # Se asume que la cabeza externa del constituyente ya fue asignada.
    # ----------------------------------------------------------------

    def resolver_sp(sp):
        """La preposición es `case` del núcleo del SN interno."""
        prep = _preterm_hijo(sp, ('PREP', 'PREP_DE', 'CONTR_A', 'CONTR_DE'))
        sn_interno = _arbol_hijo(sp, 'SN')
        cab = head_sn(sn_interno)
        cabezas[i(prep) - 1] = cab
        rels[i(prep) - 1] = 'case'
        resolver_sn(sn_interno)

    def resolver_sn(sn):
        """Asigna las dependencias internas de un SN (simple o coordinado).

        El núcleo externo (lo que apunta "hacia afuera": nsubj, obj, obl,
        nmod, root) ya fue asignado por el llamador.
        """
        sn_hijos = _arboles_hijos(sn, 'SN')
        if sn_hijos:
            # Coordinación: el primer miembro es el núcleo externo.
            primer = sn_hijos[0]
            cab_primer = head_sn(primer)
            resolver_sn(primer)
            # Los demás miembros son `conj` del núcleo del primero.
            for miembro in sn_hijos[1:]:
                h = head_sn(miembro)
                cabezas[h - 1] = cab_primer
                rels[h - 1] = 'conj'
                resolver_sn(miembro)
            # CONJ y COMA: apuntan al miembro que las sigue (cc y punct).
            ninos = list(sn)
            for k, h in enumerate(ninos):
                if _es_preterm(h) and h.label() in ('COMA', 'CONJ'):
                    sig = None
                    for m in range(k + 1, len(ninos)):
                        if isinstance(ninos[m], nltk.Tree) and ninos[m].label() == 'SN':
                            sig = ninos[m]
                            break
                    objetivo = head_sn(sig) if sig is not None else cab_primer
                    cabezas[i(h) - 1] = objetivo
                    rels[i(h) - 1] = 'cc' if h.label() == 'CONJ' else 'punct'
            return

        # SN simple: el núcleo es un SUST, NPROP o PRON.
        nucleo = head_sn(sn)
        for h in sn:
            if _es_preterm(h):
                lab = h.label()
                k = i(h)
                if lab == 'DET':
                    cabezas[k - 1] = nucleo
                    rels[k - 1] = 'det'
                elif lab == 'ADJ':
                    # ADJ pre-sustantivo (NOMINAL): hoja suelta (sin SADJ).
                    cabezas[k - 1] = nucleo
                    rels[k - 1] = 'amod'
                # SUST, NPROP, PRON: son el núcleo, ya se asigna por fuera.
            elif isinstance(h, nltk.Tree):
                lab = h.label()
                if lab == 'SADJ':
                    resolver_sadj(h, cabeza_ext=nucleo, rel_ext='amod')
                elif lab == 'SP':
                    # SP junto a un sustantivo: nmod sobre el núcleo del SN.
                    h_sp = head_sp(h)
                    cabezas[h_sp - 1] = nucleo
                    rels[h_sp - 1] = 'nmod'
                    resolver_sp(h)

    def resolver_sadj(sadj, cabeza_ext, rel_ext):
        """INTENS es `advmod` del ADJ; el ADJ apunta donde diga el llamador.

        Si el llamador es quien pone la cabeza del ADJ (porque es la raíz
        de una oración copulativa, por ejemplo), pasar `cabeza_ext=None` y
        `rel_ext=None`.
        """
        intens = _preterm_hijo(sadj, 'INTENS')
        adj = _preterm_hijo(sadj, 'ADJ')
        if intens is not None:
            cabezas[i(intens) - 1] = i(adj)
            rels[i(intens) - 1] = 'advmod'
        if cabeza_ext is not None:
            cabezas[i(adj) - 1] = cabeza_ext
            rels[i(adj) - 1] = rel_ext

    # ----------------------------------------------------------------
    # Nivel O: asignación de la oración entera.
    # ----------------------------------------------------------------

    sv = _arbol_hijo(arbol, 'SV')
    suj = _arbol_hijo(arbol, 'SUJ')
    verbo = _preterm_hijo(sv, 'VERBO')
    cop = _preterm_hijo(sv, 'COP')

    raiz = head_sv(sv)
    cabezas[raiz - 1] = 0
    rels[raiz - 1] = 'root'

    # Cópula: `cop` -> raíz (núcleo del ATRIB).
    if cop is not None:
        cabezas[i(cop) - 1] = raiz
        rels[i(cop) - 1] = 'cop'

    # Sujeto: nsubj -> raíz (que es el verbo o el núcleo del ATRIB).
    if suj is not None:
        h_suj = head_sn(suj[0])
        cabezas[h_suj - 1] = raiz
        rels[h_suj - 1] = 'nsubj'
        resolver_sn(suj[0])

    # Hijos directos de SV: SADV pre-verbal, NEG, OD, CC, ATRIB.
    ancla_v = i(verbo) if verbo is not None else raiz
    for h in sv:
        if _es_preterm(h):
            lab = h.label()
            if lab in ('ADV', 'NEG'):   # SADV ya se maneja como árbol.
                cabezas[i(h) - 1] = ancla_v
                rels[i(h) - 1] = 'advmod'
            # VERBO ya es root; COP ya es cop.
        elif isinstance(h, nltk.Tree):
            lab = h.label()
            if lab == 'SADV':
                cabezas[head_sadv(h) - 1] = ancla_v
                rels[head_sadv(h) - 1] = 'advmod'
            elif lab == 'OD':
                hd = head_sn(h[0])
                cabezas[hd - 1] = i(verbo)
                rels[hd - 1] = 'obj'
                resolver_sn(h[0])
            elif lab == 'ATRIB':
                c = h[0]
                if c.label() == 'SADJ':
                    # El ADJ ya es root (asignado arriba); solo resta INTENS.
                    resolver_sadj(c, cabeza_ext=None, rel_ext=None)
                else:
                    # SN: núcleo ya es root; resolver internos.
                    resolver_sn(c)
            elif lab == 'CC':
                c = h[0]
                if c.label() == 'SADV':
                    hd = head_sadv(c)
                    cabezas[hd - 1] = ancla_v
                    rels[hd - 1] = 'advmod'
                else:  # SP
                    hd = head_sp(c)
                    cabezas[hd - 1] = ancla_v
                    rels[hd - 1] = 'obl'
                    resolver_sp(c)

    # PUNTO final (y cualquier COMA/PUNTO suelto): punct -> raíz.
    for p in preterms:
        if rels[i(p) - 1] is None and p.label() in ('PUNTO', 'COMA'):
            cabezas[i(p) - 1] = raiz
            rels[i(p) - 1] = 'punct'

    return {
        'tokens': tokens,
        'categorias': categorias,
        'upos': upos,
        'cabezas': cabezas,
        'relaciones': rels,
    }


# ---------------------------------------------------------------------------
# Punto de entrada por consola (depuración).
# ---------------------------------------------------------------------------

def _main(argv):
    import sys
    if len(argv) != 2:
        print("Uso: python ud.py '<árbol en corchetes>'", file=sys.stderr)
        return 1
    r = arbol_a_dependencias(argv[1])
    for k, tok in enumerate(r['tokens']):
        print(f"{k+1:>2} {tok:<12} {r['categorias'][k]:<8} "
              f"{r['upos'][k]:<6} cab={r['cabezas'][k]} {r['relaciones'][k]}")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(_main(sys.argv))
