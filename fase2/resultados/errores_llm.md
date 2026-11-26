# Errores y desviaciones del LLM — Fase 2

## zero_shot

### Desviaciones hacia el español general (oraciones gramaticales que debían rechazarse)

_(ninguna)_


### R12 — casos en que el LLM unió `de` al verbo

_(ninguno)_


### Motivos de rechazo que no coinciden con lo esperado

_(ninguno)_


### Errores de etiquetado (aceptada bien pero árbol distinto)

- **N2-04**: `El libro de María será nuevo.`
  - esperado: `(O (SUJ (SN (DET El) (SUST libro) (SP (PREP_DE de) (SN (NPROP María))))) (SV (COP será) (ATRIB (SADJ (ADJ nuevo)))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (DET El) (SUST libro) (SP (PREP_DE de) (NPROP María)))) (SV (COP será) (ATRIB (SADJ (ADJ nuevo))) ) (PUNTO .))`
- **N2-05**: `La casa del profesor será grande.`
  - esperado: `(O (SUJ (SN (DET La) (SUST casa) (SP (CONTR_DE del) (SN (SUST profesor))))) (SV (COP será) (ATRIB (SADJ (ADJ grande)))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (DET La) (SUST casa) (SP (CONTR_DE del) (SUST profesor)))) (SV (COP será) (ATRIB (SADJ (ADJ grande)))) (PUNTO .))`
- **N2-06**: `Pedro camina al parque.`
  - esperado: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO camina) (CC (SP (CONTR_A al) (SN (SUST parque))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO camina) (CC (SP (CONTR_A al) (SUST parque)))) (PUNTO .))`
- **N2-07**: `Ana trabajó en la escuela ayer.`
  - esperado: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO trabajó) (CC (SP (PREP en) (SN (DET la) (SUST escuela)))) (CC (SADV (ADV ayer)))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO trabajó) (CC (SP (PREP en) (DET la) (SUST escuela))) (CC (SADV (ADV ayer)))))`
- **N2-15**: `Ana y yo caminaremos con él`
  - esperado: `(O (SUJ (SN (SN (NPROP Ana)) (CONJ y) (SN (PRON yo)))) (SV (VERBO caminaremos) (CC (SP (PREP con) (SN (PRON él))))))`
  - LLM: `(O (SUJ (SN (SN (NPROP Ana)) (CONJ y) (SN (PRON yo)))) (SV (VERBO caminaremos) (CC (SP (PREP con) (PRON él)))))`
- **N3-06**: `Ana compró libros de María.`
  - esperado: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO compró) (OD (SN (SUST libros) (SP (PREP_DE de) (SN (NPROP María)))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO compró) (OD (SN (SUST libros) (SP (PREP_DE de) (NPROP María))))))`
- **N3-17**: `Sofía abrió la ventana con la flor.`
  - esperado: `(O (SUJ (SN (NPROP Sofía))) (SV (VERBO abrió) (OD (SN (DET la) (SUST ventana))) (CC (SP (PREP con) (SN (DET la) (SUST flor))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Sofía))) (SV (VERBO abrió) (OD (SN (DET la) (SUST ventana))) (CC (SP (PREP con) (DET la) (SUST flor)))) (PUNTO .))`
- **N3-18**: `Pedro escribió cartas de Ana.`
  - esperado: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO escribió) (OD (SN (SUST cartas) (SP (PREP_DE de) (SN (NPROP Ana)))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO escribió) (OD (SN (SUST cartas) (SP (PREP_DE de) (NPROP Ana))))) (PUNTO .))`

## few_shot

### Desviaciones hacia el español general (oraciones gramaticales que debían rechazarse)

_(ninguna)_


### R12 — casos en que el LLM unió `de` al verbo

_(ninguno)_


### Motivos de rechazo que no coinciden con lo esperado

_(ninguno)_


### Errores de etiquetado (aceptada bien pero árbol distinto)

- **N2-06**: `Pedro camina al parque.`
  - esperado: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO camina) (CC (SP (CONTR_A al) (SN (SUST parque))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Pedro))) (SV (VERBO camina) (CC (SP (CONTR_A al) (SUST parque)))) (PUNTO .))`
- **N2-10**: `María, Carlos y Pedro aprendieron.`
  - esperado: `(O (SUJ (SN (SN (NPROP María)) (COMA ,) (SN (NPROP Carlos)) (CONJ y) (SN (NPROP Pedro)))) (SV (VERBO aprendieron)) (PUNTO .))`
  - LLM: `(O (SUJ (SN (SN (NPROP María)) (COMA ,) (SN (NPROP Carlos)) (CONJ y) (SN (NPROP Pedro)))) (SV (VERBO aprendieron)))`
- **N3-06**: `Ana compró libros de María.`
  - esperado: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO compró) (OD (SN (SUST libros) (SP (PREP_DE de) (SN (NPROP María)))))) (PUNTO .))`
  - LLM: `(O (SUJ (SN (NPROP Ana))) (SV (VERBO compró) (OD (SN (SUST libros) (SP (PREP_DE de) (SN (NPROP María))))) (PUNTO .))`
