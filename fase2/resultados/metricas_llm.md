# Métricas del experimento con el LLM — Fase 2

## 1. Aceptación — zero-shot vs few-shot

| Métrica | zero_shot | few_shot |
| --- | --- | --- |
| Precisión | 100.0% | 100.0% |
| Cobertura | 97.1% | 97.1% |
| Tasa de rechazo correcto | 100.0% | 100.0% |
| VP | 33 | 33 |
| FP | 0 | 0 |
| FN | 1 | 1 |
| VN | 26 | 26 |
| Error de etiquetado | 8 | 3 |

## 2. Aceptación por nivel

**zero_shot**

| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 2 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 3 | 3 | 0 | 1 | 16 | 100.0% | 75.0% | 100.0% |

**few_shot**

| Nivel | VP | FP | FN | VN | Precisión | Cobertura | Rech. correcto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 2 | 15 | 0 | 0 | 5 | 100.0% | 100.0% | 100.0% |
| 3 | 3 | 0 | 1 | 16 | 100.0% | 75.0% | 100.0% |

## 3. Exactitud UPOS y UAS/LAS

| Condición | Nivel | UPOS | UAS | LAS | n(UAS) | saltadas |
| --- | --- | --- | --- | --- | --- | --- |
| zero_shot | 1 | 100.0% | 100.0% | 100.0% | 15 | 0 |
| zero_shot | 2 | 99.1% | 100.0% | 100.0% | 10 | 5 |
| zero_shot | 3 | 91.6% | — | — | 0 | 4 |
| zero_shot | total | 96.4% | 100.0% | 100.0% | 25 | 9 |
| few_shot | 1 | 100.0% | 100.0% | 100.0% | 15 | 0 |
| few_shot | 2 | 99.1% | 100.0% | 100.0% | 13 | 2 |
| few_shot | 3 | 93.9% | 100.0% | 100.0% | 2 | 2 |
| few_shot | total | 97.3% | 100.0% | 100.0% | 30 | 4 |

## 4. Coincidencia exacta del árbol

| Condición | Nivel | OK / Total | % |
| --- | --- | --- | --- |
| zero_shot | 1 | 15/15 | 100.0% |
| zero_shot | 2 | 10/15 | 66.7% |
| zero_shot | 3 | 0/4 | 0.0% |
| zero_shot | total | 25/34 | 73.5% |
| few_shot | 1 | 15/15 | 100.0% |
| few_shot | 2 | 13/15 | 86.7% |
| few_shot | 3 | 2/4 | 50.0% |
| few_shot | total | 30/34 | 88.2% |

## 5. Desviación hacia el español general

_De las oraciones gramaticales que la gramática rechaza_ _(fenómenos del nivel 3), qué porcentaje acepta el LLM._

| Condición | Aceptadas / Total | % |
| --- | --- | --- |
| zero_shot | 0/16 | 0.0% |
| few_shot | 0/16 | 0.0% |

## 6. Respeto de R12 (unir `de` / `del` al sustantivo)

| Condición | OK / Total | Indecisos | % |
| --- | --- | --- | --- |
| zero_shot | 4/4 | 0 | 100.0% |
| few_shot | 3/4 | 1 | 75.0% |

## 7. Motivos del rechazo correcto

| Condición | Etapa correcta | Regla citada correcta | Reglas inventadas |
| --- | --- | --- | --- |
| zero_shot | 26/26 (100.0%) | 14/26 (53.8%) | 0 |
| few_shot | 26/26 (100.0%) | 14/26 (53.8%) | 0 |

## 8. Formato de la respuesta

| Condición | Inválidas / Total | % |
| --- | --- | --- |
| zero_shot | 0/60 | 0.0% |
| few_shot | 0/60 | 0.0% |

## 9. Consistencia entre las 3 repeticiones

| Condición | Consistentes / Total | % |
| --- | --- | --- |
| zero_shot | 55/60 | 91.7% |
| few_shot | 60/60 | 100.0% |

## 10. Zero-shot vs few-shot — prueba de McNemar

- Oraciones correctas solo en zero_shot (b): **0**
- Oraciones correctas solo en few_shot  (c): **0**
- Estadístico (trivial): **0.0000**
- Valor p: **1.0000**
- Resultado: diferencia _no significativo_ al 5 %.

## 11. Costo

| Condición | Llamadas | Tokens entrada | Tokens salida | Costo USD | Latencia prom. |
| --- | --- | --- | --- | --- | --- |
| zero_shot | 180 | 394617 | 242173 | $0.1605 | 6.15s |
| few_shot | 180 | 576237 | 170472 | $0.1429 | 4.45s |

**Totales: 970854 tokens de entrada, 412645 de salida, $0.3034**.
