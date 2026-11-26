"""Corre un LLM de Anthropic sobre el set de prueba de la Fase 2.

Para cada oración del set, para cada condición (``zero_shot`` y ``few_shot``)
y para cada repetición (3 por combinación), hace una llamada independiente
a la API de Anthropic (sin historial de conversación) y guarda la respuesta
cruda, los tokens, la latencia y el costo estimado.

El experimento se reanuda: si ya hay un registro para (id, condición,
repetición) en el log, no se vuelve a llamar.

Uso:
    python fase2/correr_llm.py                 # corrida completa
    python fase2/correr_llm.py --limite 3      # solo las primeras 3 oraciones
    python fase2/correr_llm.py --modelo <id>   # cambiar modelo
    python fase2/correr_llm.py --condicion zero_shot  # una sola condición

La clave de la API se lee de ``ANTHROPIC_API_KEY``. Si existe un archivo
``.env`` en la raíz del proyecto con la línea ``ANTHROPIC_API_KEY=...``, se
carga antes de arrancar.

Salidas:
    - fase2/logs/llm/<condicion>.jsonl       (una línea por llamada)
    - fase2/resultados/llm_<condicion>.jsonl (una línea por oración, con
      mayoría de las 3 repeticiones y las 3 respuestas individuales)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


# ---------------------------------------------------------------------------
# Configuración.
# ---------------------------------------------------------------------------

MODELO_DEFAULT = 'claude-haiku-5-5'

# Precio por millón de tokens, por modelo. Precios en USD, para prompts
# de hasta 100 000 tokens. Los nuestros son mucho más cortos, así que el
# tramo barato aplica siempre. Fuente: tabla de la tarea; para modelos no
# listados se usa el mismo precio por defecto y se marca con una nota.
PRECIOS_USD_POR_MTOK = {
    'claude-haiku-5-5':  {'entrada': 0.10, 'salida': 0.50},
    # Alias por si el usuario pasa un id ligeramente distinto.
    'claude-haiku-4-5':  {'entrada': 1.00, 'salida': 5.00},
    'claude-sonnet-5-5': {'entrada': 3.00, 'salida': 15.00},
    'claude-opus-5-5':   {'entrada': 15.00, 'salida': 75.00},
}

CONDICIONES = ('zero_shot', 'few_shot')
REPETICIONES = 3

# Reintentos ante errores transitorios de la API.
REINTENTOS_MAX = 6
ESPERA_BASE_SEG = 2.0

RUTA_PROMPTS = _RAIZ / 'fase2' / 'prompts'
RUTA_SET = _RAIZ / 'fase2' / 'pruebas' / 'oraciones.jsonl'
RUTA_LOG = _RAIZ / 'fase2' / 'logs' / 'llm'
RUTA_RES = _RAIZ / 'fase2' / 'resultados'


# ---------------------------------------------------------------------------
# Lectura de archivos auxiliares.
# ---------------------------------------------------------------------------

def _cargar_dotenv(ruta: Path) -> None:
    """Carga pares ``CLAVE=valor`` de un ``.env`` en ``os.environ`` sin
    pisar variables ya definidas. Implementación mínima para no agregar
    dependencias."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, _, valor = linea.partition('=')
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def _leer_set() -> list[dict]:
    """Lee ``pruebas/oraciones.jsonl`` en orden."""
    out = []
    with RUTA_SET.open(encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            out.append(json.loads(linea))
    return out


def _leer_prompt(condicion: str) -> str:
    """Lee la plantilla del prompt para una condición."""
    ruta = RUTA_PROMPTS / f'{condicion}.txt'
    return ruta.read_text(encoding='utf-8')


# ---------------------------------------------------------------------------
# Log de llamadas (reanudable).
# ---------------------------------------------------------------------------

def _leer_log_existente(ruta: Path) -> dict:
    """Devuelve {(id, condicion, repeticion): registro} del log, si existe."""
    out: dict[tuple[str, str, int], dict] = {}
    if not ruta.exists():
        return out
    with ruta.open(encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            clave = (r['id'], r['condicion'], r['repeticion'])
            out[clave] = r
    return out


def _escribir_log(ruta: Path, registro: dict) -> None:
    """Anexa un registro al log, con escritura atómica línea a línea."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open('a', encoding='utf-8') as f:
        f.write(json.dumps(registro, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# Llamada a la API con reintentos exponenciales.
# ---------------------------------------------------------------------------

def _crear_cliente():
    """Importa anthropic solo cuando hace falta (evita romper si no está)."""
    try:
        import anthropic  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            'Falta el paquete "anthropic". Instala con: pip install anthropic'
        ) from e
    clave = os.environ.get('ANTHROPIC_API_KEY')
    if not clave:
        raise SystemExit(
            'Falta ANTHROPIC_API_KEY. Definila en el entorno o en un .env '
            'en la raíz del proyecto.'
        )
    return anthropic.Anthropic(api_key=clave), anthropic


def _llamar_con_reintentos(cliente, mod_anthropic, modelo: str, prompt: str):
    """Hace una llamada a Messages. Reintenta con espera exponencial ante
    errores de red, 429 (rate limit) y 5xx."""
    retriables = (
        mod_anthropic.APIConnectionError,
        mod_anthropic.APITimeoutError,
        mod_anthropic.RateLimitError,
        mod_anthropic.InternalServerError,
    )
    intento = 0
    while True:
        intento += 1
        t0 = time.perf_counter()
        try:
            resp = cliente.messages.create(
                model=modelo,
                # Los modelos "thinking" de la familia Claude 5 consumen
                # tokens de salida en razonamiento interno; con 1024 la
                # respuesta queda truncada antes de emitir el JSON. 8192
                # deja margen cómodo para el razonamiento y el objeto final.
                max_tokens=8192,
                messages=[{'role': 'user', 'content': prompt}],
            )
            latencia = time.perf_counter() - t0
            return resp, latencia
        except retriables as e:
            if intento >= REINTENTOS_MAX:
                raise
            # Espera exponencial con jitter para no pegarle sincronizado.
            espera = ESPERA_BASE_SEG * (2 ** (intento - 1))
            espera += random.uniform(0, 0.5)
            print(f'  [reintentando {intento}/{REINTENTOS_MAX}] '
                  f'{type(e).__name__}: {e}. Espero {espera:.1f}s.',
                  file=sys.stderr)
            time.sleep(espera)


def _extraer_texto(resp) -> str:
    """Concatena los bloques de texto de la respuesta."""
    partes = []
    for bloque in resp.content:
        tipo = getattr(bloque, 'type', None)
        if tipo == 'text':
            partes.append(bloque.text)
    return ''.join(partes)


def _costo_usd(modelo: str, tokens_in: int, tokens_out: int) -> float:
    """Costo estimado para una llamada. Devuelve 0 si el modelo no está en
    la tabla de precios (ya se avisó al arrancar)."""
    tabla = PRECIOS_USD_POR_MTOK.get(modelo)
    if not tabla:
        return 0.0
    return (tokens_in * tabla['entrada'] + tokens_out * tabla['salida']) / 1_000_000


# ---------------------------------------------------------------------------
# Interpretación de la respuesta como JSON.
# ---------------------------------------------------------------------------

CAMPOS_REQUERIDOS = ('aceptada', 'etapa', 'mensajes', 'categorias', 'arbol')


def _interpretar_respuesta(texto: str) -> dict:
    """Devuelve un dict con los 5 campos del formato, o
    ``{'respuesta_invalida': True, 'motivo': '...'}`` si no se puede."""
    # El modelo a veces envuelve el JSON en ```json ... ```. Se tolera.
    texto_limpio = texto.strip()
    if texto_limpio.startswith('```'):
        # Quitar el primer fence.
        texto_limpio = texto_limpio.split('\n', 1)[-1] if '\n' in texto_limpio else texto_limpio
        if texto_limpio.endswith('```'):
            texto_limpio = texto_limpio[:-3]
        texto_limpio = texto_limpio.strip()
        if texto_limpio.startswith('json\n'):
            texto_limpio = texto_limpio[5:]
    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError as e:
        return {'respuesta_invalida': True, 'motivo': f'JSON inválido: {e}'}
    if not isinstance(datos, dict):
        return {'respuesta_invalida': True, 'motivo': 'La respuesta no es un objeto JSON.'}
    faltantes = [c for c in CAMPOS_REQUERIDOS if c not in datos]
    if faltantes:
        return {'respuesta_invalida': True,
                'motivo': f'Faltan campos: {faltantes}'}
    # Normalizar tipos mínimos para evitar sorpresas al agregar.
    if not isinstance(datos['aceptada'], bool):
        return {'respuesta_invalida': True,
                'motivo': "El campo 'aceptada' no es booleano."}
    if datos.get('etapa') not in (None, 'lexico', 'sintactico', 'semantico'):
        return {'respuesta_invalida': True,
                'motivo': f"Valor inválido en 'etapa': {datos.get('etapa')!r}"}
    if not isinstance(datos.get('mensajes'), list):
        return {'respuesta_invalida': True,
                'motivo': "El campo 'mensajes' no es una lista."}
    if not isinstance(datos.get('categorias'), list):
        return {'respuesta_invalida': True,
                'motivo': "El campo 'categorias' no es una lista."}
    if datos.get('arbol') is not None and not isinstance(datos.get('arbol'), str):
        return {'respuesta_invalida': True,
                'motivo': "El campo 'arbol' no es cadena ni null."}
    return {
        'respuesta_invalida': False,
        'aceptada': datos['aceptada'],
        'etapa': datos.get('etapa'),
        'mensajes': datos['mensajes'],
        'categorias': datos['categorias'],
        'arbol': datos.get('arbol'),
    }


# ---------------------------------------------------------------------------
# Agregación por oración (mayoría sobre las 3 repeticiones).
# ---------------------------------------------------------------------------

def _mayoria_por_oracion(registros: list[dict], id_: str) -> dict:
    """Combina las N repeticiones en el registro final para ``llm_*.jsonl``,
    con el mismo formato que ``resultados/parser.jsonl``.

    Decisión por mayoría sobre el par (aceptada, etapa). Las respuestas
    inválidas se cuentan para romper empates, pero no ganan una votación
    por sí solas: si ``inválida`` queda en el top junto a una válida, se
    prefiere la válida.
    """
    reps = [r['interpretacion'] for r in registros]
    claves = []
    for interp in reps:
        if interp.get('respuesta_invalida'):
            claves.append(('invalida', None))
        else:
            claves.append((bool(interp['aceptada']), interp.get('etapa')))
    conteo = Counter(claves)
    # Preferir una clave válida si empata con una inválida.
    orden = sorted(conteo.items(),
                   key=lambda kv: (-kv[1], kv[0][0] == 'invalida'))
    (dec_ganadora, etapa_ganadora), _ = orden[0]

    # Buscar un representante de la decisión ganadora para heredar
    # categorias/arbol/mensajes.
    representante = None
    for r, interp in zip(registros, reps):
        if interp.get('respuesta_invalida'):
            es_inv = True
            clave = ('invalida', None)
        else:
            es_inv = False
            clave = (bool(interp['aceptada']), interp.get('etapa'))
        if clave == (dec_ganadora, etapa_ganadora):
            representante = (r, interp, es_inv)
            break

    if representante is None or representante[2]:
        # La mayoría es inválida: dejamos un registro con todo vacío y la
        # bandera ``respuesta_invalida: true``.
        return {
            'id': id_,
            'aceptada': False,
            'etapa': None,
            'mensajes': ['respuesta_invalida'],
            'categorias': [],
            'arbol': None,
            'respuesta_invalida': True,
            'repeticiones': [_resumir_repeticion(r) for r in registros],
        }

    _, interp, _ = representante
    return {
        'id': id_,
        'aceptada': bool(interp['aceptada']),
        'etapa': interp.get('etapa'),
        'mensajes': interp.get('mensajes', []),
        'categorias': interp.get('categorias', []),
        'arbol': interp.get('arbol'),
        'respuesta_invalida': False,
        'repeticiones': [_resumir_repeticion(r) for r in registros],
    }


def _resumir_repeticion(reg: dict) -> dict:
    """Vista compacta de una repetición para el archivo de resultados."""
    interp = reg['interpretacion']
    if interp.get('respuesta_invalida'):
        return {
            'repeticion': reg['repeticion'],
            'respuesta_invalida': True,
            'motivo': interp.get('motivo'),
        }
    return {
        'repeticion': reg['repeticion'],
        'aceptada': interp['aceptada'],
        'etapa': interp.get('etapa'),
        'mensajes': interp.get('mensajes', []),
        'categorias': interp.get('categorias', []),
        'arbol': interp.get('arbol'),
    }


# ---------------------------------------------------------------------------
# Programa principal.
# ---------------------------------------------------------------------------

def correr(condiciones: list[str], modelo: str, limite: int | None):
    _cargar_dotenv(_RAIZ / '.env')
    cliente, mod_anthropic = _crear_cliente()
    if modelo not in PRECIOS_USD_POR_MTOK:
        print(f'[AVISO] no hay precios para "{modelo}": el costo saldrá en 0.',
              file=sys.stderr)

    oraciones = _leer_set()
    if limite is not None:
        oraciones = oraciones[:limite]

    RUTA_LOG.mkdir(parents=True, exist_ok=True)
    RUTA_RES.mkdir(parents=True, exist_ok=True)

    totales = {'llamadas': 0, 'invalidas': 0,
               'tokens_in': 0, 'tokens_out': 0,
               'costo_usd': 0.0, 'latencia_s': 0.0}

    for condicion in condiciones:
        plantilla = _leer_prompt(condicion)
        log_path = RUTA_LOG / f'{condicion}.jsonl'
        hechos = _leer_log_existente(log_path)
        print(f'\n=== Condición: {condicion} '
              f'({len(hechos)} llamadas ya en el log) ===')

        # Acumulador en memoria de las repeticiones por oración para
        # calcular la mayoría al final.
        por_oracion: dict[str, list[dict]] = {}

        for item in oraciones:
            id_ = item['id']
            oracion = item['oracion']
            por_oracion.setdefault(id_, [])
            for rep in range(1, REPETICIONES + 1):
                clave = (id_, condicion, rep)
                if clave in hechos:
                    por_oracion[id_].append(hechos[clave])
                    continue
                prompt = plantilla.replace('{ORACION}', oracion)
                try:
                    resp, latencia = _llamar_con_reintentos(
                        cliente, mod_anthropic, modelo, prompt)
                except Exception as e:
                    print(f'[FALLO] {id_} rep {rep}: {type(e).__name__}: {e}',
                          file=sys.stderr)
                    raise
                texto = _extraer_texto(resp)
                interp = _interpretar_respuesta(texto)
                tokens_in = resp.usage.input_tokens
                tokens_out = resp.usage.output_tokens
                costo = _costo_usd(modelo, tokens_in, tokens_out)
                registro = {
                    'id': id_,
                    'condicion': condicion,
                    'repeticion': rep,
                    'modelo': modelo,
                    'fecha_utc': datetime.now(timezone.utc).isoformat(),
                    'oracion': oracion,
                    'prompt': prompt,
                    'respuesta_cruda': texto,
                    'tokens_entrada': tokens_in,
                    'tokens_salida': tokens_out,
                    'latencia_s': latencia,
                    'costo_usd': costo,
                    'interpretacion': interp,
                }
                _escribir_log(log_path, registro)
                por_oracion[id_].append(registro)

                totales['llamadas'] += 1
                totales['tokens_in'] += tokens_in
                totales['tokens_out'] += tokens_out
                totales['costo_usd'] += costo
                totales['latencia_s'] += latencia
                if interp.get('respuesta_invalida'):
                    totales['invalidas'] += 1

                marca = 'INV' if interp.get('respuesta_invalida') else (
                    'OK ' if interp.get('aceptada') else 'REJ')
                print(f'  [{marca}] {id_} rep{rep}  '
                      f'{tokens_in}→{tokens_out} tok  '
                      f'{latencia:.2f}s  ${costo:.5f}')

        # Guardar el JSONL por oración con la decisión por mayoría.
        res_path = RUTA_RES / f'llm_{condicion}.jsonl'
        with res_path.open('w', encoding='utf-8') as f:
            for item in oraciones:
                id_ = item['id']
                regs = sorted(por_oracion[id_], key=lambda r: r['repeticion'])
                f.write(json.dumps(
                    _mayoria_por_oracion(regs, id_),
                    ensure_ascii=False) + '\n')
        print(f'  Guardado: {res_path.relative_to(_RAIZ)}')

    print('\nResumen:')
    print(f'  Llamadas nuevas: {totales["llamadas"]}')
    print(f'  Respuestas inválidas: {totales["invalidas"]}')
    print(f'  Tokens entrada / salida: '
          f'{totales["tokens_in"]} / {totales["tokens_out"]}')
    print(f'  Costo estimado: ${totales["costo_usd"]:.4f}')
    if totales['llamadas']:
        print(f'  Latencia promedio: '
              f'{totales["latencia_s"]/totales["llamadas"]:.2f}s/llamada')


def _parse_args():
    p = argparse.ArgumentParser(
        description='Experimento LLM — Fase 2 (gramática del español).')
    p.add_argument('--modelo', default=MODELO_DEFAULT,
                   help=f'Modelo de Anthropic (default: {MODELO_DEFAULT}).')
    p.add_argument('--condicion', choices=CONDICIONES + ('ambas',),
                   default='ambas',
                   help='Condición a correr (default: ambas).')
    p.add_argument('--limite', type=int, default=None,
                   help='Solo correr las primeras N oraciones del set.')
    return p.parse_args()


def main():
    args = _parse_args()
    cond = list(CONDICIONES) if args.condicion == 'ambas' else [args.condicion]
    correr(cond, args.modelo, args.limite)


if __name__ == '__main__':
    main()
