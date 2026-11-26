# Hallazgos — Fase 2 (análisis comparativo)

Documento de trabajo con **cifras respaldadas por su fuente**. Las fuentes
aparecen entre corchetes al final de cada viñeta; se refieren a archivos
dentro de `fase2/`. Las tablas se generan automáticamente desde CSV: no se
copian a mano.

Fecha: 2026-11-26.

---

## 1. Resumen de resultados

- Oraciones del set de prueba: **60** [pruebas/oraciones.jsonl].
- Reparto: 20 por nivel; 15 aceptadas + 5 rechazadas por nivel 1 y 2,
  y 3 ambiguas aceptadas + 17 rechazadas por nivel 3 (ver tabla siguiente).
- Exactitud UPOS total por sistema sobre 331 etiquetas:
  parser 100.0 % (289/289 de las oraciones que pasó el lexer),
  spaCy 95.5 % (316/331), HF 53.8 % (178/331) [resultados/metricas.csv,
  bloque "Exactitud UPOS por nivel y sistema", fila total].
- Aceptación (clase positiva = "aceptada"), 60 oraciones, VP = 33, VN = 26,
  FN = 1, FP = 0 para parser, llm-zero_shot y llm-few_shot
  [resultados/metricas.csv, bloque "Aceptación (parser y LLM)"].
- UAS/LAS del parser sobre las 34 oraciones con árbol esperado:
  100.0 % / 100.0 %; spaCy: 96.2 % / 77.6 %
  [resultados/metricas.csv, bloque "UAS y LAS por nivel"].

**Tabla 1 (generada automáticamente)** — métricas principales por sistema y
nivel. Fuente: `resultados/metricas.csv`.

```
Nivel  | UPOS parser | UPOS spaCy | UPOS HF | UPOS LLM-zero | UPOS LLM-few
1      | 100.0%      | 96.5%      | 41.2%   | 100.0%*       | 100.0%*
2      | 100.0%      | 97.4%      | 57.4%   | 99.1%*        | 99.1%*
3      | 100.0%      | 93.1%      | 58.8%   | 91.6%*        | 93.9%*
total  | 100.0%      | 95.5%      | 53.8%   | 96.4%*        | 97.3%*
```
\* El LLM no entrega UPOS para las oraciones que rechaza con etapa `lexico`
o `sintactico`: el 0.0 % de `resultados/metricas.csv` es un cómputo sobre
las 331 etiquetas de UD. La fila "LLM" aquí es la exactitud **entre las
oraciones que el LLM aceptó** y tiene saltadas registradas
[resultados/metricas_llm.csv y resultados/metricas_llm.md, tabla "Exactitud
UPOS y UAS/LAS"].

---

## 2. Robustez

### Desempeño por nivel

- **Parser** — cobertura por nivel: N1 100 %, N2 100 %, N3 75 %; tasa de
  rechazo correcto por nivel: 100 %, 100 %, 100 %
  [resultados/metricas.csv, bloque "Aceptación (parser y LLM)",
  desglose por nivel].
- **spaCy** — UPOS por nivel: N1 96.5 %, N2 97.4 %, N3 93.1 %; sobre 34
  oraciones con árbol esperado, LAS: 77.6 % total y 82.1 % en nivel 3
  [resultados/metricas.csv].
- **HF (RuPERTa-base-finetuned-pos)** — UPOS por nivel: N1 41.2 %,
  N2 57.4 %, N3 58.8 %. El error más frecuente es confundir puntuación con
  SYM (28 casos) [resultados/metricas.csv, bloque "Confusiones UPOS"].
- **LLM** — en nivel 3 queda con 91.6 % (zero-shot) y 93.9 % (few-shot) de
  exactitud UPOS sobre las oraciones que no saltó
  [resultados/metricas_llm.md, tabla 3].

### Experimento de variantes (nuevo)

- 15 variantes, 5 por cada tipo, derivadas de oraciones aceptadas del set
  [analisis/variantes_robustez.jsonl].
- **Parser** acepta el 100 % de las variantes con mayúsculas irregulares,
  0 % de las variantes sin tildes (3 rechazos léxicos + 2 semánticos) y
  0 % de las variantes con una palabra fuera del léxico (5 rechazos
  léxicos) [analisis/robustez.csv].
- **spaCy** mantiene UPOS en 80.0 % (sin tildes), 57.1 % (mayúsculas
  irregulares) y 100.0 % (palabra OOV) [analisis/robustez.csv].
- **HF** mantiene UPOS en 75.0 % (sin tildes), 42.9 % (mayúsculas) y
  82.8 % (palabra OOV) [analisis/robustez.csv].
- El **LLM no se volvió a correr** en las variantes para no gastar más:
  "DATO FALTANTE: aceptación y UPOS del LLM sobre las 15 variantes de
  `analisis/variantes_robustez.jsonl`; obtener con el mismo script y modelo,
  temperatura y prompt, usando `--limite` para limitar el gasto"
  [analisis/robustez.csv, columnas llm_*].

### Qué hace cada sistema con lo que no conoce

- **Parser** → **rechaza** en etapa léxica, con un mensaje que cita la
  palabra: toda palabra fuera de las 400 formas detona un rechazo léxico
  [analisis/robustez.csv, columna parser_rechazo_lexico = 8 de 15].
- **spaCy** → **adivina**: la palabra OOV se etiqueta con la categoría más
  probable del contexto. El caso de "mayúsculas irregulares" baja a 57.1 %
  porque spaCy toma muchas formas por nombres propios [analisis/robustez.csv].
- **HF** → **adivina con alta varianza**: el tokenizador BPE es más
  tolerante a OOV (82.8 %), pero descalabra en mayúsculas irregulares
  (42.9 %) y además inventa etiquetas como SYM y PART en lugar de PUNCT
  [resultados/errores.md, sección HuggingFace].
- **LLM** → **no inventa reglas**: 0 reglas inventadas en 26 rechazos
  correctos (zero_shot y few_shot) [resultados/metricas_llm.md, tabla 7].

---

## 3. Manejo de ambigüedad

- Oraciones del nivel 3 marcadas como ambigüedad estructural: **4 de 60**
  (N3-05, N3-06, N3-17, N3-18) [pruebas/oraciones.jsonl, campo `fenomeno`].
- Desacuerdos de adjunción **parser vs. spaCy**: **1 de 60** (N3-05
  "Ana mira al niño con el libro." — el parser pone `obl`, spaCy pone `obj`)
  [resultados/metricas.md, tabla 5].
- **Respeto de R12 por el LLM** (unir `de`/`del` al sustantivo cuando le
  sigue a un SN):
  zero_shot 4/4 = 100.0 %;
  few_shot 3/4 = 75.0 % (1 indeciso)
  [resultados/metricas_llm.md, tabla 6; resultados/metricas_llm.csv].
- El parser resuelve la ambigüedad con una regla fija ("pegar al
  sustantivo"), por lo que produce una sola lectura aun cuando existan dos
  válidas [docs/gramatica_espanol.md, sección "El conflicto de R12 y su
  resolución"].

---

## 4. Escalabilidad

### Tiempo del parser frente a la longitud en tokens

- Mediciones por longitud, medianas sobre 15 repeticiones
  [analisis/escalabilidad_tiempo.csv]:
  - 2 tokens (N1-06 "Correremos."): 0.0041 ms.
  - 5 tokens (N1-01): 0.0109 ms.
  - 10 tokens (coord-4): 0.0157 ms.
  - 16 tokens (coord-8): 0.0151 ms.
  - 30 tokens (coord-16): 0.0268 ms.
  - 50 tokens (de-16): 0.0507 ms.
- El crecimiento es **aproximadamente lineal** en la longitud: pasar de
  10 a 50 tokens multiplica el tiempo por ~3.2 (0.0157 → 0.0507 ms).
  Es coherente con un parser LL(1) descendente recursivo, cuyo costo es
  O(n) tokens [analisis/escalabilidad_tiempo.csv].
- Gráfica: `analisis/graficas/escalabilidad_tiempo.png`.

### Tamaño de la gramática si la concordancia estuviera en la CFG

- Si C1, C3 y C4 se expresaran dividiendo los no-terminales por género
  (m, f), número (sg, pl) y persona (1, 2, 3):
  **120 reglas** en lugar de 24, un factor 5× [analisis/gramatica_concordancia_resumen.csv].
- Método de conteo (comentado en `medir_escalabilidad.py`,
  función `estimar_reglas_cfg_concordancia`):
  - Reglas "nominales" (SNS, NOMINAL, NUCLEO_N, ADJS, SADJ, COMP_N, SP_DE,
    SN, SUJ, OD, ATRIB, SP, R3-R13 + R18-R19 + R23): ×4 variantes
    (género×número) por C1.
  - Regla R14 (SV): ×6 variantes (persona×número) por C3.
  - Reglas R1 (O) y R17 (PRED): ×24 variantes (interfaz SUJ↔SV, SUJ↔ATRIB).
  - R20 (ATRIB): ×4 por C4.
  - Reglas que no tocan concordancia (R2 FIN, R15 MOD_PRE, R16 NEG_OPC, R21
    CCS, R22 CC, R24 SADV): sin copia.
- La factorización se vuelve incluso **mayor** cuando se incorpora la
  coordinación: *Ana y Luis* mezcla géneros y hay que enumerar todas las
  combinaciones de miembros. Esto se marca como argumento cualitativo del
  informe [docs/gramatica_espanol.md, sección "Por qué estas reglas no van
  en la CFG"].

---

## 5. Costo computacional

**Tabla 2 (generada)** — costo computacional y de ampliación. Fuentes:
`resultados/metricas.csv` (tiempos), `analisis/costo_ampliacion.csv`
(tamaños y tokens), `resultados/metricas_llm.csv` (costo LLM).

| Enfoque           | Tiempo por oración | Tamaño en disco | Tokens / Costo |
| ----------------- | ------------------ | --------------- | -------------- |
| Parser            | 0.0 ms*            | 0.04 MB         | — |
| spaCy (news_lg)   | 3.0 ms             | 602.0 MB        | — |
| HF (RuPERTa)      | 18.8 ms            | 962.7 MB        | — |
| LLM zero_shot     | — (6.15 s/call†)   | —               | 2 192 tok in, 180 llamadas, $0.1605 |
| LLM few_shot      | — (4.45 s/call†)   | —               | 3 201 tok in, 180 llamadas, $0.1429 |

\* El tiempo del parser que reporta `metricas.csv` es 0.000000 s con la
precisión del script original; `analisis/escalabilidad_tiempo.csv` lo mide
en microsegundos por oración (mediana 0.011 ms para 5 tokens).
† Latencia promedio por llamada, no por oración (hay 3 repeticiones por
oración × 60 oraciones = 180 llamadas en cada condición).

- Costo total del experimento con el LLM: **970 854 tokens de entrada,
  412 645 de salida, $0.3034** [resultados/metricas_llm.md, final].
- Tokens de prompt promedio por llamada: zero_shot 2 192.3, few_shot 3 201.3
  [analisis/costo_ampliacion.csv].

---

## 6. Comportamiento del LLM frente a las reglas formales

- **Desviación hacia el español general** (oraciones gramaticales del nivel
  3 que la CFG rechaza y el LLM acepta): **0/16 (0.0 %)** en ambas
  condiciones [resultados/metricas_llm.md, tabla 5]. El LLM se mantiene
  dentro de la gramática formal.
- **Errores de formato** (JSON no parseable): 0/60 en ambas condiciones
  [resultados/metricas_llm.md, tabla 8].
- **Reglas inventadas** (que no existan en R1-R24 ni en C1-C8):
  0/26 rechazos en cada condición [resultados/metricas_llm.md, tabla 7].
- **Cita de la regla correcta al rechazar**: 14/26 (53.8 %) en ambas
  condiciones [resultados/metricas_llm.md, tabla 7].
- **Consistencia entre 3 repeticiones**: zero_shot 55/60 = 91.7 %;
  few_shot 60/60 = 100.0 % [resultados/metricas_llm.md, tabla 9].
- **McNemar zero vs. few**: b=0, c=0, p=1.0000. Diferencia no significativa
  al 5 % [resultados/metricas_llm.md, tabla 10]. **Resultado débil**:
  el estadístico es trivial; con un set tan pequeño no hay sensibilidad
  para detectar diferencias.
- **Coincidencia exacta del árbol** (una señal cualitativa de mejora entre
  condiciones): zero_shot 25/34 = 73.5 %, few_shot 30/34 = 88.2 %
  [resultados/metricas_llm.md, tabla 4].
- **Ejemplos textuales** (fuente: `logs/llm/zero_shot.jsonl`,
  `logs/llm/few_shot.jsonl`):
  1. Rechazo correcto con cita de regla (N3-01, zero_shot, rep 1):
     "Rechazo sintáctico: 'Ayer' (ADV→SADV) solo puede ocupar la posición
     inicial de SV como MOD_PRE (R14, R15, R24). Tras él, la regla R17
     exige VERBO o COP para PRED..." [logs/llm/zero_shot.jsonl, id N3-01].
  2. Rechazo correcto por R12 (N3-04, zero_shot, rep 1): "...En R12,
     COMP_N solo elige SP_DE cuando viene PREP_DE o CONTR_DE, y 'sobre' es
     PREP, así que COMP_N → ε y NUCLEO_N termina (R9)..."
     [logs/llm/zero_shot.jsonl, id N3-04].
  3. Rechazo léxico (N3-11, zero_shot): "Rechazo léxico: la palabra
     'respectivamente' no está en el léxico, y según el léxico toda palabra
     ausente es un rechazo léxico. El análisis se detiene en esta etapa."
     [logs/llm/zero_shot.jsonl, id N3-11].
  4. Error de etiquetado (aceptación correcta, árbol fuera de formato;
     N3-06, zero_shot): envuelve `NPROP María` sin el `SN` intermedio que
     exige el formato del documento [logs/llm/zero_shot.jsonl, id N3-06;
     resultados/errores_llm.md, sección zero_shot "Errores de etiquetado"].
  5. Error de etiquetado (N2-15, zero_shot): el árbol se cierra sin
     `PUNTO` (la oración original no lo trae y el LLM deja fuera el nodo)
     [resultados/errores_llm.md, sección zero_shot].

---

## 7. Dónde falla la CFG — fenómenos del nivel 3

Para cada fenómeno declarado en el set:

- **Adverbio al inicio con sujeto explícito** (*Ayer Ana comió pan.*) —
  Parser: rechazo sintáctico (esperado). spaCy: etiqueta UPOS casi perfecto,
  pero marca `cocina/comió` como PROPN en varios casos del nivel 3. HF: muy
  mal (ver `resultados/errores.md`, N3-02 etc.). **Falla formal**: orden de
  palabras libre, que la CFG fijó para mantener LL(1) [docs/gramatica_espanol.md,
  sección "Fenómenos fuera de la gramática"].
- **Orden OVS** (*Pan come Ana.*): parser acepta sintaxis, rechaza con C7
  (sust. común sin determinante) [pruebas/oraciones.jsonl, N3-03]. **Falla
  formal**: una CFG no distingue sin rasgos semánticos sujeto de objeto.
- **SP distinto de `de` junto a sustantivo** (*El libro sobre la mesa es
  nuevo.*): rechazo sintáctico en `sobre` [pruebas/oraciones.jsonl, N3-04].
  **Falla formal**: la regla R12 limita qué SP se adjunta al sustantivo,
  precio de resolver el conflicto LL(1).
- **Ambigüedad de adjunción** (N3-05, N3-17): aceptada; el parser produce
  una sola lectura [docs/gramatica_espanol.md, tabla de fenómenos].
  **Falla formal**: ambigüedad estructural, inherente a las CFG; se requiere
  información léxica o semántica externa.
- **Ambigüedad con `de`** (N3-06, N3-18): aceptada con regla fija de R12.
  **Falla formal**: la lectura alternativa se pierde.
- **Coordinación dentro de SP** (*El perro de Ana y Luis come.*): el parser
  la analiza como *[el perro de Ana] y [Luis]*; C3 la rechaza por sujeto
  plural [pruebas/oraciones.jsonl, N3-07]. **Falla formal**: la CFG no
  produce la lectura *de [Ana y Luis]*.
- **Coordinación de oraciones** (*Ana come y Luis bebe.*): rechazo
  sintáctico. **Falla formal**: la regla R4 solo coordina SN.
- **Negación con adverbio** (*Ana no siempre come pan.*): rechazo
  sintáctico. **Falla formal**: el orden de MOD_PRE y NEG_OPC es fijo
  (R14, R15, R16).
- **Intensificador de adverbio** (*Ana come pan muy rápidamente.*): rechazo
  sintáctico en `rápidamente`. **Falla formal**: R11 solo acepta INTENS
  modificando ADJ, no ADV.
- **Dependencias cruzadas** (*Ana, Luis y Sofía son alta, alto y alta,
  respectivamente.*): rechazo léxico por `respectivamente` + imposibilidad
  de encajar el patrón con la gramática. **Falla formal**: en general
  ninguna CFG genera dependencias cruzadas x₁x₂x₃y₁y₂y₃ [Shieber 1985;
  docs/gramatica_espanol.md, sección "Por qué estas reglas no van en la
  CFG"].

**Conexión con la jerarquía de Chomsky** (argumentación cualitativa desde
la gramática):
- Concordancia local (C1, C3, C4) es expresable en una CFG pero multiplica
  el tamaño por **5×** — ver §4 [analisis/gramatica_concordancia_resumen.csv].
- Dependencias cruzadas con número variable de miembros (*respectivamente*)
  **no** son expresables por una CFG; se necesita al menos una gramática
  débilmente sensible al contexto [argumento documental, no medido].

---

## 8. Aplicabilidad práctica

- Si se necesita **verificación formal de un subconjunto cerrado** del
  español (lingüística computacional, verificación gramatical pedagógica),
  conviene **CFG + semántico**, porque el parser logra 100 % UPOS, 97.1 %
  cobertura, 100 % rechazo correcto y rechaza por una regla explícita que se
  puede señalar al usuario [resultados/metricas.csv].
- Si se necesita **etiquetado UPOS sobre texto abierto** y robusto a
  ortografía imperfecta, conviene **spaCy (`es_core_news_lg`)**, porque
  mantiene 80 % y 100 % en variantes "sin tildes" y "OOV"
  [analisis/robustez.csv], con 3.0 ms por oración y 602 MB en disco
  [resultados/metricas.csv].
- Si se necesita **explicabilidad** del rechazo con cita a la regla
  violada, conviene **LLM con el prompt formal + few-shot**, porque
  consigue 100 % consistencia entre repeticiones y 0 reglas inventadas,
  a un costo total de $0.14 por 180 llamadas
  [resultados/metricas_llm.md].
- **No conviene** HuggingFace `RuPERTa-base-finetuned-pos` para este
  dominio: 53.8 % UPOS total, 28 confusiones puntuación→SYM y 18.8 ms/oración
  con 962.7 MB en disco [resultados/metricas.csv].

---

## 9. Amenazas a la validez

- **Tamaño del set** (60 oraciones) — las comparaciones de aceptación
  descansan en 34 positivos y 26 negativos; una McNemar con b=c=0 no tiene
  potencia para detectar diferencias [resultados/metricas_llm.md, tabla 10].
  Afecta a: §6 (zero vs few) y §3 (desacuerdos de adjunción, n=1).
- **Set construido por el mismo equipo** que diseñó la gramática — el
  parser puede estar sobreajustado a los fenómenos elegidos. Afecta a
  todas las métricas de aceptación.
- **Un solo modelo de LLM** (`claude-haiku-5-5`) y temperatura no reportada
  (`temperatura: None` en los logs) [logs/llm/zero_shot.jsonl]. Afecta a §6.
- **Tokenización forzada en spaCy y HF**: ambos reciben las palabras ya
  partidas por el lexer o por el fallback de puntuación; esto retira a los
  modelos el punto de decisión de segmentación [correr_spacy.py, docstring].
  Afecta a §2 y §5.
- **Modelo HF usado como reemplazo** (`RuPERTa-base-finetuned-pos`) porque
  `PlanTL-GOB-ES/roberta-base-bne-capitel-pos` fue retirado
  [correr_hf.py, docstring]. Afecta a §2 (HF).
- **UPOS 0 % del LLM** en `resultados/metricas.csv` — refleja cómo se
  calculó (sobre las 331 etiquetas de UD esperadas, el LLM solo entrega
  UPOS cuando acepta y aún con UPOS que son categorías del lexer, no UD).
  La comparación correcta vive en `resultados/metricas_llm.csv`. Afecta a
  §1 y §2.
- **Experimento de robustez**: 15 variantes es poco; la diferencia parser
  0 % / spaCy 80 % en "sin tildes" es dramática pero cae en 5 casos. Afecta
  a §2.
- **El LLM no se corrió sobre las variantes de robustez** [analisis/
  robustez.csv, columnas llm_*]. Afecta a §2.

---

## 10. Inventario de figuras y tablas

Las figuras ya existentes están en `fase2/resultados/graficas/`; las nuevas
en `fase2/analisis/graficas/`.

| Ruta | Qué muestra | Sección del informe |
| --- | --- | --- |
| resultados/graficas/upos_por_nivel.png            | UPOS por nivel y sistema                 | 8 Resultados / 9 Análisis |
| resultados/graficas/uas_las_por_nivel.png         | UAS y LAS por nivel (parser y spaCy)    | 8 Resultados |
| resultados/graficas/aceptacion_parser.png         | Aceptación del parser por nivel         | 8 Resultados |
| resultados/graficas/confusion_spacy.png           | Matriz de confusión UPOS de spaCy       | 9 Análisis comparativo |
| resultados/graficas/confusion_hf.png              | Matriz de confusión UPOS de HF          | 9 Análisis comparativo |
| resultados/graficas/llm_aceptacion_por_nivel.png  | Aceptación del LLM por nivel            | 10 Comportamiento del LLM |
| resultados/graficas/llm_desviacion_por_nivel.png  | Desviación del LLM por nivel            | 10 Comportamiento del LLM |
| resultados/graficas/llm_metricas_globales.png     | Métricas globales del LLM                | 10 Comportamiento del LLM |
| analisis/graficas/escalabilidad_tiempo.png        | Tiempo del parser vs. longitud          | 8 Resultados / 9 Escalabilidad |
| analisis/graficas/robustez_aceptacion.png         | Aceptación del parser por tipo variante | 9 Robustez |
| analisis/graficas/robustez_upos.png               | UPOS por sistema y tipo de variante     | 9 Robustez |

Tablas numeradas que se usarán en el informe:

| # | Fuente CSV | Descripción |
| --- | --- | --- |
| 1 | resultados/metricas.csv | Métricas principales por sistema y nivel |
| 2 | varias (ver §5)         | Costo computacional por enfoque |
| 3 | analisis/robustez.csv   | Robustez a variantes ortográficas y OOV |
| 4 | analisis/gramatica_concordancia_resumen.csv | Crecimiento de la CFG con concordancia |
| 5 | resultados/metricas_llm.csv | Zero-shot vs few-shot |

---

## Apéndice: verificación

La verificación se corre con `python -m fase2.analisis.verificar_hallazgos`.
Las cifras citadas aquí se vuelven a calcular desde los CSV y se comparan.
Los números no reproducibles se marcan "NO VERIFICABLE" en la salida.
