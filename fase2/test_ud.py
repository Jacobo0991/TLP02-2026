"""Pruebas de `fase2/ud.py`.

Toma los 4 árboles de la sección "Árboles sintácticos" del documento y los
compara con las dependencias UD esperadas (escritas a mano a partir de la
tabla "Equivalencias con Universal Dependencies"). No usa `unittest`: cada
caso imprime pasa/falla y el script sale con código 1 si alguno falla, para
poder encadenarlo con los demás scripts de la Fase 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar como script sin instalar el paquete.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.ud import arbol_a_dependencias   # noqa: E402


# ---------------------------------------------------------------------------
# Casos del documento (sección "Árboles sintácticos").
# Cada entrada: (id, árbol en corchetes, tokens esperados, upos esperados,
# cabezas esperadas (1-basado, 0 = raíz), relaciones UD esperadas).
# ---------------------------------------------------------------------------

CASOS = [
    (
        'ej1-el-perro-negro-come-manzanas',
        '(O (SUJ (SN (DET El) (SUST perro) (SADJ (ADJ negro)))) '
        '(SV (VERBO come) (OD (SN (SUST manzanas)))) (PUNTO .))',
        ['El', 'perro', 'negro', 'come', 'manzanas', '.'],
        ['DET', 'NOUN', 'ADJ', 'VERB', 'NOUN', 'PUNCT'],
        [2, 4, 2, 0, 4, 4],
        ['det', 'nsubj', 'amod', 'root', 'obj', 'punct'],
    ),
    (
        'ej2-ana-no-compro-los-libros-del-profesor-ayer',
        '(O (SUJ (SN (NPROP Ana))) '
        '(SV (NEG no) (VERBO compró) '
        '    (OD (SN (DET los) (SUST libros) '
        '             (SP (CONTR_DE del) (SN (SUST profesor))))) '
        '    (CC (SADV (ADV ayer)))) '
        '(PUNTO .))',
        ['Ana', 'no', 'compró', 'los', 'libros', 'del', 'profesor', 'ayer', '.'],
        ['PROPN', 'ADV', 'VERB', 'DET', 'NOUN', 'ADP', 'NOUN', 'ADV', 'PUNCT'],
        [3, 3, 0, 5, 3, 7, 5, 3, 3],
        ['nsubj', 'advmod', 'root', 'det', 'obj', 'case', 'nmod', 'advmod', 'punct'],
    ),
    (
        'ej3-ana-y-luis-son-muy-altos',
        '(O (SUJ (SN (SN (NPROP Ana)) (CONJ y) (SN (NPROP Luis)))) '
        '(SV (COP son) (ATRIB (SADJ (INTENS muy) (ADJ altos)))) (PUNTO .))',
        ['Ana', 'y', 'Luis', 'son', 'muy', 'altos', '.'],
        ['PROPN', 'CCONJ', 'PROPN', 'AUX', 'ADV', 'ADJ', 'PUNCT'],
        [6, 3, 1, 6, 6, 0, 6],
        ['nsubj', 'cc', 'conj', 'cop', 'advmod', 'root', 'punct'],
    ),
    (
        'ej4-siempre-caminamos-en-el-parque',
        '(O (SV (SADV (ADV Siempre)) (VERBO caminamos) '
        '       (CC (SP (PREP en) (SN (DET el) (SUST parque))))) '
        '(PUNTO .))',
        ['Siempre', 'caminamos', 'en', 'el', 'parque', '.'],
        ['ADV', 'VERB', 'ADP', 'DET', 'NOUN', 'PUNCT'],
        [2, 0, 5, 5, 2, 2],
        ['advmod', 'root', 'case', 'det', 'obl', 'punct'],
    ),
]


def _comparar_lista(nombre, esperado, obtenido):
    """Compara dos listas y reporta diferencias. Devuelve True si coinciden."""
    if esperado == obtenido:
        return True
    print(f"    [{nombre}] diferencia:")
    print(f"      esperado: {esperado}")
    print(f"      obtenido: {obtenido}")
    # Listar los índices distintos.
    for k, (a, b) in enumerate(zip(esperado, obtenido)):
        if a != b:
            print(f"        token {k+1}: esperado {a!r}, obtenido {b!r}")
    return False


def _probar_caso(caso):
    nombre, arbol, tokens_esp, upos_esp, cab_esp, rel_esp = caso
    print(f"- {nombre}")
    r = arbol_a_dependencias(arbol)
    ok = True
    ok &= _comparar_lista('tokens', tokens_esp, r['tokens'])
    ok &= _comparar_lista('upos', upos_esp, r['upos'])
    ok &= _comparar_lista('cabezas', cab_esp, r['cabezas'])
    ok &= _comparar_lista('relaciones', rel_esp, r['relaciones'])
    if ok:
        print("    OK")
    return ok


def main():
    print("Prueba de fase2/ud.py — 4 árboles del documento")
    todos_ok = True
    for caso in CASOS:
        todos_ok &= _probar_caso(caso)
    if todos_ok:
        print("\n4/4 árboles correctos.")
        return 0
    print("\nFallaron pruebas.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
