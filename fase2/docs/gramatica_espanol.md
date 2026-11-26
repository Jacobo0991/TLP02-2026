# Gramática libre de contexto del español — Fase 2

Nov 25, 2026 · @Jacob

## Resumen y decisiones de diseño

La gramática tiene **24 reglas de producción, 24 no terminales y 17 terminales**. Es LL(1) salvo por un único conflicto, que se resuelve igual que el *else* colgante. Cubre oraciones Sujeto-Verbo-Objeto con sujeto explícito o tácito, verbos copulativos (`ser`, `estar`), adjetivos, adverbios, frases preposicionales, negación, coordinación de sintagmas nominales y tres tiempos verbales: presente, pretérito y futuro.

Cada decisión responde a una actividad de la Fase 2, para no tener que corregir la gramática más adelante:

| Actividad de la Fase 2 | Decisión en la gramática |
| --- | --- |
| Cubrir SVO, modificadores, 2 tiempos y concordancia | SVO, copulativas, adjetivos antes y después del sustantivo, adverbios, frases preposicionales y 3 tiempos |
| Parser descendente recursivo o LL(1) | Sin recursión por la izquierda y factorizada; un solo conflicto (¿a quién se une un `de`?) con regla fija |
| Reutilizar el lexer de la Fase 1 | Cada palabra tiene **una sola** categoría en el léxico, así el lexer sigue siendo regular y el motor no cambia |
| Concordancia con el semántico | Las categorías no llevan género ni número; los rasgos viajan en el `valor` del token y el semántico aplica 8 reglas |
| Árboles visuales | Nodos con nombres fijos y una notación con corchetes que el código dibuja y que también puede producir el LLM |
| 60 oraciones en 3 niveles | Vocabulario de 400 formas y una lista cerrada de fenómenos que quedan fuera, para el nivel 3 |
| Comparar con spaCy y HuggingFace | Tabla de equivalencias con las etiquetas y relaciones de Universal Dependencies |
| Experimento con el LLM | Reglas numeradas y un prompt base listo para pegar, con salida en el mismo formato que el parser |
| Informe: dónde falla la CFG | La ambigüedad de `de`, la concordancia y la coordinación con *respectivamente* quedan documentadas como ejemplos |

## Definición formal

La gramática es G = (N, Σ, P, O), con símbolo inicial O (oración). Los terminales son las **categorías** que entrega el lexer, no las palabras: así la gramática no cambia si se agrega vocabulario.

**N** (24 no terminales): O, FIN, SUJ, SN, COORD, LISTA, SNS, NOMINAL, NUCLEO\_N, ADJS, SADJ, COMP\_N, SP\_DE, SV, MOD\_PRE, NEG\_OPC, PRED, OD\_OPC, OD, ATRIB, CCS, CC, SP, SADV.

**Σ** (17 terminales): DET, SUST, NPROP, PRON, ADJ, INTENS, VERBO, COP, NEG, ADV, PREP, PREP\_DE, CONTR\_A, CONTR\_DE, CONJ, COMA, PUNTO.

**P** (24 reglas; ε es la cadena vacía):

```text
 R1   O         → SUJ SV FIN | SV FIN
 R2   FIN       → PUNTO | ε
 R3   SUJ       → SN
 R4   SN        → SNS COORD
 R5   COORD     → LISTA CONJ SNS | ε
 R6   LISTA     → COMA SNS LISTA | ε
 R7   SNS       → DET NOMINAL | NPROP | PRON | NUCLEO_N
 R8   NOMINAL   → ADJ NUCLEO_N | NUCLEO_N
 R9   NUCLEO_N  → SUST ADJS COMP_N
 R10  ADJS      → SADJ ADJS | ε
 R11  SADJ      → INTENS ADJ | ADJ
 R12  COMP_N    → SP_DE | ε
 R13  SP_DE     → PREP_DE SNS | CONTR_DE NOMINAL
 R14  SV        → MOD_PRE NEG_OPC PRED CCS
 R15  MOD_PRE   → SADV | ε
 R16  NEG_OPC   → NEG | ε
 R17  PRED      → VERBO OD_OPC | COP ATRIB
 R18  OD_OPC    → OD | ε
 R19  OD        → SN
 R20  ATRIB     → SADJ | SN
 R21  CCS       → CC CCS | ε
 R22  CC        → SADV | SP
 R23  SP        → PREP SNS | PREP_DE SNS | CONTR_A NOMINAL | CONTR_DE NOMINAL
 R24  SADV      → ADV
```

Significado de los no terminales principales:

| Símbolo | Significado | Ejemplo |
| --- | --- | --- |
| O | Oración | *Ana come manzanas.* |
| SUJ | Sujeto (opcional: sujeto tácito) | *Ana* |
| SN | Sintagma nominal, simple o coordinado | *Ana, Luis y Pedro* |
| SNS | Sintagma nominal simple | *el perro negro de Ana* |
| NUCLEO\_N | Sustantivo con sus adjetivos posteriores y su complemento con `de` | *perro negro de Ana* |
| SV | Sintagma verbal | *no come manzanas hoy* |
| PRED | Verbo con su objeto, o cópula con su atributo | *come manzanas*, *es alto* |
| OD | Objeto directo | *manzanas* |
| ATRIB | Atributo de un verbo copulativo | *muy alto*, *una profesora* |
| CC | Complemento circunstancial | *ayer*, *en el parque* |
| SP, SP\_DE | Sintagma preposicional (SP\_DE: complemento de un sustantivo con `de`/`del`) | *en el parque*, *del profesor* |
| SADJ, SADV | Sintagma adjetival y adverbial | *muy alto*, *ayer* |

Las decisiones que restringen el lenguaje, todas a propósito:

- **El adverbio antes del verbo solo va después del sujeto** (*Ana siempre come*). Un adverbio al inicio con sujeto explícito (*Ayer Ana comió*) es un caso del nivel 3.
- **El objeto directo con "a" personal** (*Ana mira a Luis*) se analiza como CC con SP. Distinguirlo exige saber si el sustantivo es animado, y eso no puede decidirlo una CFG.
- **Solo los complementos con `de`/`del` se unen al sustantivo**; los demás SP siempre son complementos del verbo.
- **Dentro de un SP no hay coordinación**: en *el perro de Ana y Luis*, `Luis` se coordina con *el perro*, no con *Ana*.

## Versión EBNF y análisis LL(1)

Para programar el parser descendente recursivo conviene la versión EBNF: genera el mismo lenguaje que las 24 reglas, y cada línea se traduce en una función. `[ x ]` significa opcional (un `if`) y `{ x }`, cero o más veces (un `while`).

```text
O        = [ SUJ ] SV [ PUNTO ] EOF
SUJ      = SN
SN       = SNS [ { COMA SNS } CONJ SNS ]
SNS      = DET NOMINAL | NPROP | PRON | NUCLEO_N
NOMINAL  = [ ADJ ] NUCLEO_N
NUCLEO_N = SUST { SADJ } [ SP_DE ]
SADJ     = [ INTENS ] ADJ
SP_DE    = PREP_DE SNS | CONTR_DE NOMINAL
SV       = [ SADV ] [ NEG ] ( VERBO [ OD ] | COP ATRIB ) { CC }
OD       = SN
ATRIB    = SADJ | SN
CC       = SADV | SP
SP       = PREP SNS | PREP_DE SNS | CONTR_A NOMINAL | CONTR_DE NOMINAL
SADV     = ADV
```

En cada punto de decisión basta mirar **un token** para elegir la alternativa. Los conjuntos de predicción de cada regla con alternativas son disjuntos, salvo en R12:

| Regla | Alternativas y token que las elige | ¿LL(1)? |
| --- | --- | --- |
| R1 `O` | SUJ: DET, NPROP, PRON, SUST · SV: ADV, NEG, VERBO, COP | Sí |
| R2 `FIN` | PUNTO · ε: fin de la entrada | Sí |
| R5 `COORD` | COMA, CONJ · ε: lo que sigue a un SN (ADV, NEG, VERBO, COP, PREP, PREP\_DE, CONTR\_A, CONTR\_DE, PUNTO, fin) | Sí |
| R6 `LISTA` | COMA · ε: CONJ | Sí |
| R7 `SNS` | DET · NPROP · PRON · SUST | Sí |
| R8 `NOMINAL` | ADJ · SUST | Sí |
| R10 `ADJS` | INTENS, ADJ · ε: cualquier otro token | Sí |
| R11 `SADJ` | INTENS · ADJ | Sí |
| **R12 `COMP_N`** | **SP\_DE: PREP\_DE, CONTR\_DE · ε: lo que sigue al sustantivo, que también incluye PREP\_DE y CONTR\_DE** | **No: conflicto** |
| R13 `SP_DE` | PREP\_DE · CONTR\_DE | Sí |
| R15 `MOD_PRE` | ADV · ε: NEG, VERBO, COP | Sí |
| R16 `NEG_OPC` | NEG · ε: VERBO, COP | Sí |
| R17 `PRED` | VERBO · COP | Sí |
| R18 `OD_OPC` | DET, NPROP, PRON, SUST · ε: ADV, PREP, PREP\_DE, CONTR\_A, CONTR\_DE, PUNTO, fin | Sí |
| R20 `ATRIB` | INTENS, ADJ · DET, NPROP, PRON, SUST | Sí |
| R21 `CCS` | ADV, PREP, PREP\_DE, CONTR\_A, CONTR\_DE · ε: PUNTO, fin | Sí |
| R22 `CC` | ADV · PREP, PREP\_DE, CONTR\_A, CONTR\_DE | Sí |
| R23 `SP` | PREP · PREP\_DE · CONTR\_A · CONTR\_DE | Sí |

**El conflicto de R12 y su resolución.** En *Ana compró libros de María*, después de `libros` llega `de`: puede ser el complemento del sustantivo (*libros de María*) o un complemento del verbo (*compró … de María*). Las dos lecturas existen en español, así que no es un defecto de la gramática sino una **ambigüedad estructural real**. Se resuelve como el *else* colgante: **si después de un sustantivo llega `de` o `del`, siempre se une al sustantivo más cercano**. En código es un `if` dentro de la función del núcleo nominal:

```python
def nucleo_n(self):
    hijos = [self.consumir(SUST)]
    while self.actual().tipo in (INTENS, ADJ):
        hijos.append(self.sadj())
    if self.actual().tipo in (PREP_DE, CONTR_DE):   # R12: se prefiere unir al sustantivo
        hijos.append(self.sp_de())
    return hijos
```

Este conflicto es material para el informe: muestra que el problema no está en el algoritmo, sino en que una oración puede tener dos árboles válidos y el parser tiene que elegir uno.

## Árboles sintácticos

El parser, el set de prueba y el LLM usan la misma notación con corchetes. Así los árboles se comparan como cadenas y se dibujan directamente con `nltk.Tree.fromstring(arbol)`, sin tener que convertirlos.

**Nodos visibles:** O, SUJ, SN, SV, OD, ATRIB, CC, SP, SADJ y SADV, más una hoja `(CATEGORIA palabra)` por cada token.

**Nodos que no aparecen** (sus hijos suben al nodo padre): FIN, COORD, LISTA, SNS, NOMINAL, NUCLEO\_N, ADJS, COMP\_N, MOD\_PRE, NEG\_OPC, PRED, OD\_OPC y CCS. Existen solo para que la gramática sea LL(1) y no aportan información lingüística.

Reglas para que dos árboles iguales produzcan la misma cadena:

- SP\_DE se escribe como `SP`.
- El sintagma nominal dentro de un SP se escribe como `SN`.
- Un SN coordinado es un `SN` padre con cada miembro como `SN` hijo, y las hojas `COMA` y `CONJ` entre ellos.
- La palabra se escribe tal como aparece en la oración, con mayúsculas y tildes.
- Un solo espacio entre elementos y todo en una línea. Antes de comparar, se normalizan los espacios.

Ejemplos (sirven también como ejemplos *few-shot* para el LLM):

```text
El perro negro come manzanas.
(O (SUJ (SN (DET El) (SUST perro) (SADJ (ADJ negro)))) (SV (VERBO come) (OD (SN (SUST manzanas)))) (PUNTO .))

Ana no compró los libros del profesor ayer.
(O (SUJ (SN (NPROP Ana))) (SV (NEG no) (VERBO compró) (OD (SN (DET los) (SUST libros) (SP (CONTR_DE del) (SN (SUST profesor))))) (CC (SADV (ADV ayer)))) (PUNTO .))

Ana y Luis son muy altos.
(O (SUJ (SN (SN (NPROP Ana)) (CONJ y) (SN (NPROP Luis)))) (SV (COP son) (ATRIB (SADJ (INTENS muy) (ADJ altos)))) (PUNTO .))

Siempre caminamos en el parque.
(O (SV (SADV (ADV Siempre)) (VERBO caminamos) (CC (SP (PREP en) (SN (DET el) (SUST parque))))) (PUNTO .))
```

En el último ejemplo el sujeto es tácito, así que no hay nodo SUJ. El adverbio que va antes del verbo cuelga directamente de SV; los que van después del verbo van dentro de CC.

## Léxico

El léxico tiene 400 formas en 17 categorías. Cada forma tiene **una sola categoría**: es la condición para que el lexer siga siendo regular y el parser siga siendo LL(1). Los rasgos van en el `valor` del token como un diccionario, por ejemplo `{"lema": "perro", "genero": "m", "numero": "sg"}`. Las claves son `lema`, `genero` (m, f, c = común), `numero` (sg, pl), `persona` (1, 2, 3), `tiempo` (pres, pret, fut), `trans` (trans, intr, ambos) y `referencia` (pasado, futuro, libre).

| Categoría | Rasgos | Formas |
| --- | --- | --- |
| DET | género, número | el, la, los, las, un, una, unos, unas |
| SUST (masculinos) | género, número | perro(s), gato(s), niño(s), libro(s), parque(s), árbol/árboles, coche(s), pan/panes, profesor/profesores, jardín/jardines |
| SUST (femeninos) | género, número | casa(s), niña(s), manzana(s), mesa(s), ciudad/ciudades, escuela(s), flor/flores, carta(s), profesora(s), ventana(s) |
| NPROP | género; número = sg, persona = 3 | Ana, María, Sofía (f); Luis, Pedro, Carlos (m) |
| PRON | persona, número, género | yo, tú, él, ella, nosotros, nosotras, ellos, ellas |
| ADJ (variables) | género, número; 4 formas cada uno | alto, bajo, rojo, negro, blanco, pequeño, nuevo, viejo, bonito, rápido (-o, -a, -os, -as) |
| ADJ (género común) | género = c, número | grande(s), feliz/felices, inteligente(s), verde(s), azul/azules, joven/jóvenes |
| INTENS | — | muy, bastante |
| ADV | referencia temporal | ayer (pasado); pronto (futuro); hoy, siempre, nunca, rápidamente, lentamente, bien, mal, aquí, allí (libre) |
| NEG | — | no |
| PREP | — | a, en, con, por, para, sobre, desde, hacia, sin |
| PREP\_DE | — | de |
| CONTR\_A | género = m, número = sg | al |
| CONTR\_DE | género = m, número = sg | del |
| CONJ | — | y, o |
| COMA, PUNTO | — | `,` y `.` |

**Verbos (VERBO).** Son 16 verbos regulares, así que sus 228 formas distintas se generan con código a partir de la tabla de terminaciones, sin escribirlas a mano:

| Transitividad | Verbos |
| --- | --- |
| Transitivos (llevan OD) | comprar, mirar, lavar, abrir |
| Ambos (con o sin OD) | comer, beber, aprender, escribir, cocinar, pintar |
| Intransitivos (sin OD) | correr, caminar, vivir, saltar, trabajar, nadar |

| Tiempo | Persona | -ar | -er | -ir |
| --- | --- | --- | --- | --- |
| Presente | yo, tú, él, nosotros, ellos | -o, -as, -a, -amos, -an | -o, -es, -e, -emos, -en | -o, -es, -e, -imos, -en |
| Pretérito | yo, tú, él, nosotros, ellos | -é, -aste, -ó, -amos, -aron | -í, -iste, -ió, -imos, -ieron | -í, -iste, -ió, -imos, -ieron |
| Futuro | yo, tú, él, nosotros, ellos | infinitivo + -é, -ás, -á, -emos, -án | igual | igual |

En -ar e -ir, el presente y el pretérito de *nosotros* son la misma forma (*caminamos*, *vivimos*). El token lleva los dos tiempos posibles (`"tiempo": ["pres", "pret"]`), y el semántico acepta cualquiera de los dos.

**Cópulas (COP).** Son irregulares y se escriben a mano (30 formas):

| Tiempo | ser | estar |
| --- | --- | --- |
| Presente | soy, eres, es, somos, son | estoy, estás, está, estamos, están |
| Pretérito | fui, fuiste, fue, fuimos, fueron | estuve, estuviste, estuvo, estuvimos, estuvieron |
| Futuro | seré, serás, será, seremos, serán | estaré, estarás, estará, estaremos, estarán |

No se incluyen *vosotros* ni *usted*, para no duplicar formas verbales.

**Cambios al lexer de la Fase 1.** El motor queda igual; solo cambian `PATRONES` y el diccionario, que pasa de `RESERVADAS` a `LEXICO`:

```python
PATRONES = [
    ('PALABRA',       r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+'),
    ('COMA',          r','),
    ('PUNTO',         r'\.'),
    ('ESPACIO',       r'[ \t\r\n]+'),
    ('CHAR_INVALIDO', r'.'),
]
# Cada PALABRA se busca en minúsculas en LEXICO -> (categoria, rasgos).
# Si no está: "Error léxico [línea L, col C]: palabra fuera del vocabulario 'x'".
```

**Palabras que no deben agregarse**, porque tendrían dos categorías: *bajo* como preposición, *mañana* y *tarde* (sustantivo y adverbio), *cocina* y *trabajo* como sustantivos (ya son formas de *cocinar* y *trabajar*), *vivo* como adjetivo (es forma de *vivir*), *la* y *lo* como pronombres (ya son determinantes) y cualquier forma de *ir* (*fue* ya es de *ser*). Para agregar vocabulario, primero comprueben que la forma no exista ya en `LEXICO`; conviene que el programa lo verifique al cargarlo.

## Concordancia y restricciones del semántico

El semántico recorre el árbol ya construido y aplica 8 reglas con los rasgos de los tokens. Solo se ejecuta si no hubo errores léxicos ni sintácticos, y reporta todos los errores que encuentra con el formato `Error semántico [col C]: <mensaje>`.

| # | Regla | Correcta | Con error | Mensaje |
| --- | --- | --- | --- | --- |
| C1 | Dentro del SN, el DET y los ADJ concuerdan en género y número con el SUST (género `c` acepta ambos) | *las casas blancas* | *la casa blancos* | el adjetivo 'blancos' (m. pl.) no concuerda con 'casa' (f. sg.) |
| C2 | `al` y `del` solo van con un nominal masculino singular; `a el` y `de el` deben contraerse | *al perro* | *al casa*, *a el perro* | 'al' solo va con masculino singular / 'a el' debe escribirse 'al' |
| C3 | El verbo concuerda con el sujeto en persona y número | *Ana y yo comemos* | *Los perros come* | el verbo 'come' (3.ª sg.) no concuerda con el sujeto (3.ª pl.) |
| C4 | El atributo concuerda con el sujeto: un SADJ en género y número; un SN, en número | *La casa es blanca* | *La casa es blanco*, *Ana es profesoras* | el atributo 'blanco' (m. sg.) no concuerda con el sujeto (f. sg.) |
| C5 | Un verbo intransitivo no lleva OD; uno transitivo lo necesita; `ambos` acepta las dos opciones | *Ana corre*, *Ana compra pan* | *Ana corre manzanas*, *Ana compra.* | 'correr' es intransitivo y no lleva objeto directo |
| C6 | Los pronombres de sujeto no funcionan como OD, y `yo` y `tú` no van después de preposición | *Ana camina con ella* | *Ana mira él*, *Ana camina con yo* | 'yo' no puede ir después de una preposición |
| C7 | Un sujeto con sustantivo común necesita determinante | *Los perros comen pan* | *Perros comen pan* | el sujeto 'Perros' necesita un determinante |
| C8 | El adverbio temporal concuerda con el tiempo del verbo: `ayer` con pretérito, `pronto` con futuro | *Ayer comimos*, *Ana comerá pronto* | *Ana comerá ayer* | 'ayer' no es compatible con un verbo en futuro |

Rasgos del sujeto que usan C3 y C4:

- **SN simple:** los del sustantivo, nombre propio o pronombre. Los sustantivos y nombres propios son de 3.ª persona.
- **SN coordinado:** el número es plural. La persona es 1.ª si algún miembro es de 1.ª (*Ana y yo comemos*); si no, 2.ª si alguno es de 2.ª; si no, 3.ª. El género es masculino si algún miembro es masculino (*Ana y Luis son altos*) y femenino solo si todos lo son (*Ana y María son altas*).
- **Sujeto tácito:** la persona y el número salen del verbo, y el género queda libre, así que *Somos altas* y *Somos altos* son válidas.
- **Formas con dos tiempos** (*caminamos*): C8 acepta cualquiera de los dos.

**Por qué estas reglas no van en la CFG.** Como los rasgos tienen pocos valores, la concordancia local podría escribirse en una CFG dividiendo cada no terminal por género, número y persona (`SN_f_sg`, `SN_m_pl`...). Pero la gramática se multiplica: solo C1 y C3 convierten las 24 reglas en cientos, y la coordinación necesita una variante por cada combinación de miembros. Por eso se verifica con una tabla de rasgos y no con más reglas. Lo que sí excede a las CFG son las **dependencias cruzadas**, como *Ana, Luis y Sofía son alta, alto y alta, respectivamente*: el primer adjetivo concuerda con el primer nombre, el segundo con el segundo, y así sucesivamente. Ese patrón no puede generarlo en general una gramática libre de contexto, y es el argumento central para el informe.

## Fenómenos fuera de la gramática (nivel 3)

Estas oraciones son correctas en español, pero la gramática no las cubre o las analiza de una sola manera. Los resultados de la tabla salen de un prototipo del parser con este léxico, así que son los que debería dar su implementación.

| Fenómeno | Ejemplo | Resultado esperado | Qué muestra |
| --- | --- | --- | --- |
| Adverbio al inicio con sujeto explícito | *Ayer Ana comió pan.* | Rechazo sintáctico en `Ana` | El orden de palabras del español es más libre que la gramática |
| Orden OVS | *Pan come Ana.* | Pasa la sintaxis con `Pan` como sujeto; C7 la rechaza | Sin rasgos semánticos no se puede saber quién come a quién |
| SP distinto de `de` junto a un sustantivo | *El libro sobre la mesa es nuevo.* | Rechazo sintáctico en `sobre` | Costo de la regla que resuelve el conflicto de R12 |
| Ambigüedad de adjunción | *Ana mira al niño con el libro.* | Aceptada, con `con el libro` unido al verbo | Dos lecturas válidas; el parser produce solo una |
| Ambigüedad con `de` | *Ana compró libros de María.* | Aceptada, con `de María` unido a `libros` | La otra lectura (se los compró a María, que los vendía) se pierde |
| Coordinación dentro de un SP | *El perro de Ana y Luis come.* | Pasa la sintaxis como *\[el perro de Ana\] y \[Luis\]*; C3 la rechaza (sujeto plural) | La lectura *de \[Ana y Luis\]* no existe en la gramática |
| Coordinación de oraciones | *Ana come y Luis bebe.* | Rechazo sintáctico en `y` | Solo se coordinan SN |
| Negación con adverbio | *Ana no siempre come pan.* | Rechazo sintáctico en `siempre` | El orden de SADV y NEG es fijo |
| Intensificador de un adverbio | *Ana come pan muy rápidamente.* | Rechazo sintáctico en `rápidamente` | `muy` solo modifica adjetivos, para mantener LL(1) |
| Dependencias cruzadas | *Ana, Luis y Sofía son alta, alto y alta, respectivamente.* | Rechazo (falta *respectivamente* en el léxico y no hay coordinación de atributos) | El fenómeno que una CFG no puede generar en general |
| Subordinadas y relativas | *El perro que corre es negro.* | Rechazo léxico en `que` | Recursión de oraciones dentro de oraciones |
| Clíticos | *Ana lo come.* | Rechazo léxico en `lo` | El objeto aparece antes del verbo |
| Tiempos compuestos y perífrasis | *Ana ha comido pan.*, *Ana va a comer pan.* | Rechazo léxico en `ha` / `va` | Solo hay tiempos simples |
| Preguntas | *¿Ana come pan?* | Rechazo léxico en `¿` | Solo hay oraciones declarativas |
| Pasiva | *Las manzanas fueron compradas por Ana.* | Rechazo léxico en `compradas` | No hay participios |

**Recomendación para el set de prueba:** que al menos la mitad de las oraciones del nivel 3 usen solo palabras del léxico (las primeras nueve filas). Si todas fallan por vocabulario, el análisis dice poco sobre los límites de la CFG; las que fallan por estructura o por ambigüedad son las que sirven para el informe.

## Equivalencias con Universal Dependencies

spaCy y los modelos de HuggingFace para español etiquetan con Universal Dependencies (UD). Para compararlos con el parser, cada categoría y cada función del árbol se traduce a UD con estas tablas; el código de comparación las usa como diccionarios.

| Categoría | UPOS (UD) |
| --- | --- |
| DET | DET |
| SUST | NOUN |
| NPROP | PROPN |
| PRON | PRON |
| ADJ | ADJ |
| VERBO | VERB |
| COP | AUX |
| ADV, INTENS, NEG | ADV |
| PREP, PREP\_DE, CONTR\_A, CONTR\_DE | ADP |
| CONJ | CCONJ |
| COMA, PUNTO | PUNCT |

| Elemento del árbol | Relación UD | Se une a |
| --- | --- | --- |
| VERBO de la oración | `root` | — |
| Núcleo del SUJ | `nsubj` | verbo, o núcleo del ATRIB en copulativas |
| Núcleo del OD | `obj` | verbo |
| Núcleo del ATRIB | `root` (en UD, el atributo es la raíz) | — |
| COP | `cop` | núcleo del ATRIB |
| Núcleo del SN de un CC con SP | `obl` | verbo |
| Núcleo del SN de un SP junto a un sustantivo | `nmod` | sustantivo |
| PREP, PREP\_DE | `case` | núcleo de su SN |
| ADV (en CC o antes del verbo), NEG | `advmod` | verbo |
| INTENS | `advmod` | adjetivo |
| ADJ | `amod` | sustantivo |
| DET | `det` | sustantivo |
| Segundo miembro y siguientes de una coordinación | `conj` | primer miembro |
| CONJ | `cc` | miembro que la sigue |
| COMA, PUNTO | `punct` | raíz, o miembro que sigue a la coma |

El núcleo de cada SN es su SUST, NPROP o PRON, y el de un SN coordinado es su primer miembro.

Tres diferencias que hay que tratar antes de comparar:

- **Copulativas:** en UD la raíz de *La casa es blanca* es *blanca*, no *es*. Si no se convierte el árbol con esa regla, todas las copulativas saldrán como errores falsos.
- **Contracciones:** en UD, *al* y *del* se dividen en dos palabras (*a* + *el*, `case` + `det`). Comprueben cómo las tokeniza cada herramienta y alineen los tokens antes de calcular métricas.
- **Ambigüedad:** cuando el parser y spaCy unan un SP a lugares distintos (por ejemplo `nmod` frente a `obl`), clasifíquenlo aparte. Puede ser una ambigüedad real y no un error de ninguno de los dos.

## Formato del set de prueba y de la salida

El set de prueba y la salida de cada sistema usan los mismos campos, así un solo script calcula todas las métricas. Se guarda en JSON Lines (`pruebas/oraciones.jsonl`, una oración por línea).

**Reparto de las 60 oraciones:**

| Nivel | Total | Que deben aceptarse | Que deben rechazarse |
| --- | --- | --- | --- |
| 1. Simples | 20 | 15 (SVO, copulativas, sujeto tácito) | 5 con un error de C1, C3 o C4 |
| 2. Intermedias | 20 | 15 (adjetivos, SP, coordinación, negación, 3 tiempos) | 5 con un error de C2, C5, C6, C7 o C8 |
| 3. Complejas | 20 | 0 o las ambiguas que se aceptan con una sola lectura | Las demás, fuera de la gramática (al menos 10 sin palabras nuevas) |

Las oraciones que deben rechazarse en los niveles 1 y 2 son necesarias para medir la tasa de rechazo correcto: sin ellas, un parser que acepte todo tendría una cobertura perfecta.

**Campos de cada oración del set:**

| Campo | Valores | Para qué sirve |
| --- | --- | --- |
| `id` | `N1-01` … `N3-20` | Identificar la oración en tablas y logs |
| `nivel` | 1, 2, 3 | Separar las métricas por nivel |
| `oracion` | texto | Entrada de todos los sistemas |
| `gramatical` | `true` / `false` | Si es correcta en español, sin importar la gramática |
| `esperado` | `aceptada`, `rechazo_lexico`, `rechazo_sintactico`, `rechazo_semantico` | Lo que debe responder el parser |
| `regla` | `C1` … `C8` o `null` | Qué regla semántica debe fallar |
| `fenomeno` | texto o `null` | Fenómeno del nivel 3 (de la tabla anterior) |
| `arbol` | notación con corchetes o `null` | Árbol esperado, si se acepta |
| `upos` | lista de etiquetas UD | Etiquetas esperadas para **todas** las oraciones, también las del nivel 3, para poder comparar con spaCy y HuggingFace |

Separar `gramatical` de `esperado` es lo que permite decir algo en el informe: una oración del nivel 3 es gramatical pero el parser debe rechazarla, y eso mide los límites de la gramática, no un error del código.

```json
{"id": "N1-07", "nivel": 1, "oracion": "La casa es blanco.", "gramatical": false, "esperado": "rechazo_semantico", "regla": "C4", "fenomeno": null, "arbol": null, "upos": ["DET", "NOUN", "AUX", "ADJ", "PUNCT"]}
```

**Salida del parser y del LLM** (`resultados/<sistema>.jsonl`): `id`, `aceptada` (`true`/`false`), `etapa` (`lexico`, `sintactico`, `semantico` o `null`), `mensajes` (lista de errores), `categorias` (una por token) y `arbol`.

**Métricas**, tomando "aceptada" como la clase positiva:

- **Precisión** = VP / (VP + FP): de las oraciones que el sistema aceptó, cuántas debían aceptarse.
- **Cobertura** = VP / (VP + FN): de las que debían aceptarse, cuántas aceptó.
- **Tasa de rechazo correcto** = VN / (VN + FP): de las que debían rechazarse, cuántas rechazó.
- **Clasificación de errores:** falso positivo (aceptó una que debía rechazar), falso negativo (rechazó una que debía aceptar) y error de etiquetado (aceptó bien, pero el árbol o las categorías no coinciden).

spaCy y HuggingFace no rechazan oraciones, así que con ellos se compara la exactitud de las etiquetas UPOS sobre las 60 oraciones y la de las relaciones (cabeza y tipo) sobre las aceptadas, siempre separada por nivel. Las métricas de aceptación se calculan para el parser y para el LLM.

## Prompt base para el LLM

Este es el prompt *zero-shot*: lleva la gramática, el léxico y las reglas semánticas, y pide la salida en el mismo formato que el parser. Para la versión *few-shot*, agreguen al final los cuatro ejemplos de la sección de árboles y dos oraciones rechazadas (una sintáctica y una semántica) con su salida en JSON. Usen el mismo modelo y temperatura 0 en todas las corridas, y guarden en el log el prompt, la respuesta, el modelo y la fecha.

```text
Eres un analizador sintáctico. Analiza la oración usando EXCLUSIVAMENTE la gramática,
el léxico y las reglas que siguen, aunque la oración te parezca correcta o incorrecta en
español. No uses tu conocimiento general del idioma.

## Gramática (ε = cadena vacía; los símbolos en mayúsculas del léxico son terminales)
R1  O        → SUJ SV FIN | SV FIN
R2  FIN      → PUNTO | ε
R3  SUJ      → SN
R4  SN       → SNS COORD
R5  COORD    → LISTA CONJ SNS | ε
R6  LISTA    → COMA SNS LISTA | ε
R7  SNS      → DET NOMINAL | NPROP | PRON | NUCLEO_N
R8  NOMINAL  → ADJ NUCLEO_N | NUCLEO_N
R9  NUCLEO_N → SUST ADJS COMP_N
R10 ADJS     → SADJ ADJS | ε
R11 SADJ     → INTENS ADJ | ADJ
R12 COMP_N   → SP_DE | ε      (si después del sustantivo viene PREP_DE o CONTR_DE, elige SP_DE)
R13 SP_DE    → PREP_DE SNS | CONTR_DE NOMINAL
R14 SV       → MOD_PRE NEG_OPC PRED CCS
R15 MOD_PRE  → SADV | ε
R16 NEG_OPC  → NEG | ε
R17 PRED     → VERBO OD_OPC | COP ATRIB
R18 OD_OPC   → OD | ε
R19 OD       → SN
R20 ATRIB    → SADJ | SN
R21 CCS      → CC CCS | ε
R22 CC       → SADV | SP
R23 SP       → PREP SNS | PREP_DE SNS | CONTR_A NOMINAL | CONTR_DE NOMINAL
R24 SADV     → ADV

## Léxico (cada palabra tiene una sola categoría; una palabra que no esté aquí es un
## rechazo léxico)
DET: el, la, los, las, un, una, unos, unas
SUST (m): perro(s), gato(s), niño(s), libro(s), parque(s), árbol/árboles, coche(s),
          pan/panes, profesor/profesores, jardín/jardines
SUST (f): casa(s), niña(s), manzana(s), mesa(s), ciudad/ciudades, escuela(s), flor/flores,
          carta(s), profesora(s), ventana(s)
NPROP: Ana, María, Sofía (f); Luis, Pedro, Carlos (m)
PRON: yo, tú, él, ella, nosotros, nosotras, ellos, ellas
ADJ: alto, bajo, rojo, negro, blanco, pequeño, nuevo, viejo, bonito, rápido (con -o, -a,
     -os, -as); grande(s), feliz/felices, inteligente(s), verde(s), azul/azules, joven/jóvenes
INTENS: muy, bastante
ADV: ayer, pronto, hoy, siempre, nunca, rápidamente, lentamente, bien, mal, aquí, allí
NEG: no
PREP: a, en, con, por, para, sobre, desde, hacia, sin
PREP_DE: de        CONTR_A: al        CONTR_DE: del
CONJ: y, o         COMA: ,            PUNTO: .
VERBO: solo las formas regulares de presente, pretérito y futuro (yo, tú, él/ella,
       nosotros, ellos) de: comprar, mirar, lavar, abrir (transitivos); comer, beber,
       aprender, escribir, cocinar, pintar (con o sin objeto); correr, caminar, vivir,
       saltar, trabajar, nadar (intransitivos)
COP: soy, eres, es, somos, son, fui, fuiste, fue, fuimos, fueron, seré, serás, será,
     seremos, serán, estoy, estás, está, estamos, están, estuve, estuviste, estuvo,
     estuvimos, estuvieron, estaré, estarás, estará, estaremos, estarán

## Reglas semánticas (se aplican solo si la oración pasa la gramática)
C1 Dentro del SN, DET y ADJ concuerdan en género y número con el SUST.
C2 "al" y "del" solo van con masculino singular; "a el" y "de el" deben contraerse.
C3 El verbo concuerda con el sujeto en persona y número (un SN coordinado es plural;
   1.ª persona si incluye a "yo" o "nosotros").
C4 El atributo concuerda con el sujeto: en género y número si es SADJ, en número si es SN
   (coordinado: masculino si algún miembro es masculino).
C5 Los verbos intransitivos no llevan OD; los transitivos lo necesitan.
C6 Los pronombres no son OD; "yo" y "tú" no van después de preposición.
C7 Un sujeto con sustantivo común necesita determinante.
C8 "ayer" exige pretérito; "pronto" exige futuro.

## Formato del árbol
Nodos visibles: O, SUJ, SN, SV, OD, ATRIB, CC, SP, SADJ, SADV y hojas (CATEGORIA palabra).
No escribas FIN, COORD, LISTA, SNS, NOMINAL, NUCLEO_N, ADJS, COMP_N, MOD_PRE, NEG_OPC,
PRED, OD_OPC ni CCS: sus hijos van directamente en el nodo padre. SP_DE se escribe SP.
Un SN coordinado es un SN con cada miembro como SN hijo. Todo en una sola línea.

## Respuesta
Responde SOLO con un objeto JSON, sin texto adicional:
{"aceptada": true|false,
 "etapa": "lexico"|"sintactico"|"semantico"|null,
 "mensajes": ["motivo del rechazo, citando la regla (R1-R24 o C1-C8)"],
 "categorias": ["una categoría por palabra"],
 "arbol": "(O ...)" o null}

Oración: {ORACION}
```

Para saber si el LLM respeta las reglas o se desvía hacia su conocimiento del español, comparen sobre todo las oraciones del nivel 3 que son gramaticales y deben rechazarse (*Ayer Ana comió pan.*, *El libro sobre la mesa es nuevo.*). Si el LLM las acepta, está usando lo que sabe del idioma y no la gramática. Hagan el mismo conteo con las ambiguas: si une `de María` al verbo, está ignorando la regla R12.
