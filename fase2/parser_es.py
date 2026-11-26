"""Parser descendente recursivo LL(1) para el subconjunto controlado del
español definido en fase2/docs/gramatica_espanol.md.

Cada método se corresponde con una regla EBNF de la sección "Versión EBNF
y análisis LL(1)" del documento, y menciona en su docstring las reglas R1-R24
equivalentes de la gramática base, para poder defender la implementación en
la presentación.

Nodos visibles del árbol: O, SUJ, SN, SV, OD, ATRIB, CC, SP, SADJ y SADV.
Los no terminales auxiliares (FIN, COORD, LISTA, SNS, NOMINAL, NUCLEO_N,
ADJS, COMP_N, MOD_PRE, NEG_OPC, PRED, OD_OPC y CCS) se aplanan: sus hijos
suben al padre visible.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Permite ejecutar como script o importar como módulo.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase1.lexer import Token, ErrorLexico  # noqa: E402

from fase2.lexer_es import (  # noqa: E402
    tokenizar,
    DET, SUST, NPROP, PRON, ADJ, INTENS, VERBO, COP, NEG, ADV,
    PREP, PREP_DE, CONTR_A, CONTR_DE, CONJ, COMA, PUNTO, EOF,
)


# ---------------------------------------------------------------------------
# Nodo del árbol sintáctico.
# ---------------------------------------------------------------------------

class Nodo:
    """Nodo interno del árbol. Las hojas son objetos `Token` de la Fase 1."""

    __slots__ = ('etiqueta', 'hijos')

    def __init__(self, etiqueta, hijos):
        self.etiqueta = etiqueta
        self.hijos = list(hijos)

    def a_corchetes(self) -> str:
        """Cadena canónica en una sola línea, `(ETIQUETA hijos...)`.

        Las hojas se escriben `(CATEGORIA lexema)` con el lexema tal cual
        aparece en la oración (mayúsculas y tildes).
        """
        partes = [self.etiqueta]
        for h in self.hijos:
            if isinstance(h, Nodo):
                partes.append(h.a_corchetes())
            else:
                # Hoja: un Token.
                partes.append(f"({h.tipo} {h.lexema})")
        return "(" + " ".join(partes) + ")"

    def a_nltk(self):
        """Devuelve un `nltk.Tree` equivalente (para pretty_print y pruebas)."""
        import nltk  # Import diferido: nltk no es obligatorio para parsear.
        return nltk.Tree.fromstring(self.a_corchetes())

    def __repr__(self):
        return self.a_corchetes()


# ---------------------------------------------------------------------------
# Errores sintácticos.
# ---------------------------------------------------------------------------

class ErrorSintactico(Exception):
    """Se dispara en el primer token que no case con la regla activa."""

    def __init__(self, mensaje, col):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.col = col

    def __str__(self) -> str:
        return f"Error sintáctico [col {self.col}]: {self.mensaje}"


# ---------------------------------------------------------------------------
# Parser descendente recursivo.
# ---------------------------------------------------------------------------

# Conjuntos de predicción reutilizables (los que se usan en varios puntos).
_INICIO_SNS = (DET, NPROP, PRON, SUST)       # Tokens con que arranca un SNS.
_INICIO_CC = (ADV, PREP, PREP_DE, CONTR_A, CONTR_DE)  # CC → SADV | SP.


class Parser:
    """Parser LL(1) sin retroceso. Decide con un solo token de anticipación."""

    def __init__(self, tokens):
        self.tokens = tokens
        self._i = 0

    # --- utilidades ---

    def actual(self) -> Token:
        return self.tokens[self._i]

    def consumir(self, cat: str) -> Token:
        if self.actual().tipo != cat:
            self._error({cat})
        tok = self.actual()
        self._i += 1
        return tok

    def _error(self, esperadas):
        tok = self.actual()
        esperadas_str = ", ".join(sorted(esperadas))
        lex = tok.lexema if tok.tipo != EOF else 'fin'
        raise ErrorSintactico(
            f"se esperaba {esperadas_str}, se encontró '{lex}' ({tok.tipo})",
            tok.columna,
        )

    # --- O (R1, R2) ---

    def o(self) -> Nodo:
        """R1: O → SUJ SV FIN | SV FIN. R2: FIN → PUNTO | ε."""
        hijos = []
        tipo = self.actual().tipo
        if tipo in _INICIO_SNS:
            hijos.append(self.suj())
        elif tipo not in (ADV, NEG, VERBO, COP):
            self._error(set(_INICIO_SNS) | {ADV, NEG, VERBO, COP})
        hijos.append(self.sv())
        # FIN: el PUNTO es opcional.
        if self.actual().tipo == PUNTO:
            hijos.append(self.consumir(PUNTO))
        if self.actual().tipo != EOF:
            self._error({PUNTO, EOF})
        return Nodo('O', hijos)

    # --- SUJ (R3) ---

    def suj(self) -> Nodo:
        """R3: SUJ → SN."""
        return Nodo('SUJ', [self.sn()])

    # --- SN y coordinación (R4, R5, R6) ---

    def sn(self) -> Nodo:
        """R4-R6: SN → SNS [ { COMA SNS } CONJ SNS ].

        Si hay coordinación, cada miembro se envuelve en su propio SN y las
        hojas COMA y CONJ quedan como hojas del SN padre.
        """
        primera = self.sns()
        if self.actual().tipo in (COMA, CONJ):
            miembros = [Nodo('SN', primera)]
            # LISTA: cero o más COMA SNS.
            while self.actual().tipo == COMA:
                miembros.append(self.consumir(COMA))
                miembros.append(Nodo('SN', self.sns()))
            # Al final, CONJ SNS obligatorio.
            miembros.append(self.consumir(CONJ))
            miembros.append(Nodo('SN', self.sns()))
            return Nodo('SN', miembros)
        return Nodo('SN', primera)

    # --- SNS (R7) ---

    def sns(self):
        """R7: SNS → DET NOMINAL | NPROP | PRON | NUCLEO_N.

        Devuelve una lista de hijos, no un Nodo: el envoltorio lo pone el
        llamador (SN, OD, ATRIB, SP, SP_DE).
        """
        tipo = self.actual().tipo
        if tipo == DET:
            hijos = [self.consumir(DET)]
            hijos.extend(self.nominal())
            return hijos
        if tipo == NPROP:
            return [self.consumir(NPROP)]
        if tipo == PRON:
            return [self.consumir(PRON)]
        if tipo == SUST:
            return self.nucleo_n()
        self._error(set(_INICIO_SNS))

    # --- NOMINAL (R8) ---

    def nominal(self):
        """R8: NOMINAL → [ADJ] NUCLEO_N.

        El ADJ antes del sustantivo es una hoja (no se envuelve en SADJ,
        porque no admite INTENS; los adjetivos post-nominales sí se
        envuelven en SADJ, R10-R11).
        """
        hijos = []
        if self.actual().tipo == ADJ:
            hijos.append(self.consumir(ADJ))
        hijos.extend(self.nucleo_n())
        return hijos

    # --- NUCLEO_N (R9, R10, R12) ---

    def nucleo_n(self):
        """R9: NUCLEO_N → SUST ADJS COMP_N.

        R12 (conflicto): si después del sustantivo llega PREP_DE o CONTR_DE,
        se une al sustantivo (regla del 'else' colgante del documento).
        """
        hijos = [self.consumir(SUST)]
        # R10/R11: ADJS → SADJ ADJS | ε.
        while self.actual().tipo in (INTENS, ADJ):
            hijos.append(self.sadj())
        # R12 (COMP_N): se toma SP_DE siempre que se pueda.
        if self.actual().tipo in (PREP_DE, CONTR_DE):
            hijos.append(self.sp_de())
        return hijos

    # --- SADJ (R11) ---

    def sadj(self) -> Nodo:
        """R11: SADJ → INTENS ADJ | ADJ."""
        hijos = []
        if self.actual().tipo == INTENS:
            hijos.append(self.consumir(INTENS))
        if self.actual().tipo != ADJ:
            self._error({ADJ})
        hijos.append(self.consumir(ADJ))
        return Nodo('SADJ', hijos)

    # --- SP_DE (R13) ---
    # SP_DE se emite con etiqueta 'SP' (sección Árboles sintácticos).

    def sp_de(self) -> Nodo:
        """R13: SP_DE → PREP_DE SNS | CONTR_DE NOMINAL."""
        tipo = self.actual().tipo
        if tipo == PREP_DE:
            prep = self.consumir(PREP_DE)
            sn_interno = Nodo('SN', self.sns())
            return Nodo('SP', [prep, sn_interno])
        if tipo == CONTR_DE:
            contr = self.consumir(CONTR_DE)
            sn_interno = Nodo('SN', self.nominal())
            return Nodo('SP', [contr, sn_interno])
        self._error({PREP_DE, CONTR_DE})

    # --- SV (R14 .. R18, R21, R22) ---

    def sv(self) -> Nodo:
        """R14: SV → MOD_PRE NEG_OPC PRED CCS.

        MOD_PRE (R15) y NEG_OPC (R16) aportan a SV como hijos directos
        (SADV y la hoja NEG); PRED (R17) añade VERBO + OD o COP + ATRIB;
        CCS (R21) añade cero o más CC.
        """
        hijos = []
        # R15 MOD_PRE → SADV | ε.
        if self.actual().tipo == ADV:
            hijos.append(self.sadv())
        # R16 NEG_OPC → NEG | ε.
        if self.actual().tipo == NEG:
            hijos.append(self.consumir(NEG))
        # R17 PRED → VERBO OD_OPC | COP ATRIB.
        tipo = self.actual().tipo
        if tipo == VERBO:
            hijos.append(self.consumir(VERBO))
            # R18 OD_OPC → OD | ε.
            if self.actual().tipo in _INICIO_SNS:
                hijos.append(self.od())
        elif tipo == COP:
            hijos.append(self.consumir(COP))
            hijos.append(self.atrib())
        else:
            self._error({VERBO, COP})
        # R21 CCS → CC CCS | ε.
        while self.actual().tipo in _INICIO_CC:
            hijos.append(self.cc())
        return Nodo('SV', hijos)

    # --- OD (R19) ---

    def od(self) -> Nodo:
        """R19: OD → SN."""
        return Nodo('OD', [self.sn()])

    # --- ATRIB (R20) ---

    def atrib(self) -> Nodo:
        """R20: ATRIB → SADJ | SN."""
        tipo = self.actual().tipo
        if tipo in (INTENS, ADJ):
            return Nodo('ATRIB', [self.sadj()])
        if tipo in _INICIO_SNS:
            return Nodo('ATRIB', [self.sn()])
        self._error({INTENS, ADJ, DET, NPROP, PRON, SUST})

    # --- CC (R22) ---

    def cc(self) -> Nodo:
        """R22: CC → SADV | SP."""
        tipo = self.actual().tipo
        if tipo == ADV:
            return Nodo('CC', [self.sadv()])
        if tipo in (PREP, PREP_DE, CONTR_A, CONTR_DE):
            return Nodo('CC', [self.sp()])
        self._error(set(_INICIO_CC))

    # --- SP (R23) ---

    def sp(self) -> Nodo:
        """R23: SP → PREP SNS | PREP_DE SNS | CONTR_A NOMINAL | CONTR_DE NOMINAL.

        El SNS o el NOMINAL que sigue siempre se envuelve en un Nodo SN
        (sección Árboles sintácticos del documento).
        """
        tipo = self.actual().tipo
        if tipo == PREP:
            prep = self.consumir(PREP)
            return Nodo('SP', [prep, Nodo('SN', self.sns())])
        if tipo == PREP_DE:
            prep = self.consumir(PREP_DE)
            return Nodo('SP', [prep, Nodo('SN', self.sns())])
        if tipo == CONTR_A:
            contr = self.consumir(CONTR_A)
            return Nodo('SP', [contr, Nodo('SN', self.nominal())])
        if tipo == CONTR_DE:
            contr = self.consumir(CONTR_DE)
            return Nodo('SP', [contr, Nodo('SN', self.nominal())])
        self._error({PREP, PREP_DE, CONTR_A, CONTR_DE})

    # --- SADV (R24) ---

    def sadv(self) -> Nodo:
        """R24: SADV → ADV."""
        return Nodo('SADV', [self.consumir(ADV)])


# ---------------------------------------------------------------------------
# Función pública de alto nivel.
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    aceptada: bool
    etapa: str | None                   # "lexico" / "sintactico" / "semantico" / None
    mensajes: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)
    arbol: Nodo | None = None
    arbol_str: str | None = None


def analizar(oracion: str, semantico=None) -> Resultado:
    """Analiza una oración entera. Devuelve un Resultado con los campos del
    documento ('Formato del set de prueba y de la salida').

    - `semantico`: función opcional que recibe el árbol ya construido y
      devuelve una lista de mensajes de error. Si devuelve algo no vacío,
      la etapa pasa a 'semantico'. No se implementa aquí; es el punto de
      enganche para la Fase 3 (C1-C8).
    """
    tokens, errores_lex = tokenizar(oracion)
    categorias = [t.tipo for t in tokens if t.tipo != EOF]

    if errores_lex:
        mensajes = [str(e) for e in errores_lex]
        return Resultado(False, "lexico", mensajes, categorias, None, None)

    parser = Parser(tokens)
    try:
        arbol = parser.o()
    except ErrorSintactico as e:
        return Resultado(False, "sintactico", [str(e)], categorias, None, None)

    arbol_str = arbol.a_corchetes()

    if semantico is not None:
        # TODO Fase 3: enchufar aquí las reglas C1-C8.
        errores_sem = semantico(arbol)
        if errores_sem:
            mensajes = [str(e) for e in errores_sem]
            return Resultado(False, "semantico", mensajes,
                             categorias, arbol, arbol_str)

    return Resultado(True, None, [], categorias, arbol, arbol_str)


# ---------------------------------------------------------------------------
# Modo interactivo y modo lote por consola.
# ---------------------------------------------------------------------------

def _imprimir_tokens(categorias, oracion):
    """Imprime la tabla 'categoría | lexema' tras volver a tokenizar."""
    tokens, _ = tokenizar(oracion)
    print("Tokens:")
    for t in tokens:
        if t.tipo == EOF:
            continue
        print(f"  {t.tipo:<10} {t.lexema}")


def _cargar_semantico():
    """Carga perezosa del semántico, para que ``parser_es`` siga siendo
    importable aunque falte ``semantico_es`` (p. ej. en las pruebas).
    """
    from fase2.semantico_es import verificar  # noqa: WPS433
    return verificar


def _ejecutar_una(oracion, ruta_png=None, con_semantico=True):
    semantico = _cargar_semantico() if con_semantico else None
    resultado = analizar(oracion, semantico=semantico)
    _imprimir_tokens(resultado.categorias, oracion)

    if resultado.aceptada:
        print("\nAceptada.")
    else:
        print(f"\nRechazada (etapa: {resultado.etapa}):")
        for m in resultado.mensajes:
            print(f"  {m}")

    if resultado.arbol_str:
        print("\nÁrbol (corchetes):")
        print(resultado.arbol_str)
        try:
            arbol_nltk = resultado.arbol.a_nltk()
            print("\nÁrbol (nltk):")
            arbol_nltk.pretty_print()
        except Exception as exc:  # pragma: no cover - sólo para feedback
            print(f"(no se pudo dibujar con nltk: {exc})")

    if ruta_png and resultado.arbol is not None:
        from fase2.visualizar_arbol import dibujar_arbol
        dibujar_arbol(resultado.arbol, ruta_png)
        print(f"\nImagen del árbol guardada en: {ruta_png}")


def _ejecutar_lote(entrada: str, salida: str, con_semantico: bool = True):
    """Modo lote: lee un JSONL de oraciones y escribe un JSONL de salida.

    Con ``con_semantico=True`` (por defecto) añade a cada registro el
    campo ``regla`` con la lista de reglas semánticas que fallaron, o
    ``null`` si no hubo errores semánticos.
    """
    semantico = _cargar_semantico() if con_semantico else None
    with open(entrada, encoding='utf-8') as fe, \
         open(salida, 'w', encoding='utf-8') as fs:
        for linea in fe:
            linea = linea.strip()
            if not linea:
                continue
            datos = json.loads(linea)
            oracion = datos['oracion']
            resultado = analizar(oracion, semantico=semantico)
            # Recuperamos las reglas que fallaron. Si no se corrió el
            # semántico o la oración se rechazó antes, es ``None``.
            reglas = None
            if (semantico is not None and resultado.arbol is not None
                    and resultado.etapa == 'semantico'):
                errs = semantico(resultado.arbol)
                # Lista de reglas distintas en el orden de aparición.
                vistas: list[str] = []
                for e in errs:
                    if e.regla not in vistas:
                        vistas.append(e.regla)
                reglas = vistas
            registro = {
                'id': datos.get('id'),
                'aceptada': resultado.aceptada,
                'etapa': resultado.etapa,
                'mensajes': resultado.mensajes,
                'categorias': resultado.categorias,
                'arbol': resultado.arbol_str,
                'regla': reglas,
            }
            fs.write(json.dumps(registro, ensure_ascii=False) + '\n')


def _main(argv):
    parser = argparse.ArgumentParser(
        description="Analizador sintáctico del español — Fase 2",
    )
    parser.add_argument('oracion', nargs='?', help="Oración a analizar")
    parser.add_argument('--png', help="Guardar el árbol en PNG")
    parser.add_argument('--entrada', help="JSONL de oraciones (modo lote)")
    parser.add_argument('--salida',  help="JSONL de salida (modo lote)")
    parser.add_argument('--sin-semantico', action='store_true',
                        help="Desactiva el análisis semántico (C1-C8).")
    args = parser.parse_args(argv[1:])
    con_semantico = not args.sin_semantico

    if args.entrada and args.salida:
        _ejecutar_lote(args.entrada, args.salida, con_semantico=con_semantico)
        return 0

    if not args.oracion:
        parser.print_usage(sys.stderr)
        return 1

    _ejecutar_una(args.oracion, args.png, con_semantico=con_semantico)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
