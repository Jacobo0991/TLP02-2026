### 1. Cómo usar el lexer
```python
from lexer import tokenizar, Token, ID, KW_INT, LIT_INT, PUNTO_COMA  # etc.

tokens, errores = tokenizar(codigo)
if errores:          # recomendado: no correr el semántico si hay errores léxicos
    for e in errores: print(e)
```
- Los tipos de token son **strings**, así que se compara con `tok.tipo == KW_INT`.
- La lista **siempre termina en un token `EOF`**.
- Línea y columna empiezan en 1. Conviene que los errores semánticos sigan el mismo formato: `Error semántico [línea L, col C]: <mensaje>`.

### 2. Qué guarda cada token en `valor`
| Tipo | `valor` | Lo que importa para el semántico |
|---|---|---|
| `ID` | el nombre (`str`) | es la clave de la tabla de símbolos |
| `LIT_INT`, `LIT_HEX` | `int` | el sufijo se pierde en `valor`, pero queda en `lexema`: `1LL` es `long long` |
| `LIT_FLOAT` | `float` | sin sufijo es `double`; con `f` es `float` |
| `LIT_CHAR` | `str` de 1 carácter, ya decodificado | tipo `char` |
| `LIT_STRING` | `str` sin comillas, ya decodificado | tipo cadena (`string` o `const char*`, a elección del equipo) |
| `LIT_BOOL` | `True` / `False` | tipo `bool` |
| `LIT_NULLPTR` | `None` | es compatible con cualquier puntero |
| `DIR_DEFINE` | tupla `(nombre, reemplazo)` | `reemplazo` es **texto crudo**: se puede pasar por `tokenizar()` para deducir su tipo (`#define MOD 1000000007` es un `int`) |
| `DIR_INCLUDE` | nombre del archivo | se puede ignorar |

### 3. Lo que el lexer *no* hace y le toca al semántico
- **Nombres de la biblioteca estándar:** `cin`, `cout`, `endl`, `vector`, `string`, `pair`, `sort`, `max`, `min`, `ios`, `std`, etc. llegan como `ID`. Hay que **precargarlos en el ámbito global** de la tabla de símbolos; si no, se reportarían como "variable no declarada".
- **Tipos compuestos:** `long long` y `unsigned int` llegan como varios tokens `KW_*` seguidos, y hay que combinarlos en un solo tipo.
- **Tipos definidos por el usuario:** `struct Nodo`, `typedef long long ll;` y `#define ll long long` producen un `ID` que debe registrarse como **tipo**, no como variable.
- **Macros:** no se expanden. Si alguien usa `ll` después de un `#define`, el semántico tiene que saber que es un alias de tipo.
- **Miembros:** el `ID` que viene después de `.`, `->` o `::` (`a.size()`, `r->izq`, `ios::sync_with_stdio`) **no se busca como variable**. Se busca entre los campos del struct o se acepta como miembro de la biblioteca estándar.
- **Símbolos ambiguos:** `*` siempre llega como `OP_MULT` y `&` como `OP_AND_BIT`. El semántico o el agrupador decide si son puntero, referencia o dirección. El caso clave es `a * b;`: si `a` es un tipo en la tabla de símbolos, es una declaración de puntero; si no, es una multiplicación.
- **Plantillas:** `vector<vector<int>>` termina en `OP_SHR`, que hay que tratar como dos `>`.

### 4. Detalles del flujo de tokens
- **Los lexemas con error no generan token:** desaparecen del flujo. Por eso conviene no correr el semántico si hay errores léxicos, porque podría reportar errores falsos.
- **Un `/*` sin cerrar consume todo lo que sigue hasta el final del archivo.**
- **Ámbitos:** se abren y cierran con `LLAVE_IZQ` y `LLAVE_DER`. Las variables del `for (int i = 0; ...)` y los parámetros de una función pertenecen al ámbito del bloque que sigue.

### 5. Agrupar sentencias sin parser
El enunciado permite trabajar con "tokens agrupados por sentencia". Si lo hacen así, cuidado al cortar por `PUNTO_COMA`:
- el `for (...; ...; ...)` tiene `;` dentro de los paréntesis;
- un struct termina en `};`;
- `if`/`while` sin llaves controlan solo la siguiente sentencia.

Una función auxiliar que cuente la profundidad de paréntesis antes de cortar resuelve el primer caso.

### 6. Reglas mínimas que pide el enunciado
Variables declaradas antes de usarse, detección de redeclaraciones en el mismo ámbito, compatibilidad de tipos en asignaciones y expresiones, y ámbitos con tabla de símbolos. Con el subconjunto que eligieron, pueden agregar revisiones de punteros (asignar `nullptr` solo a punteros, usar `->` solo sobre punteros, usar `.` solo sobre structs) para tener más material en la demo.