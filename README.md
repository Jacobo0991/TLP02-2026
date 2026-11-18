# Proyecto de Teoría de Lenguajes

Analizador léxico (Fase 1), sintáctico (Fase 2) y semántico (Fase 3) para un
subconjunto de C++ orientado a programación competitiva.

La especificación completa de tokens está en
[docs/especificacion_tokens.md](docs/especificacion_tokens.md).

## Lexer

La Fase 1 implementa el analizador léxico en [lexer.py](lexer.py).

### Cómo ejecutarlo

```bash
python lexer.py pruebas/valido_basico.cpp
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
