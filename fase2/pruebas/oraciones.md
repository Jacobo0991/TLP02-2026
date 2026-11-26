# Set de prueba — Fase 2

Generado desde `oraciones.jsonl` (no editar a mano; regenerar con `python fase2/generar_md.py`).

Total: **60 oraciones**.

## Tabla de oraciones

| id | nivel | oración | esperado | regla/fenómeno |
| --- | --- | --- | --- | --- |
| N1-01 | 1 | Ana come el pan. | aceptada |  |
| N1-02 | 1 | Luis compró manzanas. | aceptada |  |
| N1-03 | 1 | Pedro nadó. | aceptada |  |
| N1-04 | 1 | María es feliz. | aceptada |  |
| N1-05 | 1 | Sofía será una profesora. | aceptada |  |
| N1-06 | 1 | Correremos. | aceptada |  |
| N1-07 | 1 | Yo vivo aquí. | aceptada |  |
| N1-08 | 1 | Carlos comió una manzana. | aceptada |  |
| N1-09 | 1 | Ella abrirá la ventana. | aceptada |  |
| N1-10 | 1 | Yo escribí cartas. | aceptada |  |
| N1-11 | 1 | Tú miraste los árboles. | aceptada |  |
| N1-12 | 1 | Los niños saltarán. | aceptada |  |
| N1-13 | 1 | Pedro fue inteligente. | aceptada |  |
| N1-14 | 1 | La casa está nueva. | aceptada |  |
| N1-15 | 1 | Beberemos pronto. | aceptada |  |
| N1-16 | 1 | El perro negras corre. | rechazo_semantico | C1 |
| N1-17 | 1 | Un casa es blanca. | rechazo_semantico | C1 |
| N1-18 | 1 | Ana comen pan. | rechazo_semantico | C3 |
| N1-19 | 1 | Los niños come. | rechazo_semantico | C3 |
| N1-20 | 1 | La casa es blanco. | rechazo_semantico | C4 |
| N2-01 | 2 | El bonito jardín es verde. | aceptada |  |
| N2-02 | 2 | El perro negro pequeño corrió. | aceptada |  |
| N2-03 | 2 | María será muy inteligente. | aceptada |  |
| N2-04 | 2 | El libro de María será nuevo. | aceptada |  |
| N2-05 | 2 | La casa del profesor será grande. | aceptada |  |
| N2-06 | 2 | Pedro camina al parque. | aceptada |  |
| N2-07 | 2 | Ana trabajó en la escuela ayer. | aceptada |  |
| N2-08 | 2 | Los niños cocinaron aquí ayer bien. | aceptada |  |
| N2-09 | 2 | Ana y Luis serán altos. | aceptada |  |
| N2-10 | 2 | María, Carlos y Pedro aprendieron. | aceptada |  |
| N2-11 | 2 | Sofía compra manzanas y flores. | aceptada |  |
| N2-12 | 2 | Ana pinta casas, mesas y ventanas. | aceptada |  |
| N2-13 | 2 | Pedro no lava el coche. | aceptada |  |
| N2-14 | 2 | Carlos siempre bebe. | aceptada |  |
| N2-15 | 2 | Ana y yo caminaremos con él | aceptada |  |
| N2-16 | 2 | Pedro camina al casa. | rechazo_semantico | C2 |
| N2-17 | 2 | Ana corre manzanas. | rechazo_semantico | C5 |
| N2-18 | 2 | Ana camina con yo. | rechazo_semantico | C6 |
| N2-19 | 2 | Perros comen pan. | rechazo_semantico | C7 |
| N2-20 | 2 | Ana comerá ayer. | rechazo_semantico | C8 |
| N3-01 | 3 | Ayer Ana comió pan. | rechazo_sintactico | Adverbio al inicio con sujeto explícito |
| N3-02 | 3 | Hoy María cocina manzanas. | rechazo_sintactico | Adverbio al inicio con sujeto explícito |
| N3-03 | 3 | Pan come Ana. | rechazo_semantico | C7 |
| N3-04 | 3 | El libro sobre la mesa es nuevo. | rechazo_sintactico | SP distinto de 'de' junto a un sustantivo |
| N3-05 | 3 | Ana mira al niño con el libro. | aceptada | Ambigüedad de adjunción |
| N3-06 | 3 | Ana compró libros de María. | aceptada | Ambigüedad con 'de' |
| N3-07 | 3 | El perro de Ana y Luis come. | rechazo_semantico | C3 |
| N3-08 | 3 | Ana come y Luis bebe. | rechazo_sintactico | Coordinación de oraciones |
| N3-09 | 3 | Ana no siempre come pan. | rechazo_sintactico | Negación con adverbio |
| N3-10 | 3 | Ana come pan muy rápidamente. | rechazo_sintactico | Intensificador de un adverbio |
| N3-11 | 3 | Ana, Luis y Sofía son alta, alto y alta, respectivamente. | rechazo_lexico | Dependencias cruzadas |
| N3-12 | 3 | El perro que corre es negro. | rechazo_lexico | Subordinadas y relativas |
| N3-13 | 3 | Ana lo come. | rechazo_lexico | Clíticos |
| N3-14 | 3 | Ana ha comido pan. | rechazo_lexico | Tiempos compuestos y perífrasis |
| N3-15 | 3 | ¿Ana come pan? | rechazo_lexico | Preguntas |
| N3-16 | 3 | Las manzanas fueron compradas por Ana. | rechazo_lexico | Pasiva |
| N3-17 | 3 | Sofía abrió la ventana con la flor. | aceptada | Ambigüedad de adjunción |
| N3-18 | 3 | Pedro escribió cartas de Ana. | aceptada | Ambigüedad con 'de' |
| N3-19 | 3 | Manzana compra Sofía. | rechazo_semantico | C7 |
| N3-20 | 3 | La casa de María y Carlos será grande. | rechazo_semantico | C3 |

## Resumen por nivel y resultado esperado

| nivel | aceptada | rechazo_lexico | rechazo_sintactico | rechazo_semantico | total |
| --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | 0 | 5 | 20 |
| 2 | 15 | 0 | 0 | 5 | 20 |
| 3 | 4 | 6 | 6 | 4 | 20 |
| **total** | 34 | 6 | 6 | 14 | **60** |

## Reglas semánticas en los rechazos (C1-C8)

| regla | ocurrencias |
| --- | --- |
| C1 | 2 |
| C2 | 1 |
| C3 | 4 |
| C4 | 1 |
| C5 | 1 |
| C6 | 1 |
| C7 | 3 |
| C8 | 1 |

## Fenómenos del nivel 3

| fenómeno | ocurrencias |
| --- | --- |
| Adverbio al inicio con sujeto explícito | 2 |
| Orden OVS | 2 |
| Ambigüedad de adjunción | 2 |
| Ambigüedad con 'de' | 2 |
| Coordinación dentro de un SP | 2 |
| SP distinto de 'de' junto a un sustantivo | 1 |
| Coordinación de oraciones | 1 |
| Negación con adverbio | 1 |
| Intensificador de un adverbio | 1 |
| Dependencias cruzadas | 1 |
| Subordinadas y relativas | 1 |
| Clíticos | 1 |
| Tiempos compuestos y perífrasis | 1 |
| Preguntas | 1 |
| Pasiva | 1 |
