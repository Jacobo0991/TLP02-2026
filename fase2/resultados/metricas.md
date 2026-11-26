# Métricas — Fase 2

_Generado: 2026-11-26 01:20:36_

## 1. Exactitud UPOS por nivel y sistema

| Nivel | parser | spacy | hf | llm-few_shot | llm-zero_shot |
| --- | --- | --- | --- | --- | --- |
| 1 | 100.0% (85/85) | 96.5% (82/85) | 41.2% (35/85) | 0.0% (0/85) | 0.0% (0/85) |
| 2 | 100.0% (115/115) | 97.4% (112/115) | 57.4% (66/115) | 0.0% (0/115) | 0.0% (0/115) |
| 3 | 100.0% (89/89) | 93.1% (122/131) | 58.8% (77/131) | 0.0% (0/131) | 0.0% (0/131) |
| total | 100.0% (289/289) | 95.5% (316/331) | 53.8% (178/331) | 0.0% (0/331) | 0.0% (0/331) |

_Parser: quedan fuera por error léxico — nivel 1: 0, nivel 2: 0, nivel 3: 6 (total 6)._

## 2. UAS y LAS por nivel (oraciones con árbol esperado)

| Nivel | Parser UAS | Parser LAS | n | spaCy UAS | spaCy LAS | n |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 100.0% | 100.0% | 15 | 95.2% | 71.0% | 15 |
| 2 | 100.0% | 100.0% | 15 | 95.7% | 80.6% | 15 |
| 3 | 100.0% | 100.0% | 4 | 100.0% | 82.1% | 4 |
| total | 100.0% | 100.0% | 34 | 96.2% | 77.6% | 34 |

## 3. Aceptación — parser y LLM (clase positiva: aceptada)

| Sistema | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto | Err. etiquetado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| parser | 33 | 0 | 1 | 26 | 100.0% | 97.1% | 100.0% | 0 |
| llm-few_shot | 33 | 0 | 1 | 26 | 100.0% | 97.1% | 100.0% | 3 |
| llm-zero_shot | 33 | 0 | 1 | 26 | 100.0% | 97.1% | 100.0% | 8 |

### Aceptación desglosada por nivel

**parser**

| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 2 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 3 | 3 | 0 | 1 | 16 | 100.0% | 75.0% | 100.0% |

**llm-few_shot**

| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 2 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 3 | 3 | 0 | 1 | 16 | 100.0% | 75.0% | 100.0% |

**llm-zero_shot**

| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 2 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 3 | 3 | 0 | 1 | 16 | 100.0% | 75.0% | 100.0% |

## 4. Confusiones UPOS más frecuentes

**spaCy — top 10 errores**

| Esperado → Obtenido | Casos |
| --- | --- |
| VERB → PROPN | 7 |
| NOUN → PROPN | 6 |
| ADV → PART | 1 |
| VERB → NOUN | 1 |

**HuggingFace — top 10 errores**

| Esperado → Obtenido | Casos |
| --- | --- |
| PUNCT → SYM | 28 |
| VERB → PROPN | 13 |
| PUNCT → ADJ | 12 |
| NOUN → PRON | 11 |
| DET → PROPN | 11 |
| PUNCT → CCONJ | 10 |
| NOUN → PROPN | 9 |
| PUNCT → NOUN | 5 |
| PROPN → PRON | 4 |
| NOUN → NUM | 4 |

## 5. Desacuerdos de adjunción (parser vs spaCy)

| Id | Oración | Parser | spaCy |
| --- | --- | --- | --- |
| N3-05 | Ana mira al niño con el libro. | obl | obj |

## 6. Costo

| Sistema | Tiempo promedio por oración | Tamaño en disco |
| --- | --- | --- |
| parser | 0.0 ms | 0.0 MB |
| spacy | 3.0 ms | 602.0 MB |
| hf | 18.8 ms | 962.7 MB |
| llm-few_shot | 0.0 ms | — |
| llm-zero_shot | 0.0 ms | — |
