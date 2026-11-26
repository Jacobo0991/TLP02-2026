"""Dibuja un árbol sintáctico (fase2.parser_es.Nodo) como imagen PNG.

Algoritmo: se asigna a cada hoja una x consecutiva (0, 1, 2, …) de izquierda
a derecha, y cada nodo interno toma como x el promedio de las x de sus
hijos. La profundidad del nodo determina su y (hacia abajo). Luego se traza
con matplotlib: texto por nodo y líneas padre→hijo. No se usa Graphviz ni
ningún programa externo.
"""

from __future__ import annotations

def _es_nodo(obj):
    """Nodo (interno) vs. Token (hoja). Se identifica por atributo, no por
    isinstance, para que funcione aunque parser_es se cargue como __main__
    (clase Nodo distinta de la importada por nombre completo).
    """
    return hasattr(obj, 'hijos') and hasattr(obj, 'etiqueta')


# Nombre humano asociado a cada código del árbol. Se pinta entre paréntesis
# debajo del código para que el dibujo se entienda sin consultar la tabla de
# categorías.
NOMBRES = {
    # Nodos visibles del árbol.
    'O':        'oración',
    'SUJ':      'sujeto',
    'SN':       'sintagma nominal',
    'SV':       'sintagma verbal',
    'OD':       'objeto directo',
    'ATRIB':    'atributo',
    'CC':       'compl. circunstancial',
    'SP':       'sintagma preposicional',
    'SADJ':     'sintagma adjetival',
    'SADV':     'sintagma adverbial',
    # Categorías léxicas (hojas).
    'DET':      'determinante',
    'SUST':     'sustantivo',
    'NPROP':    'nombre propio',
    'PRON':     'pronombre',
    'ADJ':      'adjetivo',
    'INTENS':   'intensificador',
    'VERBO':    'verbo',
    'COP':      'cópula',
    'NEG':      'negación',
    'ADV':      'adverbio',
    'PREP':     'preposición',
    'PREP_DE':  'preposición "de"',
    'CONTR_A':  'contracción "al"',
    'CONTR_DE': 'contracción "del"',
    'CONJ':     'conjunción',
    'COMA':     'coma',
    'PUNTO':    'punto',
}


def _etiqueta_con_nombre(codigo):
    """Devuelve 'CODIGO\n(nombre)' si hay traducción; si no, el código solo."""
    nombre = NOMBRES.get(codigo)
    return f"{codigo}\n({nombre})" if nombre else codigo


def _recolectar_posiciones(nodo, profundidad=0, contador=None, pos=None):
    """Recorre el árbol y devuelve {id(nodo_o_token): (x, y, texto)}."""
    if contador is None:
        contador = [0]
    if pos is None:
        pos = {}

    if _es_nodo(nodo):
        xs = []
        for h in nodo.hijos:
            _recolectar_posiciones(h, profundidad + 1, contador, pos)
            xs.append(pos[id(h)][0])
        x = sum(xs) / len(xs) if xs else contador[0]
        # Nodo interno: etiqueta + nombre humano.
        pos[id(nodo)] = (x, -profundidad, _etiqueta_con_nombre(nodo.etiqueta))
    else:
        # Hoja (Token): categoría + nombre humano + lexema.
        x = contador[0]
        contador[0] += 1
        texto = f"{_etiqueta_con_nombre(nodo.tipo)}\n{nodo.lexema}"
        pos[id(nodo)] = (x, -profundidad, texto)

    return pos


def dibujar_arbol(nodo: Nodo, ruta_png: str) -> None:
    """Guarda en `ruta_png` una imagen del árbol que empieza en `nodo`."""
    # Import diferido para no exigir matplotlib al parser.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    pos = _recolectar_posiciones(nodo)

    # Dimensionado del lienzo según el ancho del árbol. Al añadir la
    # traducción de cada código, cada nodo es más ancho: subimos el factor
    # horizontal para que los rectángulos no se superpongan.
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ancho = max(8.0, (max(xs) - min(xs) + 1) * 1.8)
    alto = max(4.0, (max(ys) - min(ys) + 1) * 1.3)

    fig, ax = plt.subplots(figsize=(ancho, alto))

    # Recorremos otra vez para dibujar líneas padre→hijo.
    def _dibujar(n):
        x1, y1, _ = pos[id(n)]
        if _es_nodo(n):
            for h in n.hijos:
                x2, y2, _ = pos[id(h)]
                ax.plot([x1, x2], [y1, y2], color='gray', linewidth=0.8,
                        zorder=1)
                _dibujar(h)

    _dibujar(nodo)

    # Texto de cada nodo encima de un rectángulo claro.
    for _, (x, y, texto) in pos.items():
        ax.text(
            x, y, texto,
            ha='center', va='center',
            fontsize=9,
            bbox=dict(
                boxstyle='round,pad=0.25',
                facecolor='white', edgecolor='black', linewidth=0.7,
            ),
            zorder=2,
        )

    ax.set_axis_off()
    ax.margins(0.1)
    plt.savefig(ruta_png, dpi=150, bbox_inches='tight')
    plt.close(fig)
