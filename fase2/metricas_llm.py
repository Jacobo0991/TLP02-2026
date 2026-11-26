"""Métricas del experimento con el LLM.

Lee:
  - fase2/pruebas/oraciones.jsonl               (set anotado)
  - fase2/resultados/llm_zero_shot.jsonl        (decisión por mayoría)
  - fase2/resultados/llm_few_shot.jsonl
  - fase2/logs/llm/zero_shot.jsonl              (todas las llamadas crudas)
  - fase2/logs/llm/few_shot.jsonl

Produce:
  - fase2/resultados/metricas_llm.md
  - fase2/resultados/metricas_llm.csv
  - fase2/resultados/errores_llm.md
  - fase2/resultados/graficas/llm_*.png

Métricas por condición (zero_shot vs few_shot), por nivel y en total:
  * Precisión, cobertura, tasa de rechazo correcto, VP/FP/FN/VN, error de
    etiquetado (árbol o UPOS del árbol distintos del esperado).
  * Exactitud UPOS por oración (con las categorías que entrega el LLM).
  * UAS / LAS de los árboles aceptados (vía ``ud.py``).
  * Coincidencia exacta del árbol.
  * Desviación hacia el español general: % de aceptación entre las
    oraciones gramaticales que el parser debe rechazar.
  * Respeto de R12 en las oraciones con "de" o "del" tras un sustantivo.
  * Motivos de rechazo: coincidencia de etapa y de regla citada.
  * Formato: % de respuestas inválidas.
  * Consistencia: % de oraciones donde las 3 repeticiones dan la misma
    decisión (par ``aceptada, etapa``).
  * Costo: tokens totales, costo total y latencia promedio por condición.
  * Zero-shot vs few-shot: McNemar sobre correctos/incorrectos por oración.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.ud import arbol_a_dependencias, CAT_A_UPOS  # noqa: E402

RUTA_SET = _RAIZ / 'fase2' / 'pruebas' / 'oraciones.jsonl'
RUTA_RES = _RAIZ / 'fase2' / 'resultados'
RUTA_LOG = _RAIZ / 'fase2' / 'logs' / 'llm'
RUTA_GRAF = RUTA_RES / 'graficas'

CONDICIONES = ('zero_shot', 'few_shot')

CATEGORIAS_VALIDAS = frozenset(CAT_A_UPOS.keys())
REGLAS_VALIDAS = frozenset(
    {f'R{i}' for i in range(1, 25)} | {f'C{i}' for i in range(1, 9)}
)
RE_REGLA = re.compile(r'\b([RC]\d{1,2})\b')


# ---------------------------------------------------------------------------
# Utilidades.
# ---------------------------------------------------------------------------

def _leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    out = []
    with ruta.open(encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            out.append(json.loads(linea))
    return out


def _leer_jsonl_por_id(ruta: Path) -> dict:
    return {r['id']: r for r in _leer_jsonl(ruta)}


def _norm_arbol(a: str | None) -> str | None:
    if a is None:
        return None
    return re.sub(r'\s+', ' ', a).strip()


def _fmt_pct(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return '—'
    return f'{100*x:.1f}%'


def _safe_div(a, b):
    return a / b if b else float('nan')


# ---------------------------------------------------------------------------
# Métricas de aceptación (precisión, cobertura, rechazo correcto).
# ---------------------------------------------------------------------------

def _clasificar(set_dict: dict, sal_dict: dict) -> dict:
    """VP/FP/FN/VN + error de etiquetado + detalle por oración.

    El error de etiquetado (``bien aceptada, pero árbol distinto``) se mide
    comparando el árbol normalizado contra el esperado del set.
    """
    vp = fp = fn = vn = 0
    err_etq = 0
    detalle = []
    for id_, orig in set_dict.items():
        sal = sal_dict.get(id_)
        if not sal:
            continue
        esp = orig['esperado']
        aceptada = bool(sal.get('aceptada'))
        if esp == 'aceptada':
            if aceptada:
                bien = True
                if orig.get('arbol') and sal.get('arbol'):
                    if _norm_arbol(orig['arbol']) != _norm_arbol(sal['arbol']):
                        bien = False
                vp += 1
                if not bien:
                    err_etq += 1
                    detalle.append((id_, 'etiquetado', orig['oracion']))
            else:
                fn += 1
                detalle.append((id_, 'FN', orig['oracion']))
        else:
            if aceptada:
                fp += 1
                detalle.append((id_, 'FP', orig['oracion']))
            else:
                vn += 1
    return {
        'VP': vp, 'FP': fp, 'FN': fn, 'VN': vn,
        'errores_etiquetado': err_etq,
        'detalle': detalle,
    }


def _pcr(c: dict) -> tuple[float, float, float]:
    p = _safe_div(c['VP'], c['VP'] + c['FP'])
    co = _safe_div(c['VP'], c['VP'] + c['FN'])
    r = _safe_div(c['VN'], c['VN'] + c['FP'])
    return p, co, r


# ---------------------------------------------------------------------------
# UPOS / UAS / LAS a partir del árbol del LLM.
# ---------------------------------------------------------------------------

def _upos_de_sal(sal: dict) -> list[str]:
    """Convierte ``categorias`` del LLM a UPOS vía ``CAT_A_UPOS``.
    Una categoría fuera del inventario produce ``'X'`` para no romper la
    comparación, y se contará igual como error."""
    return [CAT_A_UPOS.get(c, 'X') for c in sal.get('categorias', [])]


def _exactitud_upos(esp: list[str], obt: list[str]) -> tuple[int, int]:
    total = max(len(esp), len(obt))
    aciertos = sum(1 for a, b in zip(esp, obt) if a == b)
    return aciertos, total


def _uas_las(esp_cab, esp_rel, obt_cab, obt_rel):
    total = min(len(esp_cab), len(obt_cab))
    uas = sum(1 for k in range(total) if esp_cab[k] == obt_cab[k])
    las = sum(1 for k in range(total)
              if esp_cab[k] == obt_cab[k] and esp_rel[k] == obt_rel[k])
    return uas, las, total


# ---------------------------------------------------------------------------
# Desviaciones específicas.
# ---------------------------------------------------------------------------

def _desviacion_espanol_general(set_dict: dict, sal_dict: dict) -> dict:
    """De las oraciones gramaticales que el parser debe rechazar, cuántas
    aceptó el LLM. Son las que miden si el LLM usa la gramática o su
    conocimiento del español."""
    casos = []
    aceptadas = 0
    por_fenomeno = Counter()
    for id_, orig in set_dict.items():
        if not orig['gramatical'] or orig['esperado'] == 'aceptada':
            continue
        sal = sal_dict.get(id_)
        if not sal:
            continue
        acep = bool(sal.get('aceptada'))
        casos.append((id_, orig['oracion'], orig.get('fenomeno'), acep))
        if acep:
            aceptadas += 1
            por_fenomeno[orig.get('fenomeno') or '—'] += 1
    return {
        'total': len(casos),
        'aceptadas': aceptadas,
        'porcentaje': _safe_div(aceptadas, len(casos)),
        'por_fenomeno': por_fenomeno,
        'casos': casos,
    }


def _une_de_al_sustantivo(arbol: str) -> bool | None:
    """Mira si en el árbol del LLM hay un ``SP`` cuyo primer token sea
    ``PREP_DE`` o ``CONTR_DE`` dentro de un SN, no como hijo directo de SV
    (donde iría unido al verbo).

    Devuelve True si la regla R12 parece aplicada (el "de" se unió al
    sustantivo), False si se unió al verbo, None si no puede decidirse.
    """
    try:
        import nltk
        t = nltk.Tree.fromstring(arbol)
    except Exception:
        return None

    def _tiene_de(sub):
        if not isinstance(sub, nltk.Tree):
            return False
        if sub.label() == 'SP' and len(sub) >= 1:
            primer = sub[0]
            if isinstance(primer, nltk.Tree) and primer.label() in ('PREP_DE', 'CONTR_DE'):
                return True
        return False

    def _buscar(sub, padre_label):
        if not isinstance(sub, nltk.Tree):
            return None
        if _tiene_de(sub):
            return padre_label
        for hijo in sub:
            r = _buscar(hijo, sub.label() if isinstance(sub, nltk.Tree) else padre_label)
            if r is not None:
                return r
        return None

    resultado = _buscar(t, t.label())
    if resultado is None:
        return None
    # SN (o hijo directo de SUJ/OD que sea SN) → unido al sustantivo.
    return resultado == 'SN'


def _respeto_r12(set_dict: dict, sal_dict: dict) -> dict:
    """De las oraciones con ``de`` / ``del`` tras un sustantivo (según el
    oráculo del set), cuántas une el LLM al sustantivo."""
    total = 0
    r12_ok = 0
    indecisos = 0
    detalle = []
    for id_, orig in set_dict.items():
        arbol_esp = orig.get('arbol')
        if not arbol_esp:
            continue
        # El set une "de" al sustantivo si en el árbol aparece un
        # (SP (PREP_DE ...)) o (SP (CONTR_DE ...)) dentro de un SN. Como
        # el set ya sigue R12, lo detectamos con el mismo método.
        if _une_de_al_sustantivo(arbol_esp) is not True:
            continue
        sal = sal_dict.get(id_)
        if not sal or not sal.get('arbol'):
            continue
        total += 1
        une = _une_de_al_sustantivo(sal['arbol'])
        if une is None:
            indecisos += 1
            detalle.append((id_, orig['oracion'], 'indeciso'))
        elif une:
            r12_ok += 1
        else:
            detalle.append((id_, orig['oracion'], 'unido_al_verbo'))
    return {
        'total': total,
        'ok': r12_ok,
        'indecisos': indecisos,
        'porcentaje': _safe_div(r12_ok, total),
        'detalle': detalle,
    }


def _motivos_rechazo(set_dict: dict, sal_dict: dict) -> dict:
    """En los rechazos correctos (VN), mira si la etapa y la regla citada
    coinciden con lo esperado. También cuenta las reglas inventadas."""
    casos_etapa_ok = 0
    casos_regla_ok = 0
    casos = 0
    reglas_inventadas = Counter()
    detalle = []
    for id_, orig in set_dict.items():
        if orig['esperado'] == 'aceptada':
            continue
        sal = sal_dict.get(id_)
        if not sal:
            continue
        if sal.get('aceptada'):
            continue  # No rechazó: no entra aquí.
        casos += 1
        esperada_etapa = orig['esperado'].replace('rechazo_', '')
        if sal.get('etapa') == esperada_etapa:
            casos_etapa_ok += 1
        # Regla citada: busca R.. o C.. en los mensajes.
        mensajes = ' '.join(sal.get('mensajes') or [])
        reglas_citadas = set(RE_REGLA.findall(mensajes))
        regla_esperada = orig.get('regla')
        regla_hit = (regla_esperada is not None
                     and regla_esperada in reglas_citadas)
        if regla_hit:
            casos_regla_ok += 1
        for r in reglas_citadas:
            if r not in REGLAS_VALIDAS:
                reglas_inventadas[r] += 1
        if sal.get('etapa') != esperada_etapa or (regla_esperada and not regla_hit):
            detalle.append({
                'id': id_,
                'oracion': orig['oracion'],
                'etapa_esperada': esperada_etapa,
                'etapa_obtenida': sal.get('etapa'),
                'regla_esperada': regla_esperada,
                'reglas_citadas': sorted(reglas_citadas),
            })
    return {
        'casos': casos,
        'etapa_ok': casos_etapa_ok,
        'regla_ok': casos_regla_ok,
        'pct_etapa': _safe_div(casos_etapa_ok, casos),
        'pct_regla': _safe_div(casos_regla_ok, casos),
        'reglas_inventadas': reglas_inventadas,
        'detalle': detalle,
    }


def _formato_invalido(sal_dict: dict) -> dict:
    total = len(sal_dict)
    invalidas = sum(1 for s in sal_dict.values()
                    if s.get('respuesta_invalida'))
    return {
        'total': total,
        'invalidas': invalidas,
        'porcentaje': _safe_div(invalidas, total),
    }


def _consistencia(sal_dict: dict) -> dict:
    """% de oraciones en las que las 3 repeticiones dan la misma decisión."""
    total = 0
    consistentes = 0
    detalle = []
    for id_, sal in sal_dict.items():
        reps = sal.get('repeticiones') or []
        if not reps:
            continue
        total += 1
        claves = []
        for r in reps:
            if r.get('respuesta_invalida'):
                claves.append(('inv', None))
            else:
                claves.append((bool(r.get('aceptada')), r.get('etapa')))
        if len(set(claves)) == 1:
            consistentes += 1
        else:
            detalle.append((id_, claves))
    return {
        'total': total,
        'consistentes': consistentes,
        'porcentaje': _safe_div(consistentes, total),
        'detalle': detalle,
    }


# ---------------------------------------------------------------------------
# Costo (sobre el log crudo).
# ---------------------------------------------------------------------------

def _costo_desde_log(log: list[dict]) -> dict:
    tokens_in = sum(r['tokens_entrada'] for r in log)
    tokens_out = sum(r['tokens_salida'] for r in log)
    costo = sum(r['costo_usd'] for r in log)
    lat = [r['latencia_s'] for r in log]
    return {
        'llamadas': len(log),
        'tokens_in': tokens_in,
        'tokens_out': tokens_out,
        'costo_usd': costo,
        'latencia_prom_s': (sum(lat) / len(lat)) if lat else 0.0,
    }


# ---------------------------------------------------------------------------
# UPOS y UAS/LAS agregados por condición.
# ---------------------------------------------------------------------------

def _agregar_upos_uas(set_dict: dict, sal_dict: dict) -> dict:
    """Devuelve {'upos': {'nivel': {aciertos, total}}, 'uaslas': ...}.

    UPOS cuenta sobre todas las oraciones donde el LLM entregó una lista de
    categorías de la misma longitud que la esperada. Si difiere, se cuenta
    hasta el mínimo y el resto como errores.

    UAS/LAS se calcula sobre las oraciones con árbol esperado donde el LLM
    produjo un árbol parseable con ``ud.py`` y con la misma cantidad de
    tokens que el oráculo.
    """
    niveles = (1, 2, 3)
    upos = {n: {'aciertos': 0, 'total': 0, 'n': 0} for n in niveles}
    uas_las = {n: {'uas': 0, 'las': 0, 'total': 0, 'n': 0, 'saltadas': 0}
               for n in niveles}
    for id_, orig in set_dict.items():
        sal = sal_dict.get(id_)
        if not sal:
            continue
        nivel = orig['nivel']
        esp_upos = orig['upos']
        obt_upos = _upos_de_sal(sal)
        a, t = _exactitud_upos(esp_upos, obt_upos)
        upos[nivel]['aciertos'] += a
        upos[nivel]['total'] += t
        upos[nivel]['n'] += 1
        # UAS/LAS solo si hay árbol esperado y árbol del LLM.
        if not orig.get('arbol') or orig['esperado'] != 'aceptada':
            continue
        if not sal.get('arbol'):
            uas_las[nivel]['saltadas'] += 1
            continue
        try:
            dep_esp = arbol_a_dependencias(orig['arbol'])
            dep_obt = arbol_a_dependencias(sal['arbol'])
        except Exception:
            uas_las[nivel]['saltadas'] += 1
            continue
        if len(dep_esp['cabezas']) != len(dep_obt['cabezas']):
            uas_las[nivel]['saltadas'] += 1
            continue
        u, l, t2 = _uas_las(dep_esp['cabezas'], dep_esp['relaciones'],
                            dep_obt['cabezas'], dep_obt['relaciones'])
        uas_las[nivel]['uas'] += u
        uas_las[nivel]['las'] += l
        uas_las[nivel]['total'] += t2
        uas_las[nivel]['n'] += 1

    def _tot(d, claves):
        return {k: sum(d[n][k] for n in niveles) for k in claves}
    upos['total'] = _tot(upos, ('aciertos', 'total', 'n'))
    uas_las['total'] = _tot(uas_las, ('uas', 'las', 'total', 'n', 'saltadas'))
    return {'upos': upos, 'uaslas': uas_las}


# ---------------------------------------------------------------------------
# Coincidencia exacta del árbol.
# ---------------------------------------------------------------------------

def _arbol_exacto(set_dict: dict, sal_dict: dict) -> dict:
    por_nivel = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
    for id_, orig in set_dict.items():
        if not orig.get('arbol'):
            continue
        sal = sal_dict.get(id_)
        if not sal or not sal.get('arbol'):
            por_nivel[orig['nivel']][1] += 1
            continue
        ok = _norm_arbol(orig['arbol']) == _norm_arbol(sal['arbol'])
        por_nivel[orig['nivel']][0] += int(ok)
        por_nivel[orig['nivel']][1] += 1
    tot = sum(v[0] for v in por_nivel.values()), sum(v[1] for v in por_nivel.values())
    return {
        **{n: {'ok': v[0], 'total': v[1],
               'pct': _safe_div(v[0], v[1])} for n, v in por_nivel.items()},
        'total': {'ok': tot[0], 'total': tot[1], 'pct': _safe_div(tot[0], tot[1])},
    }


# ---------------------------------------------------------------------------
# McNemar.
# ---------------------------------------------------------------------------

def _es_correcto(orig: dict, sal: dict | None) -> bool:
    """Una oración se considera correctamente clasificada si el LLM acertó
    la aceptación esperada (ignoramos el árbol para McNemar: aquí queremos
    comparar decisiones, no etiquetado)."""
    if not sal:
        return False
    deberia = (orig['esperado'] == 'aceptada')
    return bool(sal.get('aceptada')) == deberia


def _mcnemar(b: int, c: int) -> dict:
    """b: éxitos solo en A (zero), no en B (few).
       c: éxitos solo en B (few), no en A (zero).

    Si b + c < 25 se usa la versión exacta binomial (dos colas) con p=0.5;
    si no, el estadístico de McNemar con corrección de continuidad y la
    chi-cuadrado con 1 grado de libertad.
    """
    n = b + c
    if n == 0:
        return {'b': 0, 'c': 0, 'estadistico': 0.0, 'p': 1.0, 'metodo': 'trivial'}
    if n < 25:
        # Versión exacta binomial de dos colas.
        k = min(b, c)
        # P(X <= k) con X ~ Binomial(n, 0.5), por los dos extremos.
        p_una = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
        p = min(1.0, 2 * p_una)
        return {'b': b, 'c': c, 'estadistico': float(k), 'p': p,
                'metodo': 'exacta_binomial'}
    # Chi-cuadrado con corrección de continuidad.
    chi = (abs(b - c) - 1) ** 2 / (b + c)
    # Supervivencia de chi-cuadrado(1 gl) = erfc(sqrt(chi/2)).
    p = math.erfc(math.sqrt(chi / 2))
    return {'b': b, 'c': c, 'estadistico': chi, 'p': p,
            'metodo': 'chi2_cc'}


# ---------------------------------------------------------------------------
# Cálculo principal.
# ---------------------------------------------------------------------------

def _por_nivel(set_dict: dict, sal_dict: dict) -> dict:
    """Clasificación de aceptación desglosada por nivel."""
    por_niv = {}
    for nivel in (1, 2, 3):
        subset = {k: v for k, v in set_dict.items() if v['nivel'] == nivel}
        por_niv[nivel] = _clasificar(subset, sal_dict)
    return por_niv


def _r12_por_nivel(set_dict: dict, sal_dict: dict) -> dict:
    por_niv = {}
    for nivel in (1, 2, 3):
        subset = {k: v for k, v in set_dict.items() if v['nivel'] == nivel}
        por_niv[nivel] = _respeto_r12(subset, sal_dict)
    return por_niv


def _desviacion_por_nivel(set_dict: dict, sal_dict: dict) -> dict:
    por_niv = {}
    for nivel in (1, 2, 3):
        subset = {k: v for k, v in set_dict.items() if v['nivel'] == nivel}
        por_niv[nivel] = _desviacion_espanol_general(subset, sal_dict)
    return por_niv


def calcular() -> dict:
    set_list = _leer_jsonl(RUTA_SET)
    set_dict = {r['id']: r for r in set_list}

    datos = {'set': set_dict, 'condiciones': {}}
    for cond in CONDICIONES:
        sal = _leer_jsonl_por_id(RUTA_RES / f'llm_{cond}.jsonl')
        log = _leer_jsonl(RUTA_LOG / f'{cond}.jsonl')
        clas = _clasificar(set_dict, sal)
        p, c, r = _pcr(clas)
        datos['condiciones'][cond] = {
            'sal': sal,
            'log': log,
            'aceptacion': clas,
            'precision': p, 'cobertura': c, 'rechazo': r,
            'por_nivel': _por_nivel(set_dict, sal),
            'upos_uas': _agregar_upos_uas(set_dict, sal),
            'arbol_exacto': _arbol_exacto(set_dict, sal),
            'desviacion': _desviacion_espanol_general(set_dict, sal),
            'desviacion_niveles': _desviacion_por_nivel(set_dict, sal),
            'r12': _respeto_r12(set_dict, sal),
            'motivos': _motivos_rechazo(set_dict, sal),
            'formato': _formato_invalido(sal),
            'consistencia': _consistencia(sal),
            'costo': _costo_desde_log(log),
        }

    # McNemar sobre correctos/incorrectos por oración.
    sal_a = datos['condiciones']['zero_shot']['sal']
    sal_b = datos['condiciones']['few_shot']['sal']
    b = c = 0
    discrepancias = []
    for id_, orig in set_dict.items():
        ca = _es_correcto(orig, sal_a.get(id_))
        cb = _es_correcto(orig, sal_b.get(id_))
        if ca and not cb:
            b += 1
            discrepancias.append((id_, 'zero_ok_few_falla', orig['oracion']))
        elif cb and not ca:
            c += 1
            discrepancias.append((id_, 'few_ok_zero_falla', orig['oracion']))
    datos['mcnemar'] = _mcnemar(b, c)
    datos['mcnemar']['discrepancias'] = discrepancias

    return datos


# ---------------------------------------------------------------------------
# Salidas.
# ---------------------------------------------------------------------------

def _escribir_markdown(m: dict, ruta: Path):
    lin = []
    lin.append('# Métricas del experimento con el LLM — Fase 2\n')

    # 1) Tabla principal.
    lin.append('## 1. Aceptación — zero-shot vs few-shot\n')
    lin.append('| Métrica | zero_shot | few_shot |')
    lin.append('| --- | --- | --- |')
    for clave, etiqueta in [
            ('precision', 'Precisión'),
            ('cobertura', 'Cobertura'),
            ('rechazo', 'Tasa de rechazo correcto')]:
        a = m['condiciones']['zero_shot'][clave]
        b = m['condiciones']['few_shot'][clave]
        lin.append(f'| {etiqueta} | {_fmt_pct(a)} | {_fmt_pct(b)} |')
    for clave, etiqueta in [
            ('VP', 'VP'), ('FP', 'FP'), ('FN', 'FN'), ('VN', 'VN'),
            ('errores_etiquetado', 'Error de etiquetado')]:
        a = m['condiciones']['zero_shot']['aceptacion'][clave]
        b = m['condiciones']['few_shot']['aceptacion'][clave]
        lin.append(f'| {etiqueta} | {a} | {b} |')
    lin.append('')

    # 2) Por nivel.
    lin.append('## 2. Aceptación por nivel\n')
    for cond in CONDICIONES:
        lin.append(f'**{cond}**\n')
        lin.append('| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |')
        lin.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for nivel in (1, 2, 3):
            c = m['condiciones'][cond]['por_nivel'][nivel]
            p, co, r = _pcr(c)
            lin.append(f"| {nivel} | {c['VP']} | {c['FP']} | {c['FN']} | {c['VN']} "
                       f"| {_fmt_pct(p)} | {_fmt_pct(co)} | {_fmt_pct(r)} |")
        lin.append('')

    # 3) UPOS y UAS/LAS.
    lin.append('## 3. Exactitud UPOS y UAS/LAS\n')
    lin.append('| Condición | Nivel | UPOS | UAS | LAS | n(UAS) | saltadas |')
    lin.append('| --- | --- | --- | --- | --- | --- | --- |')
    for cond in CONDICIONES:
        uu = m['condiciones'][cond]['upos_uas']
        for nivel in (1, 2, 3, 'total'):
            u = uu['upos'][nivel]
            d = uu['uaslas'][nivel]
            u_pct = _safe_div(u['aciertos'], u['total'])
            uas = _safe_div(d['uas'], d['total'])
            las = _safe_div(d['las'], d['total'])
            lin.append(f"| {cond} | {nivel} | {_fmt_pct(u_pct)} "
                       f"| {_fmt_pct(uas)} | {_fmt_pct(las)} "
                       f"| {d['n']} | {d['saltadas']} |")
    lin.append('')

    # 4) Coincidencia exacta del árbol.
    lin.append('## 4. Coincidencia exacta del árbol\n')
    lin.append('| Condición | Nivel | OK / Total | % |')
    lin.append('| --- | --- | --- | --- |')
    for cond in CONDICIONES:
        ae = m['condiciones'][cond]['arbol_exacto']
        for nivel in (1, 2, 3, 'total'):
            d = ae[nivel]
            lin.append(f"| {cond} | {nivel} | {d['ok']}/{d['total']} | {_fmt_pct(d['pct'])} |")
    lin.append('')

    # 5) Desviación al español general.
    lin.append('## 5. Desviación hacia el español general\n')
    lin.append('_De las oraciones gramaticales que la gramática rechaza_'
               ' _(fenómenos del nivel 3), qué porcentaje acepta el LLM._\n')
    lin.append('| Condición | Aceptadas / Total | % |')
    lin.append('| --- | --- | --- |')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['desviacion']
        lin.append(f"| {cond} | {d['aceptadas']}/{d['total']} | {_fmt_pct(d['porcentaje'])} |")
    lin.append('')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['desviacion']
        if not d['por_fenomeno']:
            continue
        lin.append(f'**{cond} — aceptaciones por fenómeno**\n')
        lin.append('| Fenómeno | Casos aceptados |')
        lin.append('| --- | --- |')
        for k, v in d['por_fenomeno'].most_common():
            lin.append(f'| {k} | {v} |')
        lin.append('')

    # 6) R12.
    lin.append('## 6. Respeto de R12 (unir `de` / `del` al sustantivo)\n')
    lin.append('| Condición | OK / Total | Indecisos | % |')
    lin.append('| --- | --- | --- | --- |')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['r12']
        lin.append(f"| {cond} | {d['ok']}/{d['total']} | {d['indecisos']} | {_fmt_pct(d['porcentaje'])} |")
    lin.append('')

    # 7) Motivos de rechazo.
    lin.append('## 7. Motivos del rechazo correcto\n')
    lin.append('| Condición | Etapa correcta | Regla citada correcta | Reglas inventadas |')
    lin.append('| --- | --- | --- | --- |')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['motivos']
        inv = sum(d['reglas_inventadas'].values())
        lin.append(f"| {cond} | {d['etapa_ok']}/{d['casos']} ({_fmt_pct(d['pct_etapa'])}) "
                   f"| {d['regla_ok']}/{d['casos']} ({_fmt_pct(d['pct_regla'])}) "
                   f"| {inv} |")
    lin.append('')
    for cond in CONDICIONES:
        inv = m['condiciones'][cond]['motivos']['reglas_inventadas']
        if inv:
            lin.append(f'**{cond} — reglas citadas que no existen**: '
                       + ', '.join(f'`{k}` ({v})' for k, v in inv.most_common()))
            lin.append('')

    # 8) Formato.
    lin.append('## 8. Formato de la respuesta\n')
    lin.append('| Condición | Inválidas / Total | % |')
    lin.append('| --- | --- | --- |')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['formato']
        lin.append(f"| {cond} | {d['invalidas']}/{d['total']} | {_fmt_pct(d['porcentaje'])} |")
    lin.append('')

    # 9) Consistencia entre las 3 repeticiones.
    lin.append('## 9. Consistencia entre las 3 repeticiones\n')
    lin.append('| Condición | Consistentes / Total | % |')
    lin.append('| --- | --- | --- |')
    for cond in CONDICIONES:
        d = m['condiciones'][cond]['consistencia']
        lin.append(f"| {cond} | {d['consistentes']}/{d['total']} | {_fmt_pct(d['porcentaje'])} |")
    lin.append('')

    # 10) McNemar.
    lin.append('## 10. Zero-shot vs few-shot — prueba de McNemar\n')
    mc = m['mcnemar']
    lin.append(f"- Oraciones correctas solo en zero_shot (b): **{mc['b']}**")
    lin.append(f"- Oraciones correctas solo en few_shot  (c): **{mc['c']}**")
    lin.append(f"- Estadístico ({mc['metodo']}): **{mc['estadistico']:.4f}**")
    lin.append(f"- Valor p: **{mc['p']:.4f}**")
    signif = 'significativo' if mc['p'] < 0.05 else 'no significativo'
    lin.append(f"- Resultado: diferencia _{signif}_ al 5 %.\n")

    # 11) Costo.
    lin.append('## 11. Costo\n')
    lin.append('| Condición | Llamadas | Tokens entrada | Tokens salida | Costo USD | Latencia prom. |')
    lin.append('| --- | --- | --- | --- | --- | --- |')
    for cond in CONDICIONES:
        c = m['condiciones'][cond]['costo']
        lin.append(f"| {cond} | {c['llamadas']} | {c['tokens_in']} | {c['tokens_out']} "
                   f"| ${c['costo_usd']:.4f} | {c['latencia_prom_s']:.2f}s |")
    tot_costo = sum(m['condiciones'][c]['costo']['costo_usd'] for c in CONDICIONES)
    tot_tin = sum(m['condiciones'][c]['costo']['tokens_in'] for c in CONDICIONES)
    tot_tout = sum(m['condiciones'][c]['costo']['tokens_out'] for c in CONDICIONES)
    lin.append(f"\n**Totales: {tot_tin} tokens de entrada, {tot_tout} de salida, ${tot_costo:.4f}**.\n")

    ruta.write_text('\n'.join(lin), encoding='utf-8')


def _escribir_csv(m: dict, ruta: Path):
    with ruta.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Métrica', 'zero_shot', 'few_shot'])
        for cond_clave, et in [('precision', 'Precisión'),
                               ('cobertura', 'Cobertura'),
                               ('rechazo', 'Rechazo correcto')]:
            a = m['condiciones']['zero_shot'][cond_clave]
            b = m['condiciones']['few_shot'][cond_clave]
            w.writerow([et, f'{a:.4f}' if a == a else '',
                        f'{b:.4f}' if b == b else ''])
        for clave in ('VP', 'FP', 'FN', 'VN', 'errores_etiquetado'):
            w.writerow([clave,
                        m['condiciones']['zero_shot']['aceptacion'][clave],
                        m['condiciones']['few_shot']['aceptacion'][clave]])
        w.writerow([])
        w.writerow(['Formato inválido (%)',
                    m['condiciones']['zero_shot']['formato']['porcentaje'],
                    m['condiciones']['few_shot']['formato']['porcentaje']])
        w.writerow(['Consistencia (%)',
                    m['condiciones']['zero_shot']['consistencia']['porcentaje'],
                    m['condiciones']['few_shot']['consistencia']['porcentaje']])
        w.writerow(['Desviación español (%)',
                    m['condiciones']['zero_shot']['desviacion']['porcentaje'],
                    m['condiciones']['few_shot']['desviacion']['porcentaje']])
        w.writerow(['R12 (%)',
                    m['condiciones']['zero_shot']['r12']['porcentaje'],
                    m['condiciones']['few_shot']['r12']['porcentaje']])
        w.writerow([])
        w.writerow(['Costo'])
        w.writerow(['', 'tokens_in', 'tokens_out', 'costo_usd', 'latencia_s'])
        for cond in CONDICIONES:
            c = m['condiciones'][cond]['costo']
            w.writerow([cond, c['tokens_in'], c['tokens_out'],
                        f"{c['costo_usd']:.6f}", f"{c['latencia_prom_s']:.4f}"])
        w.writerow([])
        w.writerow(['McNemar',
                    f"b={m['mcnemar']['b']}",
                    f"c={m['mcnemar']['c']}",
                    f"p={m['mcnemar']['p']:.4f}",
                    m['mcnemar']['metodo']])


def _escribir_errores(m: dict, ruta: Path):
    lin = ['# Errores y desviaciones del LLM — Fase 2\n']
    set_dict = m['set']
    for cond in CONDICIONES:
        datos = m['condiciones'][cond]
        lin.append(f'## {cond}\n')
        lin.append('### Desviaciones hacia el español general '
                   '(oraciones gramaticales que debían rechazarse)\n')
        aceptadas = [(i, o, fen) for i, o, fen, ok in datos['desviacion']['casos'] if ok]
        if not aceptadas:
            lin.append('_(ninguna)_\n')
        for id_, oracion, fen in aceptadas:
            sal = datos['sal'].get(id_, {})
            lin.append(f'- **{id_}** ({fen}): `{oracion}`')
            if sal.get('arbol'):
                lin.append(f"  - árbol del LLM: `{sal['arbol']}`")
        lin.append('')
        lin.append('### R12 — casos en que el LLM unió `de` al verbo\n')
        malos = [(i, o) for i, o, m_ in datos['r12']['detalle'] if m_ == 'unido_al_verbo']
        if not malos:
            lin.append('_(ninguno)_\n')
        for id_, oracion in malos:
            sal = datos['sal'].get(id_, {})
            lin.append(f'- **{id_}**: `{oracion}`')
            if sal.get('arbol'):
                lin.append(f"  - árbol del LLM: `{sal['arbol']}`")
        lin.append('')
        lin.append('### Motivos de rechazo que no coinciden con lo esperado\n')
        if not datos['motivos']['detalle']:
            lin.append('_(ninguno)_\n')
        for d in datos['motivos']['detalle']:
            lin.append(f"- **{d['id']}**: `{d['oracion']}`")
            lin.append(f"  - esperada etapa `{d['etapa_esperada']}` regla `{d['regla_esperada']}`, "
                       f"obtuvo etapa `{d['etapa_obtenida']}` reglas citadas: "
                       f"{d['reglas_citadas'] or '[]'}")
        lin.append('')
        lin.append('### Errores de etiquetado (aceptada bien pero árbol distinto)\n')
        etq = [(i, o) for i, tipo, o in datos['aceptacion']['detalle'] if tipo == 'etiquetado']
        if not etq:
            lin.append('_(ninguno)_\n')
        for id_, oracion in etq:
            orig = set_dict[id_]
            sal = datos['sal'].get(id_, {})
            lin.append(f'- **{id_}**: `{oracion}`')
            lin.append(f"  - esperado: `{orig.get('arbol')}`")
            lin.append(f"  - LLM: `{sal.get('arbol')}`")
        lin.append('')
    ruta.write_text('\n'.join(lin), encoding='utf-8')


def _generar_graficas(m: dict):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f'[graficas] matplotlib no disponible: {e}')
        return
    RUTA_GRAF.mkdir(parents=True, exist_ok=True)

    # 1) Barras agrupadas: métricas globales.
    metricas = [
        ('Precisión', 'precision'),
        ('Cobertura', 'cobertura'),
        ('Rechazo correcto', 'rechazo'),
        ('Formato válido',
         lambda d: 1.0 - d['formato']['porcentaje']),
        ('Consistencia',
         lambda d: d['consistencia']['porcentaje']),
    ]
    labels = [et for et, _ in metricas]
    x = np.arange(len(labels))
    ancho = 0.4
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, cond in enumerate(CONDICIONES):
        valores = []
        for _, f in metricas:
            if isinstance(f, str):
                v = m['condiciones'][cond][f]
            else:
                v = f(m['condiciones'][cond])
            valores.append(100 * v if v == v else 0.0)
        ax.bar(x + i * ancho, valores, ancho, label=cond)
    ax.set_xticks(x + ancho / 2)
    ax.set_xticklabels(labels, rotation=20, ha='right')
    ax.set_ylim(0, 100)
    ax.set_ylabel('%')
    ax.set_title('Métricas globales del LLM — zero-shot vs few-shot')
    ax.legend()
    fig.tight_layout()
    fig.savefig(RUTA_GRAF / 'llm_metricas_globales.png', dpi=140)
    plt.close(fig)

    # 2) Precisión/Cobertura por nivel.
    fig, ax = plt.subplots(figsize=(9, 5))
    niveles = [1, 2, 3]
    x = np.arange(len(niveles))
    ancho = 0.2
    colores = {'zero_shot': 'C0', 'few_shot': 'C1'}
    for i, cond in enumerate(CONDICIONES):
        pres = []
        cobs = []
        for n in niveles:
            d = m['condiciones'][cond]['por_nivel'][n]
            p, co, r = _pcr(d)
            pres.append(100 * (p if p == p else 0))
            cobs.append(100 * (co if co == co else 0))
        ax.bar(x + (2 * i) * ancho, pres, ancho,
               label=f'{cond} precisión', color=colores[cond])
        ax.bar(x + (2 * i + 1) * ancho, cobs, ancho,
               label=f'{cond} cobertura', color=colores[cond], alpha=0.5)
    ax.set_xticks(x + 1.5 * ancho)
    ax.set_xticklabels([str(n) for n in niveles])
    ax.set_ylim(0, 100)
    ax.set_ylabel('%')
    ax.set_title('Precisión y cobertura por nivel')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RUTA_GRAF / 'llm_aceptacion_por_nivel.png', dpi=140)
    plt.close(fig)

    # 3) Desviación al español general, por nivel.
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, cond in enumerate(CONDICIONES):
        vals = []
        for n in niveles:
            d = m['condiciones'][cond]['desviacion_niveles'][n]
            vals.append(100 * (d['porcentaje'] if d['porcentaje'] == d['porcentaje'] else 0))
        ax.bar(x + i * 0.4, vals, 0.4, label=cond)
    ax.set_xticks(x + 0.2)
    ax.set_xticklabels([str(n) for n in niveles])
    ax.set_ylim(0, 100)
    ax.set_ylabel('% de desviación')
    ax.set_title('Desviación hacia el español general por nivel')
    ax.legend()
    fig.tight_layout()
    fig.savefig(RUTA_GRAF / 'llm_desviacion_por_nivel.png', dpi=140)
    plt.close(fig)


def main():
    m = calcular()
    RUTA_RES.mkdir(parents=True, exist_ok=True)
    _escribir_markdown(m, RUTA_RES / 'metricas_llm.md')
    _escribir_csv(m, RUTA_RES / 'metricas_llm.csv')
    _escribir_errores(m, RUTA_RES / 'errores_llm.md')
    _generar_graficas(m)
    print('Escrito:',
          RUTA_RES / 'metricas_llm.md',
          RUTA_RES / 'metricas_llm.csv',
          RUTA_RES / 'errores_llm.md',
          sep='\n  ')
    print(f'\nCosto total: '
          f'${sum(m["condiciones"][c]["costo"]["costo_usd"] for c in CONDICIONES):.4f}')


if __name__ == '__main__':
    main()
