# Proyecto de Teoría de Lenguajes

| Integrantes |
|---|
| Mejía Oliva, David Ernesto. |
| Nativí Claude, Luís Alejandro. |
| Osegueda Hernández, Graciela María. |
| Umanzor Velásquez, Rodrigo. |
| Valdes Jacobo, José Andrés. |

Analizador léxico (Fase 1), sintáctico (Fase 2) y semántico (Fase 3) para un
subconjunto de C++ orientado a programación competitiva.

La especificación completa de tokens está en
[docs/especificacion_tokens.md](docs/especificacion_tokens.md).

[Enlace al video](https://ucaedusv-my.sharepoint.com/:v:/g/personal/00087022_uca_edu_sv/IQBtFSWluIBSR6J_OcBQ33USAdyeNjl2MpOg58hy-b0JYw4?e=0phBrP)

## Lexer

La Fase 1 implementa el analizador léxico en [lexer.py](lexer.py).

### Cómo ejecutarlo

```bash
python lexer.py pruebas/lexer/valido_basico.cpp
```

Imprime una tabla alineada con las columnas `Tipo | Lexema | Línea | Col` y,
debajo, la lista de errores léxicos encontrados (o `Sin errores léxicos` si
no hubo ninguno). Un token `EOF` cierra siempre la tabla.

Como módulo de Python:

```python
from lexer import tokenizar
tokens, errores = tokenizar(codigo_fuente)
```

Donde `tokens` es una lista de `Token(tipo, lexema, linea, columna, valor)` y
`errores` una lista de `ErrorLexico(mensaje, linea, columna)`.

### Cómo correr las pruebas

```bash
pip install pytest
pytest -v
```

Los 25 tests de [test_lexer.py](test_lexer.py) cubren:

- Los 21 tokens exactos del ejemplo de la sección *Ejemplo de tokenización*.
- Los 3 errores exactos del ejemplo con errores.
- Los dos archivos válidos de [pruebas/](pruebas/) (`valido_basico.cpp` y
  `valido_structs.cpp`).
- Cada uno de los 10 errores léxicos, con su línea, columna y mensaje.
- Casos de borde: `int` vs `intx`, `1e9` y `1LL` vs `123abc`, `.5` como
  `LIT_FLOAT` frente a `a.size()` como `OP_PUNTO`, los tres niveles de `<`,
  `<<` y `<<=`, `->` vs `--` vs `-=`, `vector<vector<int>>` cerrando con
  `OP_SHR`, y un comentario de bloque multilínea seguido de un token (para
  comprobar que la línea y la columna se actualizan bien).

### Resumen de cómo funciona

1. **Tabla de patrones (`PATRONES`).** Es una lista ordenada de pares
   `(nombre_de_tipo, regex)`. El orden sigue la sección *Orden de prioridad y
   casos ambiguos* de la especificación: comentarios, directivas, literales de
   texto, literales numéricos (cada uno con lookahead `(?![\w.])` para que
   `123abc` no se parta en `123` + `abc`), número mal formado, identificador,
   operadores de 3 caracteres, de 2, de 1, espacios y, al final, el carácter
   inválido `.`. La lista está separada de la lógica del motor para que la
   Fase 2 solo tenga que cambiar la tabla.

2. **Expresión regular maestra.** `_MAESTRA` se construye uniendo cada entrada
   como un grupo con nombre `(?P<NOMBRE>regex)`. En Python, la alternancia
   prueba las alternativas en orden y se queda con la primera que coincide.
   Por eso el orden de la lista es parte de la especificación.

3. **Motor (`tokenizar`).** Recorre el código con `re.finditer`. Para cada
   match:

   - Decide qué hacer según `m.lastgroup`: ignorar (espacios, saltos y
     comentarios válidos), emitir un token, o reportar un error.
   - Valida en código los errores 4 a 8 (cadenas y caracteres sin cerrar,
     vacíos, con varios caracteres o con escapes inválidos), que no se pueden
     distinguir solo con la regex.
   - Convierte el valor para los literales (`int`, `float`, el carácter o la
     cadena decodificados, el nombre del archivo en `DIR_INCLUDE`, el nombre
     y el reemplazo en `DIR_DEFINE`).
   - Mantiene línea y columna contando los `'\n'` presentes en cada lexema,
     para que un comentario de bloque de varias líneas actualice bien el
     estado.

4. **Recuperación en modo pánico.** Cada error se reporta con el formato
   `Error léxico [línea L, col C]: <mensaje>`, el motor descarta el lexema
   que falló y sigue. Así una sola corrida muestra todos los errores del
   archivo, como pide la especificación.

### Archivos del proyecto

- [lexer.py](lexer.py) — el analizador léxico.
- [test_lexer.py](test_lexer.py) — pruebas con pytest.
- [pruebas/](pruebas/) — programas de entrada: dos válidos y uno por cada
  uno de los 10 errores léxicos.
- [docs/especificacion_tokens.md](docs/especificacion_tokens.md) — la
  especificación, única fuente de verdad.

## Parser del español — Fase 2

La Fase 2 implementa un analizador sintáctico descendente recursivo LL(1)
para un subconjunto controlado del español. La especificación completa
(24 reglas R1-R24, léxico de 400 formas, 8 reglas semánticas y notación
de árboles con corchetes) está en
[fase2/docs/gramatica_espanol.md](fase2/docs/gramatica_espanol.md).

Archivos de la fase:

- [fase2/lexer_es.py](fase2/lexer_es.py) — lexer que reutiliza el motor de
  la Fase 1 con los patrones `PALABRA`, `COMA`, `PUNTO`, `ESPACIO` y
  `CHAR_INVALIDO`, y el diccionario `LEXICO` de 400 formas.
- [fase2/parser_es.py](fase2/parser_es.py) — parser LL(1), árbol
  (`Nodo`/`Token`), función pública `analizar(oracion, semantico=None)`
  que devuelve `Resultado`, y la CLI.
- [fase2/semantico_es.py](fase2/semantico_es.py) — analizador semántico
  con las 8 reglas C1-C8 del documento.
- [fase2/visualizar_arbol.py](fase2/visualizar_arbol.py) — dibuja el árbol
  en PNG con matplotlib (sin Graphviz).
- [fase2/test_parser_es.py](fase2/test_parser_es.py) y
  [fase2/test_semantico_es.py](fase2/test_semantico_es.py) — pruebas con
  pytest.

### Instalación

```bash
pip install -r requirements.txt
```

### Analizar una oración

```bash
python fase2/parser_es.py "El perro negro come manzanas."
```

Imprime los tokens con su categoría, la decisión de aceptación (o los
errores con su columna), el árbol en corchetes y el árbol dibujado con
`nltk.pretty_print`.

Para guardar también el árbol como imagen:

```bash
python fase2/parser_es.py "Ana no compró los libros del profesor ayer." --png fase2/arbol_ejemplo.png
```

### Modo lote (JSON Lines)

```bash
python fase2/parser_es.py --entrada fase2/pruebas/oraciones.jsonl \
                         --salida  fase2/resultados/parser.jsonl
```

Lee una oración por línea (campo `oracion`, opcional `id`) y escribe un
registro JSON por línea con `id, aceptada, etapa, mensajes, categorias,
arbol`, en el formato de la sección *Formato del set de prueba y de la
salida* del documento.

### Correr las pruebas

```bash
pytest fase2/test_parser_es.py fase2/test_semantico_es.py -v
```

Las pruebas del parser verifican el conteo exacto del léxico (400 formas,
con los sub-totales por categoría), los 4 árboles canónicos del documento,
los casos de la tabla del nivel 3 (aceptaciones y rechazos con la columna
del token que falla) y una selección de casos de cobertura (sujeto
tácito, coordinación con comas, `al`/`del`, atributo SN, OD sin
determinante, ADJ antes del SUST, negación, los tres tiempos verbales y
una oración sin punto final).

### Analizador semántico

[fase2/semantico_es.py](fase2/semantico_es.py) recorre el árbol que
produce el parser y aplica las 8 reglas de la sección "Concordancia y
restricciones del semántico" del documento. Si no hubo errores léxicos
ni sintácticos, devuelve TODOS los errores que encuentra con el formato
`Error semántico [col C]: <mensaje>`.

| # | Regla |
| --- | --- |
| C1 | Dentro del SN, el DET y los ADJ concuerdan en género y número con el SUST (el género `c` acepta `m` y `f`). |
| C2 | `al` y `del` solo van con un nominal masculino singular; `a el` y `de el` deben contraerse. |
| C3 | El verbo (VERBO o COP) concuerda con el sujeto en persona y número (un SN coordinado es plural; persona 1 si incluye `yo` o `nosotros/as`, 2 si incluye `tú`, 3 si no). |
| C4 | El atributo concuerda con el sujeto: un SADJ en género y número; un SN, solo en número (coord. masculino si algún miembro es masculino, femenino solo si todos lo son; sujeto tácito: género libre). |
| C5 | Un verbo intransitivo no lleva OD; uno transitivo lo necesita; `ambos` acepta las dos opciones. |
| C6 | Los pronombres de sujeto no funcionan como OD, y `yo` y `tú` no van después de preposición. |
| C7 | Un sujeto con sustantivo común necesita determinante. |
| C8 | `ayer` (referencia pasado) exige pretérito; `pronto` (futuro) exige futuro. Para las formas con dos tiempos (`caminamos`, `vivimos`), basta con que uno de los tiempos sea compatible. |

El semántico está activado por defecto en la CLI y en el modo lote. En
el modo lote, cada registro de salida añade el campo `regla` con la
lista de reglas que fallaron (o `null` si no hubo errores semánticos).
Para desactivarlo se usa `--sin-semantico`:

```bash
# Con semántico (por defecto):
python fase2/parser_es.py "La casa es blanco."
# ... Rechazada (etapa: semantico):
#   Error semántico [col 12]: el atributo 'blanco' (m. sg.) no concuerda
#   con el sujeto (f. sg.)

# Sin semántico (solo léxico + sintaxis, como la Fase 2 previa al semántico):
python fase2/parser_es.py --sin-semantico "La casa es blanco."
```

Las pruebas del semántico (`fase2/test_semantico_es.py`) cubren:

- Una oración "Correcta" y otra "Con error" por cada regla C1-C8; las
  correctas no dan errores y las erróneas disparan exactamente esa regla.
- Resolución de rasgos del sujeto coordinado (persona 1 con `yo`,
  género masculino si algún miembro lo es, etc.) y del sujeto tácito.
- Tiempos con dos valores (`caminamos` acepta `ayer`).
- Casos del nivel 3 del documento (`Pan come Ana.` → C7, `El perro de
  Ana y Luis come.` → C3).
- Errores dentro de un SP (`Ana camina con la niño.` → C1,
  `Ana camina al casa.` → C2).
- Oración con dos reglas distintas devueltas en orden de aparición.
- Formato y columna correctos de los mensajes.

### Comparación con herramientas de NLP

Comparamos el parser propio con `spaCy` (modelo `es_core_news_lg`,
versión **3.8.0**) y con un etiquetador POS de HuggingFace sobre el mismo
set de 60 oraciones.

> **Nota sobre el modelo de HuggingFace.** La especificación pedía
> `PlanTL-GOB-ES/roberta-base-bne-capitel-pos`, pero ese repositorio fue
> retirado del Hub (devuelve 404) a la fecha del informe (2026-11-25). Se
> usa como reemplazo **`mrm8488/RuPERTa-base-finetuned-pos`**, también
> basado en RoBERTa en español y con `id2label` de UPOS. El único ajuste
> es traducir la etiqueta `O` del modelo a la UPOS `X`, lo documenta
> `fase2/correr_hf.py` cuando arranca.

#### Descargar los modelos (una sola vez)

```bash
python -m spacy download es_core_news_lg
```

El modelo de HuggingFace se descarga automáticamente al correr
`correr_hf.py` (la cache de HuggingFace queda en `~/.cache/huggingface`).

#### Pipeline completo

```bash
# 1) Pruebas del convertidor de árboles a UD.
python fase2/test_ud.py

# 2) Salida del parser propio sobre el set.
python fase2/parser_es.py --entrada fase2/pruebas/oraciones.jsonl \
                          --salida  fase2/resultados/parser.jsonl

# 3) spaCy sobre el mismo set (misma tokenización que el lexer).
python fase2/correr_spacy.py

# 4) HuggingFace.
python fase2/correr_hf.py

# 5) Métricas finales (CSV, Markdown, gráficas PNG y errores cualitativos).
python fase2/metricas.py
```

Los resultados quedan en `fase2/resultados/`:

- `metricas.csv` y `metricas.md` — tablas listas para el informe.
- `graficas/upos_por_nivel.png`, `uas_las_por_nivel.png`,
  `aceptacion_parser.png`, `confusion_spacy.png`, `confusion_hf.png`.
- `errores.md` — cada error con su oración.
- `parser.jsonl`, `spacy.jsonl`, `hf.jsonl` — salidas por oración.

#### Reproducibilidad

- `fase2/correr_spacy.py` y `fase2/correr_hf.py` no usan muestreo: los
  modelos son deterministas al cargarlos en modo `eval()` sin dropout.
- Versiones fijas de los modelos:
  - `es_core_news_lg` 3.8.0.
  - `mrm8488/RuPERTa-base-finetuned-pos` (commit vigente en la cache; se
    puede fijar añadiendo `revision=<sha>` al `from_pretrained` si hace
    falta reproducir exactamente la corrida).

### Experimento con el LLM

Corre un modelo de Anthropic sobre las mismas 60 oraciones del set, en
las condiciones **zero-shot** y **few-shot**, con 3 repeticiones por
oración. Los prompts están en
[fase2/prompts/zero_shot.txt](fase2/prompts/zero_shot.txt) y
[fase2/prompts/few_shot.txt](fase2/prompts/few_shot.txt) (el primero es
el prompt base de la especificación; el segundo añade 6 ejemplos
verificados contra el set y contra `parser_es.py`).

#### Configurar la clave de la API

La clave se lee de la variable de entorno `ANTHROPIC_API_KEY` o, si
existe, del archivo `.env` en la raíz del proyecto (ya está en
`.gitignore`, no se sube al repositorio):

```bash
# .env en la raíz del proyecto
ANTHROPIC_API_KEY=sk-ant-...
```

El modelo por defecto es `claude-haiku-5-5`. No se envían `temperature`,
`top_p` ni `top_k`: todas las corridas usan la configuración por defecto
del modelo. La variación entre respuestas se mide con las 3
repeticiones.

#### Prueba corta (3 oraciones)

```bash
pip install -r requirements.txt
python fase2/correr_llm.py --limite 3
```

Este arranque imprime una línea por llamada (id, tokens, latencia y
costo), guarda el log crudo en `fase2/logs/llm/<condicion>.jsonl` y el
resultado por oración en `fase2/resultados/llm_<condicion>.jsonl`. Es
reanudable: al volver a correr, las llamadas ya hechas se saltan.

#### Experimento completo

```bash
python fase2/correr_llm.py                # 60 oraciones × 2 condiciones × 3 reps
python fase2/metricas_llm.py              # métricas, CSV, markdown, gráficas
```

Las métricas quedan en `fase2/resultados/metricas_llm.md`,
`fase2/resultados/metricas_llm.csv`,
`fase2/resultados/errores_llm.md` y
`fase2/resultados/graficas/llm_*.png`. Para cambiar de modelo:

```bash
python fase2/correr_llm.py --modelo claude-sonnet-5-5
```

## Analizador semántico — Fase 3

La Fase 3 está implementada en [semantico.py](semantico.py), basada en
[tabla_simbolos.py](tabla_simbolos.py), **sin modificar `lexer.py`**.

Comprueba declaraciones antes de uso, redeclaraciones por ámbito, compatibilidad
de tipos y gestión de ámbitos; incluye comprobaciones adicionales de funciones,
`struct`, punteros, alias de tipos y operaciones frecuentes de C++ competitivo.

### Prueba rápida

```bash
python semantico.py pruebas/semantico/valido.cpp --tabla
python semantico.py pruebas/semantico/errores_semanticos.cpp
python semantico.py pruebas/semantico/valido.cpp --json
python -m pytest -v
```

### Uso desde Python

```python
from semantico import analizar

resultado = analizar('int x = 3; x = "hola";')
for error in resultado.errores:
    print(error)
# Error semántico [...]: asignación incompatible: 'const char*' a 'int'
```

**Importante:** se usa un lector/agrupador de sentencias, no un parser C++
completo. La biblioteca estándar precargada y las plantillas se soportan como
un subconjunto de reglas, no como todo C++.

Consulta [docs/analizador_semantico.md](docs/analizador_semantico.md)
para arquitectura, reglas, API, limitaciones y ejemplos completos.
