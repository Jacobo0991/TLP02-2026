"""Validador del set de prueba de la Fase 2.

Revisa fase2/pruebas/oraciones.jsonl y termina con código de salida 1 si
detecta algún problema. Imprime todas las incidencias con el id de la
oración. No modifica archivos.

Comprobaciones:

1. 60 oraciones, ids únicos y reparto exacto por nivel y por 'esperado'.
2. Coherencia de campos (tipos, valores válidos, 'regla' solo con
   rechazo_semantico, 'fenomeno' solo en nivel 3, 'arbol' solo si aceptada).
3. Longitud de 'upos' igual al número de tokens que produce fase2.lexer_es
   (excluye EOF y los errores léxicos).
4. Cada 'arbol' se lee con nltk.Tree.fromstring y sus hojas son, en orden,
   los lexemas tokenizados de la oración.
5. Contraste con el parser (con el semántico activado):
   - rechazo_lexico      → el parser falla en etapa 'lexico'.
   - rechazo_sintactico  → falla en etapa 'sintactico'.
   - aceptada            → acepta y el árbol del parser es IDÉNTICO al esperado.
   - rechazo_semantico   → falla en etapa 'semantico' y la regla esperada
                           aparece entre las reglas que devuelve el
                           semántico.
6. Las diferencias entre el árbol esperado y el del parser NO se corrigen;
   se reportan al final para que el usuario decida.
7. Cobertura entre las aceptadas: lista los verbos, tiempos, personas y
   categorías del léxico que no aparezcan.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Permitimos ejecutar como script.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import nltk  # noqa: E402

from fase2.lexer_es import tokenizar, LEXICO, EOF, _MAESTRA  # noqa: E402
from fase2.parser_es import analizar  # noqa: E402
from fase2.semantico_es import verificar  # noqa: E402


def _unidades_lexer(texto: str) -> list[str]:
    """Devuelve los lexemas de todas las unidades que detecta el motor del
    lexer (PALABRA, COMA, PUNTO y CHAR_INVALIDO), omitiendo los ESPACIOs.

    Es la lista con la que debe coincidir 'upos': incluye también los
    lexemas que luego el lexer marca como errores léxicos (palabras fuera
    del vocabulario y caracteres inválidos), para poder comparar etiqueta
    por etiqueta contra spaCy/HuggingFace.
    """
    unidades: list[str] = []
    for m in _MAESTRA.finditer(texto):
        if m.lastgroup == "ESPACIO":
            continue
        unidades.append(m.group())
    return unidades


RUTA_JSONL = Path(__file__).resolve().parent / "pruebas" / "oraciones.jsonl"

# Valores válidos para los enumerados del set.
ESPERADOS = {"aceptada", "rechazo_lexico", "rechazo_sintactico",
             "rechazo_semantico"}
REGLAS = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"}
CATEGORIAS = {"DET", "SUST", "NPROP", "PRON", "ADJ", "INTENS", "VERBO",
              "COP", "NEG", "ADV", "PREP", "PREP_DE", "CONTR_A",
              "CONTR_DE", "CONJ", "COMA", "PUNTO"}

# 16 verbos regulares + ser + estar; se controla con 'lema'.
VERBOS_LEMA = {
    "comprar", "mirar", "lavar", "abrir",
    "comer", "beber", "aprender", "escribir", "cocinar", "pintar",
    "correr", "caminar", "vivir", "saltar", "trabajar", "nadar",
}
COP_LEMA = {"ser", "estar"}
TIEMPOS = {"pres", "pret", "fut"}
PERSONAS = {(1, "sg"), (2, "sg"), (3, "sg"), (1, "pl"), (3, "pl")}

# Expresión para normalizar espacios al comparar árboles.
_RE_ESPACIOS = re.compile(r"\s+")


def _norm(cadena: str) -> str:
    return _RE_ESPACIOS.sub(" ", cadena).strip()


def _cargar():
    """Lee el JSONL y devuelve la lista de registros (dict)."""
    registros = []
    with open(RUTA_JSONL, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            registros.append(json.loads(linea))
    return registros


def _hojas_de_arbol(arbol_str: str) -> list[str]:
    """Devuelve los lexemas (hojas) de un árbol en notación con corchetes.

    Las hojas son los `(CATEGORIA lexema)` del árbol. Como nltk.Tree.fromstring
    puede confundirse con lexemas no alfanuméricos, extraemos directamente
    con una expresión regular sobre el texto normalizado.
    """
    # Captura el último token dentro de cada paréntesis innermost,
    # usando el árbol como nltk.Tree para mayor fiabilidad.
    arbol = nltk.Tree.fromstring(arbol_str)
    return arbol.leaves()


def _tokens_de(oracion: str):
    """Tokens exitosos (sin EOF) que produce el lexer y sus errores."""
    tokens, errores = tokenizar(oracion)
    tokens = [t for t in tokens if t.tipo != EOF]
    return tokens, errores


def validar() -> int:
    registros = _cargar()
    errores: list[str] = []          # Problemas que marcan el set como inválido.
    avisos: list[str] = []           # Observaciones que no bloquean (cobertura).
    diffs_arbol: list[tuple[str, str, str]] = []   # (id, esperado, parser)

    # ----- 1. Conteo y reparto por nivel/esperado -----------------------

    if len(registros) != 60:
        errores.append(
            f"[conjunto] Se esperaban 60 oraciones; hay {len(registros)}."
        )

    ids = [r.get("id") for r in registros]
    duplicados = [x for x, c in Counter(ids).items() if c > 1]
    if duplicados:
        errores.append(f"[conjunto] IDs duplicados: {duplicados}")

    # Reparto esperado por nivel.
    reparto_nivel = Counter(r.get("nivel") for r in registros)
    for nivel in (1, 2, 3):
        if reparto_nivel.get(nivel, 0) != 20:
            errores.append(
                f"[conjunto] Nivel {nivel}: se esperaban 20, "
                f"hay {reparto_nivel.get(nivel, 0)}."
            )

    # Reparto por esperado dentro de cada nivel:
    #   Nivel 1: 15 aceptada + 5 rechazo_semantico.
    #   Nivel 2: 15 aceptada + 5 rechazo_semantico.
    #   Nivel 3: la tabla del documento.
    reparto_esperado = defaultdict(Counter)
    for r in registros:
        reparto_esperado[r.get("nivel")][r.get("esperado")] += 1

    if reparto_esperado[1].get("aceptada", 0) != 15:
        errores.append(
            f"[nivel 1] se esperaban 15 aceptadas; "
            f"hay {reparto_esperado[1].get('aceptada', 0)}."
        )
    if reparto_esperado[1].get("rechazo_semantico", 0) != 5:
        errores.append(
            f"[nivel 1] se esperaban 5 rechazo_semantico; "
            f"hay {reparto_esperado[1].get('rechazo_semantico', 0)}."
        )
    if reparto_esperado[2].get("aceptada", 0) != 15:
        errores.append(
            f"[nivel 2] se esperaban 15 aceptadas; "
            f"hay {reparto_esperado[2].get('aceptada', 0)}."
        )
    if reparto_esperado[2].get("rechazo_semantico", 0) != 5:
        errores.append(
            f"[nivel 2] se esperaban 5 rechazo_semantico; "
            f"hay {reparto_esperado[2].get('rechazo_semantico', 0)}."
        )
    # Nivel 1 y 2 solo deberían tener esos dos tipos:
    for nivel in (1, 2):
        for etiq, cnt in reparto_esperado[nivel].items():
            if etiq not in ("aceptada", "rechazo_semantico"):
                errores.append(
                    f"[nivel {nivel}] etiqueta 'esperado'={etiq!r} "
                    f"({cnt} ocurrencias) no está permitida en este nivel."
                )
    # Nivel 1 y 2: C1-C4 vs C2+C5-C8 según el documento.
    regs_rech_n1 = [r for r in registros
                    if r.get("nivel") == 1
                    and r.get("esperado") == "rechazo_semantico"]
    reglas_n1 = Counter(r.get("regla") for r in regs_rech_n1)
    for req in ("C1", "C3", "C4"):
        if reglas_n1.get(req, 0) == 0:
            errores.append(
                f"[nivel 1] falta al menos un rechazo con regla {req}."
            )
    for r in regs_rech_n1:
        if r.get("regla") not in {"C1", "C3", "C4"}:
            errores.append(
                f"[{r.get('id')}] regla {r.get('regla')} fuera de "
                f"{{C1,C3,C4}} para nivel 1."
            )

    regs_rech_n2 = [r for r in registros
                    if r.get("nivel") == 2
                    and r.get("esperado") == "rechazo_semantico"]
    reglas_n2 = set(r.get("regla") for r in regs_rech_n2)
    for req in ("C2", "C5", "C6", "C7", "C8"):
        if req not in reglas_n2:
            errores.append(
                f"[nivel 2] falta un rechazo con regla {req}."
            )
    for r in regs_rech_n2:
        if r.get("regla") not in {"C2", "C5", "C6", "C7", "C8"}:
            errores.append(
                f"[{r.get('id')}] regla {r.get('regla')} fuera de "
                f"{{C2,C5-C8}} para nivel 2."
            )

    # ----- 2. Coherencia de campos ---------------------------------------

    for r in registros:
        rid = r.get("id") or "<sin id>"
        if not isinstance(r.get("gramatical"), bool):
            errores.append(f"[{rid}] 'gramatical' debe ser booleano.")
        if r.get("esperado") not in ESPERADOS:
            errores.append(
                f"[{rid}] 'esperado'={r.get('esperado')!r} no válido."
            )
        # regla ↔ rechazo_semantico.
        if r.get("esperado") == "rechazo_semantico":
            if r.get("regla") not in REGLAS:
                errores.append(
                    f"[{rid}] se esperaba 'regla' en {sorted(REGLAS)}; "
                    f"hay {r.get('regla')!r}."
                )
        else:
            if r.get("regla") is not None:
                errores.append(
                    f"[{rid}] 'regla' solo se usa en rechazo_semantico "
                    f"(aquí 'esperado'={r.get('esperado')!r})."
                )
        # fenomeno ↔ nivel 3.
        if r.get("nivel") == 3:
            if not r.get("fenomeno"):
                errores.append(f"[{rid}] falta 'fenomeno' (nivel 3).")
        else:
            if r.get("fenomeno") is not None:
                errores.append(
                    f"[{rid}] 'fenomeno' solo se usa en nivel 3."
                )
        # arbol ↔ aceptada.
        if r.get("esperado") == "aceptada":
            if not r.get("arbol"):
                errores.append(f"[{rid}] falta 'arbol' en oración aceptada.")
        else:
            if r.get("arbol") is not None:
                errores.append(
                    f"[{rid}] 'arbol' solo se usa en oraciones aceptadas."
                )
        # upos debe ser lista.
        if not isinstance(r.get("upos"), list) or not all(
                isinstance(x, str) for x in r.get("upos", [])):
            errores.append(f"[{rid}] 'upos' debe ser una lista de strings.")

    # ----- 3. UPOS vs tokens del lexer -----------------------------------
    # ----- 4. Árbol: nltk + hojas == lexemas -----------------------------

    for r in registros:
        rid = r.get("id")
        oracion = r.get("oracion", "")
        tokens, _errs = _tokens_de(oracion)
        lexemas_tokens = [t.lexema for t in tokens]   # Solo éxitos del lexer.
        unidades = _unidades_lexer(oracion)           # Éxitos y errores juntos.

        upos = r.get("upos") or []
        if len(upos) != len(unidades):
            errores.append(
                f"[{rid}] |upos|={len(upos)} ≠ |unidades lexer|="
                f"{len(unidades)} (unidades: {unidades})."
            )

        if r.get("arbol"):
            try:
                hojas = _hojas_de_arbol(r["arbol"])
            except Exception as exc:  # pragma: no cover - ayuda al diagnóstico
                errores.append(
                    f"[{rid}] el árbol no se puede leer con "
                    f"nltk.Tree.fromstring: {exc}"
                )
                continue
            # El árbol solo lo construye el parser sobre oraciones aceptadas,
            # que no tienen errores léxicos: hojas == lexemas de los tokens.
            if hojas != lexemas_tokens:
                errores.append(
                    f"[{rid}] las hojas del árbol {hojas} no coinciden con "
                    f"los lexemas de la oración {lexemas_tokens}."
                )

    # ----- 5. Contraste con el parser ------------------------------------

    for r in registros:
        rid = r.get("id")
        oracion = r.get("oracion", "")
        esperado = r.get("esperado")
        resultado = analizar(oracion, semantico=verificar)

        if esperado == "rechazo_lexico":
            if resultado.etapa != "lexico":
                errores.append(
                    f"[{rid}] se esperaba rechazo_lexico, "
                    f"parser dice etapa={resultado.etapa!r}, "
                    f"aceptada={resultado.aceptada}."
                )
        elif esperado == "rechazo_sintactico":
            if resultado.etapa != "sintactico":
                errores.append(
                    f"[{rid}] se esperaba rechazo_sintactico, "
                    f"parser dice etapa={resultado.etapa!r}, "
                    f"aceptada={resultado.aceptada}."
                )
        elif esperado == "aceptada":
            if not resultado.aceptada:
                errores.append(
                    f"[{rid}] se esperaba aceptada, "
                    f"parser dice etapa={resultado.etapa!r}: "
                    f"{resultado.mensajes}"
                )
            else:
                # Árbol del parser vs esperado (cadenas normalizadas).
                esp = _norm(r.get("arbol") or "")
                obt = _norm(resultado.arbol_str or "")
                if esp != obt:
                    diffs_arbol.append((rid, esp, obt))
        elif esperado == "rechazo_semantico":
            # Debe rechazarse en el semántico y la regla esperada debe
            # estar entre las que el semántico detectó.
            if resultado.etapa != "semantico":
                errores.append(
                    f"[{rid}] se esperaba rechazo_semantico, pero el parser "
                    f"dice etapa={resultado.etapa!r} "
                    f"(aceptada={resultado.aceptada}): {resultado.mensajes}"
                )
            else:
                reglas_detectadas = sorted({
                    e.regla for e in verificar(resultado.arbol)
                })
                esperado_regla = r.get("regla")
                if esperado_regla not in reglas_detectadas:
                    errores.append(
                        f"[{rid}] se esperaba la regla {esperado_regla!r}, "
                        f"el semántico detectó {reglas_detectadas}: "
                        f"{resultado.mensajes}"
                    )

    # ----- 7. Cobertura entre aceptadas ----------------------------------

    aceptadas = [r for r in registros if r.get("esperado") == "aceptada"]

    cat_vistas = set()
    verbos_vistos = set()
    cop_vistos = set()
    tiempos_vistos = set()
    personas_vistas = set()

    for r in aceptadas:
        tokens, _ = _tokens_de(r.get("oracion", ""))
        for t in tokens:
            cat_vistas.add(t.tipo)
            if t.tipo == "VERBO":
                lema = (t.valor or {}).get("lema")
                if lema:
                    verbos_vistos.add(lema)
                tiempo = (t.valor or {}).get("tiempo")
                if isinstance(tiempo, list):
                    tiempos_vistos.update(tiempo)
                elif isinstance(tiempo, str):
                    tiempos_vistos.add(tiempo)
                persona = (t.valor or {}).get("persona")
                numero = (t.valor or {}).get("numero")
                if persona is not None and numero is not None:
                    personas_vistas.add((persona, numero))
            elif t.tipo == "COP":
                lema = (t.valor or {}).get("lema")
                if lema:
                    cop_vistos.add(lema)
                tiempo = (t.valor or {}).get("tiempo")
                if tiempo:
                    tiempos_vistos.add(tiempo)
                persona = (t.valor or {}).get("persona")
                numero = (t.valor or {}).get("numero")
                if persona is not None and numero is not None:
                    personas_vistas.add((persona, numero))
            elif t.tipo == "PRON":
                persona = (t.valor or {}).get("persona")
                numero = (t.valor or {}).get("numero")
                if persona is not None and numero is not None:
                    personas_vistas.add((persona, numero))

    verbos_faltan = sorted(VERBOS_LEMA - verbos_vistos)
    cop_faltan = sorted(COP_LEMA - cop_vistos)
    tiempos_faltan = sorted(TIEMPOS - tiempos_vistos)
    personas_faltan = sorted(PERSONAS - personas_vistas)
    cat_faltan = sorted(CATEGORIAS - cat_vistas)

    # Conteo de tiempos para la cota "al menos 8 veces cada uno".
    conteo_tiempos = Counter()
    for r in aceptadas:
        tokens, _ = _tokens_de(r.get("oracion", ""))
        for t in tokens:
            if t.tipo in ("VERBO", "COP"):
                tiempo = (t.valor or {}).get("tiempo")
                if isinstance(tiempo, list):
                    # 'caminamos' lleva tiempo=[pres, pret]; sumamos uno
                    # a cada tiempo al que la forma puede referir.
                    for ti in tiempo:
                        conteo_tiempos[ti] += 1
                elif isinstance(tiempo, str):
                    conteo_tiempos[tiempo] += 1

    if verbos_faltan:
        avisos.append(f"[cobertura] verbos sin aparecer en aceptadas: "
                      f"{verbos_faltan}")
    if cop_faltan:
        avisos.append(f"[cobertura] cópulas sin aparecer: {cop_faltan}")
    if tiempos_faltan:
        avisos.append(f"[cobertura] tiempos sin aparecer: {tiempos_faltan}")
    if personas_faltan:
        avisos.append(f"[cobertura] personas sin aparecer: {personas_faltan}")
    if cat_faltan:
        avisos.append(f"[cobertura] categorías del léxico sin aparecer: "
                      f"{cat_faltan}")
    for t in sorted(TIEMPOS):
        if conteo_tiempos.get(t, 0) < 8:
            avisos.append(
                f"[cobertura] tiempo {t}: {conteo_tiempos.get(t, 0)} "
                f"apariciones, se pidieron ≥ 8."
            )

    # Nivel 3: al menos 10 oraciones sin palabras nuevas (lex OK).
    n3_sin_nuevas = 0
    for r in registros:
        if r.get("nivel") != 3:
            continue
        _toks, errs = _tokens_de(r.get("oracion", ""))
        if not errs:
            n3_sin_nuevas += 1
    if n3_sin_nuevas < 10:
        errores.append(
            f"[nivel 3] se esperaban ≥10 oraciones sin palabras nuevas; "
            f"hay {n3_sin_nuevas}."
        )

    # Nivel 2: exactamente una aceptada sin punto final.
    n2_sin_punto = [r for r in registros
                    if r.get("nivel") == 2
                    and r.get("esperado") == "aceptada"
                    and not r.get("oracion", "").rstrip().endswith(".")]
    if len(n2_sin_punto) != 1:
        errores.append(
            f"[nivel 2] se esperaba exactamente 1 aceptada sin punto final; "
            f"hay {len(n2_sin_punto)}: {[r['id'] for r in n2_sin_punto]}."
        )

    # ----- Salida --------------------------------------------------------

    print(f"Set: {RUTA_JSONL}")
    print(f"Total de oraciones: {len(registros)}\n")

    print("REPARTO POR NIVEL Y 'esperado':")
    for nivel in (1, 2, 3):
        for et in ("aceptada", "rechazo_lexico",
                   "rechazo_sintactico", "rechazo_semantico"):
            cnt = reparto_esperado[nivel].get(et, 0)
            if cnt:
                print(f"  Nivel {nivel} / {et}: {cnt}")
    print()

    print("COBERTURA EN LAS ACEPTADAS:")
    print(f"  Verbos vistos ({len(verbos_vistos)}): "
          f"{sorted(verbos_vistos)}")
    print(f"  Cópulas vistas: {sorted(cop_vistos)}")
    print(f"  Tiempos vistos: {sorted(tiempos_vistos)}")
    print(f"  Conteo de tiempos: {dict(conteo_tiempos)}")
    print(f"  Personas vistas: {sorted(personas_vistas)}")
    print(f"  Categorías vistas ({len(cat_vistas)}): {sorted(cat_vistas)}")
    print()

    if avisos:
        print("AVISOS (no bloquean):")
        for a in avisos:
            print(f"  {a}")
        print()

    if diffs_arbol:
        print("DIFERENCIAS ENTRE ÁRBOL ESPERADO Y EL DEL PARSER:")
        for rid, esp, obt in diffs_arbol:
            print(f"  [{rid}]")
            print(f"    esperado: {esp}")
            print(f"    parser:   {obt}")
        print()
    else:
        print("Árboles esperados == árboles del parser para todas las "
              "aceptadas.\n")

    if errores:
        print("ERRORES:")
        for e in errores:
            print(f"  {e}")
        print(f"\nValidación: FALLÓ ({len(errores)} errores).")
        return 1

    print("Validación: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(validar())
