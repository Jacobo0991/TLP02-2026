"""Cálculo de métricas de la Fase 2.

Lee el set de prueba y las salidas de los sistemas (parser propio, spaCy y
HuggingFace; opcionalmente, un LLM) y produce:

  - `fase2/resultados/metricas.csv` y `fase2/resultados/metricas.md`
    con todas las tablas del informe.
  - `fase2/resultados/graficas/*.png` con matplotlib.
  - `fase2/resultados/errores.md` con cada error y su oración.

Las métricas se calculan por nivel (1, 2, 3) y en total:

  - **Exactitud UPOS** por sistema sobre las 60 oraciones. El parser solo
    cuenta en las oraciones que tokenizó sin error léxico; se indica cuántas
    quedan fuera.
  - **UAS / LAS** para el parser y spaCy sobre las oraciones con árbol
    esperado (el parser se convierte a UD con `ud.py`).
  - **Aceptación** del parser (y del LLM si existe): precisión, cobertura,
    tasa de rechazo correcto y clasificación de errores (FP, FN, etiquetado).
  - **Matriz de confusión UPOS** para spaCy y HF (etiqueta esperada vs.
    predicha, lista de las confusiones más frecuentes).
  - **Desacuerdos de adjunción**: oraciones donde el parser y spaCy unen
    un SP (ADP) a cabezas distintas (nmod ↔ obl).
  - **Costo**: tiempo promedio por oración por sistema y tamaño del modelo
    en disco.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from fase2.ud import arbol_a_dependencias, CAT_A_UPOS   # noqa: E402

RESULTS_DIR = _RAIZ / 'fase2' / 'resultados'
GRAFICAS_DIR = RESULTS_DIR / 'graficas'


# ---------------------------------------------------------------------------
# Lectura de archivos JSONL.
# ---------------------------------------------------------------------------

def _leer_jsonl(ruta: Path) -> dict:
    """Devuelve {id: registro} para los JSONL por oración."""
    out = {}
    if not ruta.exists():
        return out
    with ruta.open(encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            out[r['id']] = r
    return out


def _leer_set():
    return _leer_jsonl(_RAIZ / 'fase2' / 'pruebas' / 'oraciones.jsonl')


def _leer_llm():
    """Lee todos los archivos `llm_*.jsonl` del directorio de resultados."""
    salidas = {}
    for p in sorted(RESULTS_DIR.glob('llm_*.jsonl')):
        nombre = p.stem.replace('llm_', 'llm-')
        salidas[nombre] = _leer_jsonl(p)
    return salidas


# ---------------------------------------------------------------------------
# Métricas: exactitud UPOS.
# ---------------------------------------------------------------------------

def _upos_del_parser(reg):
    """Convierte las categorías del parser en UPOS, manteniendo la longitud."""
    return [CAT_A_UPOS[c] for c in reg['categorias']]


def _exactitud_upos(esperado, obtenido):
    """(aciertos, total) con alineación por posición; si no coinciden las
    longitudes, se cuenta hasta el mínimo y el resto como errores."""
    aciertos = 0
    total = max(len(esperado), len(obtenido))
    for a, b in zip(esperado, obtenido):
        if a == b:
            aciertos += 1
    return aciertos, total


# ---------------------------------------------------------------------------
# UAS / LAS.
# ---------------------------------------------------------------------------

def _las(esperado_cab, esperado_rel, obtenido_cab, obtenido_rel):
    """Devuelve (uas_ok, las_ok, total) para una oración.

    uas_ok: tokens con la cabeza correcta.
    las_ok: tokens con cabeza Y relación correctas.
    """
    total = min(len(esperado_cab), len(obtenido_cab))
    uas = sum(1 for k in range(total)
              if esperado_cab[k] == obtenido_cab[k])
    las = sum(1 for k in range(total)
              if esperado_cab[k] == obtenido_cab[k]
              and esperado_rel[k] == obtenido_rel[k])
    return uas, las, total


# ---------------------------------------------------------------------------
# Clasificación de aceptación (parser / LLM).
# ---------------------------------------------------------------------------

def _clasificar_aceptacion(set_dict, sal_dict):
    """Devuelve dict con VP, FP, FN, VN, errores_etiquetado y detalle."""
    vp = fp = fn = vn = 0
    err_etq = 0
    detalle = []
    sin_semantico = True   # ¿la salida distingue rechazo semántico?
    for id_, orig in set_dict.items():
        esp = orig['esperado']        # 'aceptada' | 'rechazo_*'
        salida = sal_dict.get(id_)
        if salida is None:
            continue
        aceptada = salida.get('aceptada')
        etapa = salida.get('etapa')
        if etapa == 'semantico':
            sin_semantico = False
        if esp == 'aceptada':
            if aceptada:
                # Revisar árbol/categorías para "error de etiquetado".
                bien_etq = True
                if orig.get('arbol') and salida.get('arbol'):
                    bien_etq = _arboles_iguales(orig['arbol'], salida['arbol'])
                if bien_etq:
                    vp += 1
                else:
                    vp += 1          # Aceptada correctamente...
                    err_etq += 1     # ...pero con etiquetado distinto.
                    detalle.append((id_, 'etiquetado', orig['oracion']))
            else:
                fn += 1
                detalle.append((id_, 'FN', orig['oracion']))
        else:  # debe rechazarse
            if aceptada:
                fp += 1
                detalle.append((id_, 'FP', orig['oracion']))
            else:
                vn += 1
    return {
        'VP': vp, 'FP': fp, 'FN': fn, 'VN': vn,
        'errores_etiquetado': err_etq,
        'detalle': detalle,
        'sin_semantico': sin_semantico,
    }


def _arboles_iguales(a: str, b: str) -> bool:
    """Normaliza espacios para comparar dos árboles de corchetes."""
    import re
    return re.sub(r'\s+', ' ', a).strip() == re.sub(r'\s+', ' ', b).strip()


def _precision_cobertura_rechazo(c):
    vp, fp, fn, vn = c['VP'], c['FP'], c['FN'], c['VN']
    precision = vp / (vp + fp) if (vp + fp) else float('nan')
    cobertura = vp / (vp + fn) if (vp + fn) else float('nan')
    rechazo = vn / (vn + fp) if (vn + fp) else float('nan')
    return precision, cobertura, rechazo


# ---------------------------------------------------------------------------
# Matriz de confusión UPOS.
# ---------------------------------------------------------------------------

def _matriz_confusion(set_dict, sal_dict):
    """(esperado, obtenido) -> cuenta. Solo pares alineados por posición."""
    conf = Counter()
    for id_, orig in set_dict.items():
        salida = sal_dict.get(id_)
        if salida is None:
            continue
        esp = orig['upos']
        obt = salida['upos']
        for a, b in zip(esp, obt):
            conf[(a, b)] += 1
    return conf


# ---------------------------------------------------------------------------
# Desacuerdos de adjunción (parser vs spaCy).
# ---------------------------------------------------------------------------

def _desacuerdos_adjuncion(set_dict, parser_dict, spacy_dict):
    """Lista de oraciones donde una preposición (ADP) une su SP a un núcleo
    distinto entre el parser y spaCy.

    Para cada ADP de la oración (`upos == 'ADP'` según el set), miramos la
    relación en el parser (nmod/obl/case) y en spaCy. Si difieren,
    reportamos la oración.
    """
    resultados = []
    for id_, orig in set_dict.items():
        if orig['esperado'] != 'aceptada' or not orig.get('arbol'):
            continue
        p = parser_dict.get(id_)
        s = spacy_dict.get(id_)
        if not p or not s or not p.get('arbol'):
            continue
        try:
            dep_p = arbol_a_dependencias(p['arbol'])
        except Exception:
            continue
        rels_p = dep_p['relaciones']
        cab_p = dep_p['cabezas']
        rels_s = s['relaciones']
        cab_s = s['cabezas']
        upos_esp = orig['upos']
        if not (len(rels_p) == len(rels_s) == len(upos_esp)):
            continue
        for k, u in enumerate(upos_esp):
            if u != 'ADP':
                continue
            # Buscamos quién usa el SP de esta preposición.
            # La relación interesante es la de la cabeza del SN que la
            # preposición marca como `case`: esa cabeza es la que se une
            # al nombre o al verbo. Encontrémosla.
            # En nuestro UD: la ADP apunta como `case` a su "head" que es
            # el núcleo del SN. Ese núcleo tiene su propia relación.
            def rel_del_sp(cab, rel, k):
                nucleo = cab[k] if rel[k] == 'case' else None
                if nucleo is None or nucleo == 0:
                    return rel[k]
                return rel[nucleo - 1]
            rp = rel_del_sp(cab_p, rels_p, k)
            rs = rel_del_sp(cab_s, rels_s, k)
            if rp != rs and {rp, rs} & {'nmod', 'obl'}:
                resultados.append({
                    'id': id_, 'oracion': orig['oracion'],
                    'preposicion': p['categorias'][k] if k < len(p.get('categorias', [])) else '?',
                    'parser': rp, 'spacy': rs,
                })
    return resultados


# ---------------------------------------------------------------------------
# Tamaño del modelo en disco.
# ---------------------------------------------------------------------------

def _tamano_dir(ruta: Path) -> int:
    total = 0
    for p in ruta.rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _tamano_modelo_spacy(nombre: str) -> int:
    try:
        import importlib, pathlib
        mod = importlib.import_module(nombre)
        return _tamano_dir(pathlib.Path(mod.__file__).parent)
    except Exception:
        return 0


def _tamano_modelo_hf(nombre: str) -> int:
    """Suma los bytes del modelo en la cache de HuggingFace, si está en disco."""
    try:
        from huggingface_hub import scan_cache_dir
        s = scan_cache_dir()
        for repo in s.repos:
            if repo.repo_id == nombre:
                return sum(r.size_on_disk for r in repo.revisions)
    except Exception:
        return 0
    return 0


def _tamano_parser() -> int:
    """El "modelo" del parser son sus archivos de código."""
    total = 0
    for p in (_RAIZ / 'fase2').glob('*.py'):
        if p.name in ('lexer_es.py', 'parser_es.py', 'ud.py'):
            total += p.stat().st_size
    return total


def _mb(n_bytes: int) -> str:
    return f"{n_bytes / (1024*1024):.1f} MB" if n_bytes else "—"


# ---------------------------------------------------------------------------
# Cálculo principal.
# ---------------------------------------------------------------------------

def calcular(set_dict, parser_dict, spacy_dict, hf_dict, llms_dict):
    """Devuelve un diccionario con todas las métricas y tablas."""
    sistemas_upos = {'parser': parser_dict, 'spacy': spacy_dict, 'hf': hf_dict}
    sistemas_upos.update(llms_dict)
    niveles = (1, 2, 3)

    # --- Exactitud UPOS por sistema y nivel ---
    exact_upos = {sys_: {} for sys_ in sistemas_upos}
    fuera_parser = {n: 0 for n in niveles}
    for nivel in niveles:
        por_sys = {}
        for sys_, dic in sistemas_upos.items():
            aciertos = 0
            total = 0
            n_evaluadas = 0
            for id_, orig in set_dict.items():
                if orig['nivel'] != nivel:
                    continue
                esp = orig['upos']
                salida = dic.get(id_)
                if salida is None:
                    continue
                if sys_ == 'parser':
                    if salida.get('etapa') == 'lexico':
                        fuera_parser[nivel] += 1
                        continue
                    obt = _upos_del_parser(salida)
                else:
                    obt = salida.get('upos', [])
                a, t = _exactitud_upos(esp, obt)
                aciertos += a
                total += t
                n_evaluadas += 1
            por_sys[sys_] = {
                'aciertos': aciertos, 'total': total,
                'exactitud': aciertos / total if total else 0.0,
                'n_evaluadas': n_evaluadas,
            }
        exact_upos[nivel] = por_sys
    # Totales (todas las oraciones).
    exact_upos['total'] = {}
    for sys_ in sistemas_upos:
        a = sum(exact_upos[n][sys_]['aciertos'] for n in niveles)
        t = sum(exact_upos[n][sys_]['total'] for n in niveles)
        exact_upos['total'][sys_] = {
            'aciertos': a, 'total': t,
            'exactitud': a / t if t else 0.0,
            'n_evaluadas': sum(exact_upos[n][sys_]['n_evaluadas'] for n in niveles),
        }

    # --- UAS / LAS parser y spaCy ---
    uaslas = {'parser': {}, 'spacy': {}}
    for nivel in list(niveles) + ['total']:
        for sys_ in ('parser', 'spacy'):
            uaslas[sys_][nivel] = {'uas': 0, 'las': 0, 'total': 0, 'n': 0}
    for id_, orig in set_dict.items():
        if orig['esperado'] != 'aceptada' or not orig.get('arbol'):
            continue
        nivel = orig['nivel']
        # Esperado: convertir el árbol del set con ud.py.
        try:
            dep_esp = arbol_a_dependencias(orig['arbol'])
        except Exception:
            continue
        esp_cab = dep_esp['cabezas']
        esp_rel = dep_esp['relaciones']
        # Parser.
        p = parser_dict.get(id_)
        if p and p.get('arbol'):
            try:
                dep_p = arbol_a_dependencias(p['arbol'])
                u, l, t = _las(esp_cab, esp_rel, dep_p['cabezas'], dep_p['relaciones'])
                uaslas['parser'][nivel]['uas'] += u
                uaslas['parser'][nivel]['las'] += l
                uaslas['parser'][nivel]['total'] += t
                uaslas['parser'][nivel]['n'] += 1
            except Exception:
                pass
        # spaCy.
        s = spacy_dict.get(id_)
        if s:
            u, l, t = _las(esp_cab, esp_rel, s['cabezas'], s['relaciones'])
            uaslas['spacy'][nivel]['uas'] += u
            uaslas['spacy'][nivel]['las'] += l
            uaslas['spacy'][nivel]['total'] += t
            uaslas['spacy'][nivel]['n'] += 1
    # Totales.
    for sys_ in ('parser', 'spacy'):
        tot = {'uas': 0, 'las': 0, 'total': 0, 'n': 0}
        for nivel in niveles:
            for k in tot:
                tot[k] += uaslas[sys_][nivel][k]
        uaslas[sys_]['total'] = tot

    # --- Aceptación: parser y LLM ---
    aceptacion = {'parser': _clasificar_aceptacion(set_dict, parser_dict)}
    for nombre, dic in llms_dict.items():
        aceptacion[nombre] = _clasificar_aceptacion(set_dict, dic)
    # Por nivel también.
    aceptacion_niveles = {}
    for sys_, dic in {'parser': parser_dict, **llms_dict}.items():
        por_niv = {}
        for nivel in niveles:
            subset = {k: v for k, v in set_dict.items() if v['nivel'] == nivel}
            por_niv[nivel] = _clasificar_aceptacion(subset, dic)
        aceptacion_niveles[sys_] = por_niv

    # --- Matrices de confusión UPOS (spaCy, HF) ---
    conf_spacy = _matriz_confusion(set_dict, spacy_dict)
    conf_hf = _matriz_confusion(set_dict, hf_dict)

    # --- Desacuerdos de adjunción ---
    desacuerdos = _desacuerdos_adjuncion(set_dict, parser_dict, spacy_dict)

    # --- Costo: tiempo promedio por oración y tamaño ---
    costos = {}
    for sys_, dic in sistemas_upos.items():
        tiempos = [r.get('tiempo_s') for r in dic.values() if r.get('tiempo_s') is not None]
        prom = sum(tiempos) / len(tiempos) if tiempos else 0.0
        costos[sys_] = {'tiempo_prom_s': prom, 'n': len(tiempos)}
    # Tamaños en disco.
    costos['parser']['tamano_bytes'] = _tamano_parser()
    costos['spacy']['tamano_bytes'] = _tamano_modelo_spacy('es_core_news_lg')
    costos['hf']['tamano_bytes'] = _tamano_modelo_hf('mrm8488/RuPERTa-base-finetuned-pos')
    for nombre in llms_dict:
        costos[nombre]['tamano_bytes'] = 0

    return {
        'exactitud_upos': exact_upos,
        'uaslas': uaslas,
        'aceptacion': aceptacion,
        'aceptacion_niveles': aceptacion_niveles,
        'fuera_parser': fuera_parser,
        'conf_spacy': conf_spacy,
        'conf_hf': conf_hf,
        'desacuerdos_adjuncion': desacuerdos,
        'costos': costos,
    }


# ---------------------------------------------------------------------------
# Salidas: CSV, Markdown, errores.md y gráficas.
# ---------------------------------------------------------------------------

def _fmt_pct(x):
    if x is None:
        return '—'
    if isinstance(x, float) and (x != x):   # NaN
        return '—'
    return f"{100*x:.1f}%"


def _escribir_csv(m, ruta: Path):
    """Un CSV con todas las métricas; secciones separadas por filas vacías."""
    with ruta.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        # Exactitud UPOS.
        w.writerow(['Exactitud UPOS por nivel y sistema'])
        sistemas = list(m['exactitud_upos'][1].keys())
        w.writerow(['nivel'] + sistemas)
        for nivel in (1, 2, 3, 'total'):
            fila = [nivel]
            for sys_ in sistemas:
                fila.append(f"{m['exactitud_upos'][nivel][sys_]['exactitud']:.4f}")
            w.writerow(fila)
        w.writerow([])

        # UAS/LAS.
        w.writerow(['UAS y LAS por nivel'])
        w.writerow(['nivel', 'parser_UAS', 'parser_LAS', 'parser_n',
                    'spacy_UAS', 'spacy_LAS', 'spacy_n'])
        for nivel in (1, 2, 3, 'total'):
            fila = [nivel]
            for sys_ in ('parser', 'spacy'):
                d = m['uaslas'][sys_][nivel]
                uas = d['uas'] / d['total'] if d['total'] else 0.0
                las = d['las'] / d['total'] if d['total'] else 0.0
                fila.extend([f"{uas:.4f}", f"{las:.4f}", d['n']])
            w.writerow(fila)
        w.writerow([])

        # Aceptación.
        w.writerow(['Aceptación (parser y LLM)'])
        w.writerow(['sistema', 'VP', 'FP', 'FN', 'VN',
                    'precision', 'cobertura', 'rechazo_correcto',
                    'errores_etiquetado'])
        for sys_, d in m['aceptacion'].items():
            p, c, r = _precision_cobertura_rechazo(d)
            w.writerow([sys_, d['VP'], d['FP'], d['FN'], d['VN'],
                        f"{p:.4f}" if p == p else '',
                        f"{c:.4f}" if c == c else '',
                        f"{r:.4f}" if r == r else '',
                        d['errores_etiquetado']])
        w.writerow([])

        # Costos.
        w.writerow(['Costo: tiempo promedio por oración y tamaño del modelo'])
        w.writerow(['sistema', 'tiempo_prom_s', 'tamano_MB'])
        for sys_, d in m['costos'].items():
            w.writerow([sys_, f"{d['tiempo_prom_s']:.6f}",
                        f"{d.get('tamano_bytes',0)/(1024*1024):.2f}"])


def _escribir_markdown(m, ruta: Path):
    lin = []
    lin.append("# Métricas — Fase 2\n")
    lin.append(f"_Generado: {time.strftime('%Y-%m-%d %H:%M:%S')}_\n")

    sistemas = list(m['exactitud_upos'][1].keys())
    lin.append("## 1. Exactitud UPOS por nivel y sistema\n")
    lin.append("| Nivel | " + " | ".join(sistemas) + " |")
    lin.append("| --- |" + " --- |" * len(sistemas))
    for nivel in (1, 2, 3, 'total'):
        celdas = []
        for sys_ in sistemas:
            d = m['exactitud_upos'][nivel][sys_]
            celdas.append(f"{_fmt_pct(d['exactitud'])} ({d['aciertos']}/{d['total']})")
        lin.append(f"| {nivel} | " + " | ".join(celdas) + " |")
    lin.append("")
    fp = m['fuera_parser']
    lin.append(f"_Parser: quedan fuera por error léxico — nivel 1: {fp[1]}, nivel 2: {fp[2]}, nivel 3: {fp[3]} (total {sum(fp.values())})._\n")

    lin.append("## 2. UAS y LAS por nivel (oraciones con árbol esperado)\n")
    lin.append("| Nivel | Parser UAS | Parser LAS | n | spaCy UAS | spaCy LAS | n |")
    lin.append("| --- | --- | --- | --- | --- | --- | --- |")
    for nivel in (1, 2, 3, 'total'):
        p = m['uaslas']['parser'][nivel]
        s = m['uaslas']['spacy'][nivel]
        p_uas = p['uas'] / p['total'] if p['total'] else 0.0
        p_las = p['las'] / p['total'] if p['total'] else 0.0
        s_uas = s['uas'] / s['total'] if s['total'] else 0.0
        s_las = s['las'] / s['total'] if s['total'] else 0.0
        lin.append(f"| {nivel} | {_fmt_pct(p_uas)} | {_fmt_pct(p_las)} | {p['n']} | "
                   f"{_fmt_pct(s_uas)} | {_fmt_pct(s_las)} | {s['n']} |")
    lin.append("")

    lin.append("## 3. Aceptación — parser y LLM (clase positiva: aceptada)\n")
    lin.append("| Sistema | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto | Err. etiquetado |")
    lin.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for sys_, d in m['aceptacion'].items():
        p, c, r = _precision_cobertura_rechazo(d)
        lin.append(f"| {sys_} | {d['VP']} | {d['FP']} | {d['FN']} | {d['VN']} | "
                   f"{_fmt_pct(p)} | {_fmt_pct(c)} | {_fmt_pct(r)} | {d['errores_etiquetado']} |")
        if d.get('sin_semantico'):
            lin.append(f"\n> _Advertencia: la salida de **{sys_}** no distingue rechazos semánticos (etapa `semantico`). "
                       "Los rechazos esperados por reglas C1-C8 contarán como falsos positivos._\n")
    lin.append("")

    lin.append("### Aceptación desglosada por nivel\n")
    for sys_, por_niv in m['aceptacion_niveles'].items():
        lin.append(f"**{sys_}**\n")
        lin.append("| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |")
        lin.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for nivel in (1, 2, 3):
            d = por_niv[nivel]
            p, c, r = _precision_cobertura_rechazo(d)
            lin.append(f"| {nivel} | {d['VP']} | {d['FP']} | {d['FN']} | {d['VN']} | "
                       f"{_fmt_pct(p)} | {_fmt_pct(c)} | {_fmt_pct(r)} |")
        lin.append("")

    lin.append("## 4. Confusiones UPOS más frecuentes\n")
    for nombre, conf in (('spaCy', m['conf_spacy']), ('HuggingFace', m['conf_hf'])):
        errs = Counter({k: v for k, v in conf.items() if k[0] != k[1]})
        lin.append(f"**{nombre} — top 10 errores**\n")
        if not errs:
            lin.append("_(sin errores detectados)_\n")
            continue
        lin.append("| Esperado → Obtenido | Casos |")
        lin.append("| --- | --- |")
        for (esp, obt), n in errs.most_common(10):
            lin.append(f"| {esp} → {obt} | {n} |")
        lin.append("")

    lin.append("## 5. Desacuerdos de adjunción (parser vs spaCy)\n")
    if not m['desacuerdos_adjuncion']:
        lin.append("_(sin desacuerdos nmod↔obl en las oraciones aceptadas)_\n")
    else:
        lin.append("| Id | Oración | Parser | spaCy |")
        lin.append("| --- | --- | --- | --- |")
        for d in m['desacuerdos_adjuncion']:
            lin.append(f"| {d['id']} | {d['oracion']} | {d['parser']} | {d['spacy']} |")
        lin.append("")

    lin.append("## 6. Costo\n")
    lin.append("| Sistema | Tiempo promedio por oración | Tamaño en disco |")
    lin.append("| --- | --- | --- |")
    for sys_, d in m['costos'].items():
        lin.append(f"| {sys_} | {d['tiempo_prom_s']*1000:.1f} ms | {_mb(d.get('tamano_bytes',0))} |")
    lin.append("")

    ruta.write_text("\n".join(lin), encoding='utf-8')


def _escribir_errores(set_dict, m, ruta: Path, parser_dict, spacy_dict, hf_dict, llms_dict):
    """Genera `errores.md` con cada error del parser/LLM/spaCy/HF."""
    lin = ["# Errores cualitativos — Fase 2\n"]

    # Errores del parser (FP, FN, etiquetado).
    lin.append("## Parser — rechazos equivocados y errores de etiquetado\n")
    for id_, tipo, oracion in m['aceptacion']['parser']['detalle']:
        d = parser_dict.get(id_, {})
        lin.append(f"- **{id_} [{tipo}]**: `{oracion}`")
        if d.get('mensajes'):
            lin.append(f"  - mensajes del parser: {d['mensajes']}")
        if tipo == 'etiquetado':
            orig = set_dict[id_]
            lin.append(f"  - árbol esperado: `{orig.get('arbol')}`")
            lin.append(f"  - árbol parser:   `{d.get('arbol')}`")
    lin.append("")

    # spaCy: oraciones con más errores UPOS.
    def _errores_upos(sys_name, dic):
        filas = []
        for id_, orig in set_dict.items():
            sal = dic.get(id_)
            if not sal:
                continue
            esp = orig['upos']
            obt = sal.get('upos', [])
            difs = [(k, a, b) for k, (a, b) in enumerate(zip(esp, obt)) if a != b]
            if difs:
                filas.append((id_, orig['oracion'], difs, sal.get('tokens')))
        filas.sort(key=lambda x: -len(x[2]))
        return filas

    for nombre, dic in (('spaCy', spacy_dict), ('HuggingFace', hf_dict)):
        lin.append(f"## {nombre} — errores UPOS por oración\n")
        filas = _errores_upos(nombre, dic)
        for id_, oracion, difs, tokens in filas:
            lin.append(f"- **{id_}**: `{oracion}`")
            partes = []
            for k, esp, obt in difs:
                tok = tokens[k] if tokens and k < len(tokens) else '?'
                partes.append(f"{tok}: {esp}→{obt}")
            lin.append(f"  - {' · '.join(partes)}")
        lin.append("")

    for nombre, dic in llms_dict.items():
        lin.append(f"## {nombre} — aceptación\n")
        for id_, tipo, oracion in m['aceptacion'][nombre]['detalle']:
            lin.append(f"- **{id_} [{tipo}]**: `{oracion}`")
        lin.append("")

    ruta.write_text("\n".join(lin), encoding='utf-8')


def _generar_graficas(m):
    """Genera gráficas PNG con matplotlib. No es imprescindible: si falta la
    librería, se emite una advertencia y se continúa."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[graficas] matplotlib no disponible: {e}")
        return
    GRAFICAS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Exactitud UPOS por nivel y sistema — barras agrupadas.
    sistemas = list(m['exactitud_upos'][1].keys())
    niveles = [1, 2, 3, 'total']
    import numpy as np
    x = np.arange(len(niveles))
    ancho = 0.8 / max(1, len(sistemas))
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, sys_ in enumerate(sistemas):
        valores = [m['exactitud_upos'][n][sys_]['exactitud'] * 100 for n in niveles]
        ax.bar(x + i*ancho, valores, ancho, label=sys_)
    ax.set_xticks(x + (len(sistemas)-1)*ancho/2)
    ax.set_xticklabels([str(n) for n in niveles])
    ax.set_ylabel('Exactitud UPOS (%)')
    ax.set_title('Exactitud UPOS por nivel y sistema')
    ax.set_ylim(0, 100)
    ax.legend()
    fig.tight_layout()
    fig.savefig(GRAFICAS_DIR / 'upos_por_nivel.png', dpi=140)
    plt.close(fig)

    # 2) UAS y LAS por nivel.
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, (sys_, color) in enumerate([('parser', 'C0'), ('spacy', 'C1')]):
        uas = [(m['uaslas'][sys_][n]['uas'] / m['uaslas'][sys_][n]['total'] * 100)
               if m['uaslas'][sys_][n]['total'] else 0 for n in niveles]
        las = [(m['uaslas'][sys_][n]['las'] / m['uaslas'][sys_][n]['total'] * 100)
               if m['uaslas'][sys_][n]['total'] else 0 for n in niveles]
        ax.bar(x + i*0.4 - 0.2, uas, 0.18, label=f'{sys_} UAS', color=color)
        ax.bar(x + i*0.4, las, 0.18, label=f'{sys_} LAS', color=color, alpha=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in niveles])
    ax.set_ylabel('UAS / LAS (%)')
    ax.set_title('UAS y LAS por nivel — parser vs spaCy')
    ax.set_ylim(0, 100)
    ax.legend()
    fig.tight_layout()
    fig.savefig(GRAFICAS_DIR / 'uas_las_por_nivel.png', dpi=140)
    plt.close(fig)

    # 3) Aceptación parser por nivel.
    por_niv = m['aceptacion_niveles'].get('parser', {})
    if por_niv:
        pres, cobs, recs = [], [], []
        for n in (1, 2, 3):
            p, c, r = _precision_cobertura_rechazo(por_niv[n])
            pres.append(0 if p != p else p * 100)
            cobs.append(0 if c != c else c * 100)
            recs.append(0 if r != r else r * 100)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(np.arange(3) - 0.25, pres, 0.25, label='Precisión')
        ax.bar(np.arange(3), cobs, 0.25, label='Cobertura')
        ax.bar(np.arange(3) + 0.25, recs, 0.25, label='Rech. correcto')
        ax.set_xticks(np.arange(3))
        ax.set_xticklabels(['Nivel 1', 'Nivel 2', 'Nivel 3'])
        ax.set_ylabel('%')
        ax.set_ylim(0, 105)
        ax.set_title('Aceptación del parser por nivel')
        ax.legend()
        fig.tight_layout()
        fig.savefig(GRAFICAS_DIR / 'aceptacion_parser.png', dpi=140)
        plt.close(fig)

    # 4) Matrices de confusión UPOS (spaCy, HF).
    for nombre, conf in (('spacy', m['conf_spacy']), ('hf', m['conf_hf'])):
        etiquetas = sorted({e for p in conf for e in p})
        if not etiquetas:
            continue
        mat = np.zeros((len(etiquetas), len(etiquetas)), dtype=int)
        for (esp, obt), c in conf.items():
            mat[etiquetas.index(esp), etiquetas.index(obt)] = c
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(mat, cmap='Blues')
        ax.set_xticks(range(len(etiquetas)))
        ax.set_yticks(range(len(etiquetas)))
        ax.set_xticklabels(etiquetas, rotation=45, ha='right')
        ax.set_yticklabels(etiquetas)
        ax.set_xlabel('Obtenido')
        ax.set_ylabel('Esperado')
        ax.set_title(f'Matriz de confusión UPOS — {nombre}')
        for i in range(len(etiquetas)):
            for j in range(len(etiquetas)):
                if mat[i, j]:
                    ax.text(j, i, str(mat[i, j]), ha='center', va='center',
                            color='white' if mat[i, j] > mat.max()/2 else 'black',
                            fontsize=8)
        fig.colorbar(im, ax=ax, shrink=0.8)
        fig.tight_layout()
        fig.savefig(GRAFICAS_DIR / f'confusion_{nombre}.png', dpi=140)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Punto de entrada.
# ---------------------------------------------------------------------------

def _main(argv):
    set_dict = _leer_set()
    parser_dict = _leer_jsonl(RESULTS_DIR / 'parser.jsonl')
    spacy_dict = _leer_jsonl(RESULTS_DIR / 'spacy.jsonl')
    hf_dict = _leer_jsonl(RESULTS_DIR / 'hf.jsonl')
    llms_dict = _leer_llm()

    if not parser_dict:
        print("ERROR: no se encontró fase2/resultados/parser.jsonl. "
              "Genéralo con: python fase2/parser_es.py --entrada "
              "fase2/pruebas/oraciones.jsonl --salida "
              "fase2/resultados/parser.jsonl", file=sys.stderr)
        return 1

    m = calcular(set_dict, parser_dict, spacy_dict, hf_dict, llms_dict)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _escribir_csv(m, RESULTS_DIR / 'metricas.csv')
    _escribir_markdown(m, RESULTS_DIR / 'metricas.md')
    _escribir_errores(set_dict, m, RESULTS_DIR / 'errores.md',
                      parser_dict, spacy_dict, hf_dict, llms_dict)
    _generar_graficas(m)
    print(f"Métricas escritas en: {RESULTS_DIR}")
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
