# Especificación de tokens — Subconjunto de C++ para programación competitiva

Nov 18, 2026 · @Jacob

## Alcance del subconjunto

El lexer reconoce el C++ que aparece en una solución típica de programación competitiva: un solo archivo con `#include`, `using namespace std`, `typedef`/`#define` simples, tipos primitivos, `vector`/`string`/`pair`, ciclos, condicionales, funciones, structs, punteros y entrada/salida con `cin`/`cout`.

Programa de referencia que debe tokenizarse sin errores:

```cpp
#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
#define MOD 1000000007

const ll INF = 1e18;

ll potencia(ll b, ll e) {
    ll r = 1;
    while (e > 0) {
        if (e & 1) r = r * b % MOD;
        b = b * b % MOD;
        e >>= 1;
    }
    return r;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    cin >> n;
    vector<int> a(n);
    for (auto &x : a) cin >> x;
    sort(a.begin(), a.end());
    cout << a[0] << " " << potencia(2, n) << '\n';
    return 0;
}
```

**Decisión de diseño:** `vector`, `string`, `pair`, `cin`, `cout`, `endl`, `sort`, `max`, `min`, `ios` y los demás nombres de la biblioteca estándar se reconocen como **identificadores** (`ID`), igual que en el C++ real, donde no son palabras reservadas. El analizador semántico los precarga en la tabla de símbolos con su tipo. Así el lexer queda pequeño y la verificación de que existan pasa a la fase semántica.

## Definiciones regulares auxiliares

Todos los tokens se definen a partir de estas definiciones regulares. Ninguna usa recursión ni conteo, así que todo el léxico es un lenguaje regular (tipo 3 en la jerarquía de Chomsky).

```text
letra       → [A-Za-z_]
digito      → [0-9]
hexdig      → [0-9A-Fa-f]
exponente   → [eE] [+-]? digito+
sufijo_ent  → [uU] (ll | LL | l | L)?  |  (ll | LL | l | L) [uU]?
sufijo_flot → [fFlL]
escape      → \\ [ntr0\\'"]
```

`escape` acepta solo `\n`, `\t`, `\r`, `\0`, `\\`, `\'` y `\"`, que son los que se usan en la práctica. Cualquier otra barra invertida dentro de un literal es un error léxico.

## Palabras reservadas

Son 37 palabras. Cada una produce su propio tipo de token `KW_<PALABRA>` (por ejemplo, `while` → `KW_WHILE`), salvo `true`, `false` y `nullptr`, que son literales. Se reconocen primero como identificador y luego se buscan en el diccionario `RESERVADAS`; así `int` es `KW_INT` pero `intx` es `ID`.

| Grupo | Palabras | Tipo de token |
| --- | --- | --- |
| Tipos primitivos | `int`, `long`, `short`, `char`, `bool`, `float`, `double`, `void`, `auto` | `KW_INT`, `KW_LONG`, … |
| Modificadores de tipo | `unsigned`, `signed`, `const`, `constexpr`, `static` | `KW_UNSIGNED`, `KW_CONST`, … |
| Control de flujo | `if`, `else`, `for`, `while`, `do`, `switch`, `case`, `default`, `break`, `continue`, `return` | `KW_IF`, `KW_FOR`, … |
| Declaraciones | `using`, `namespace`, `typedef`, `struct` | `KW_USING`, `KW_STRUCT`, … |
| Punteros y memoria dinámica | `new`, `delete`, `this` | `KW_NEW`, `KW_DELETE`, `KW_THIS` |
| Otras | `sizeof`, `operator` | `KW_SIZEOF`, `KW_OPERATOR` |
| Literales con nombre | `true`, `false` | `LIT_BOOL` |
| Literales con nombre | `nullptr` | `LIT_NULLPTR` |

Los tipos compuestos como `long long` o `unsigned int` se emiten como dos tokens (`KW_LONG KW_LONG`); combinarlos en un solo tipo le toca al parser o al semántico.

## Identificadores y literales

Hay un tipo de identificador y cinco tipos de literal numérico o de texto. La notación científica (`1e9`, `1e18`) se incluye porque es la forma habitual de escribir `INF` en programación competitiva.

| Tipo de token | Ejemplos válidos | Valor que guarda el lexer |
| --- | --- | --- |
| `ID` | `n`, `dp`, `_max2`, `vector`, `cout` | el texto |
| `LIT_INT` | `0`, `42`, `1000000007`, `1LL`, `5ull` | entero de Python |
| `LIT_HEX` | `0xFF`, `0x3f3f3f3f` | entero de Python |
| `LIT_FLOAT` | `3.14`, `0.5`, `.5`, `2.`, `1e9`, `1.5e-6`, `2.0f` | `float` de Python |
| `LIT_CHAR` | `'a'`, `'\n'`, `'0'` | el carácter ya decodificado |
| `LIT_STRING` | `"YES"`, `"Case #"`, `"\n"` | el texto sin comillas, decodificado |

Expresiones regulares, usando las definiciones de arriba:

```text
ID          → letra (letra | digito)*
LIT_HEX     → 0[xX] hexdig+ sufijo_ent?
LIT_FLOAT   → ( digito+ \. digito* exponente?
              | \. digito+ exponente?
              | digito+ exponente ) sufijo_flot?
LIT_INT     → digito+ sufijo_ent?
LIT_CHAR    → ' ( [^'\\\n] | escape ) '
LIT_STRING  → " ( [^"\\\n] | escape )* "
```

Un `LIT_INT` que empieza con `0` y tiene más dígitos (`017`) sería octal en C++. Como casi nunca se usa en concursos, se declara fuera del alcance y se reporta como error para que no se interprete como decimal sin aviso.

## Operadores y delimitadores

Son 38 operadores y 8 delimitadores; cada símbolo tiene su propio tipo de token. El lexer solo reconoce el símbolo: si `<<` es desplazamiento o salida con `cout`, o si `&` es AND de bits o referencia, lo decide el parser según el contexto.

| Categoría | Símbolo | Tipo de token |
| --- | --- | --- |
| Aritméticos | `+` `-` `*` `/` `%` | `OP_SUMA`, `OP_RESTA`, `OP_MULT`, `OP_DIV`, `OP_MOD` |
| Incremento | `++` `--` | `OP_INC`, `OP_DEC` |
| Relacionales | `==` `!=` `<` `>` `<=` `>=` | `OP_IGUAL`, `OP_DIST`, `OP_MENOR`, `OP_MAYOR`, `OP_MENOR_IG`, `OP_MAYOR_IG` |
| Lógicos | `&&` `\|\|` `!` | `OP_AND`, `OP_OR`, `OP_NOT` |
| De bits | `&` `\|` `^` `~` `<<` `>>` | `OP_AND_BIT`, `OP_OR_BIT`, `OP_XOR`, `OP_NOT_BIT`, `OP_SHL`, `OP_SHR` |
| Asignación | `=` | `OP_ASIG` |
| Asignación compuesta | `+=` `-=` `*=` `/=` `%=` | `OP_SUMA_ASIG`, `OP_RESTA_ASIG`, `OP_MULT_ASIG`, `OP_DIV_ASIG`, `OP_MOD_ASIG` |
| Asignación de bits | `&=` `\|=` `^=` `<<=` `>>=` | `OP_AND_ASIG`, `OP_OR_ASIG`, `OP_XOR_ASIG`, `OP_SHL_ASIG`, `OP_SHR_ASIG` |
| Ternario | `?` `:` | `OP_TERNARIO`, `DOS_PUNTOS` |
| Acceso y ámbito | `::` `.` `->` | `OP_AMBITO`, `OP_PUNTO`, `OP_FLECHA` |
| Delimitadores | `(` `)` | `PAR_IZQ`, `PAR_DER` |
| Delimitadores | `[` `]` | `COR_IZQ`, `COR_DER` |
| Delimitadores | `{` `}` | `LLAVE_IZQ`, `LLAVE_DER` |
| Delimitadores | `;` `,` | `PUNTO_COMA`, `COMA` |

`DOS_PUNTOS` también aparece en el `for` por rango (`for (auto &x : a)`) y en `case 1:`.

## Punteros y structs

Punteros y structs no agregan símbolos nuevos: reutilizan `*`, `&`, `->`, `.` y `:`, y suman 4 palabras reservadas (`new`, `delete`, `this`, `operator`) a `struct` y `nullptr`, que ya estaban. El código típico de concursos que deben tokenizar sin errores:

```cpp
struct Arista {
    int u, v, w;
    bool operator<(const Arista &o) const { return w < o.w; }
};

struct Nodo {
    int val;
    Nodo *izq, *der;
    Nodo(int v) : val(v), izq(nullptr), der(nullptr) {}
};

Nodo *insertar(Nodo *r, int v) {
    if (r == nullptr) return new Nodo(v);
    if (v < r->val) r->izq = insertar(r->izq, v);
    else r->der = insertar(r->der, v);
    return r;
}
```

| Construcción | Ejemplo | Tokens |
| --- | --- | --- |
| Definir un struct | `struct Punto { int x, y; };` | `KW_STRUCT ID LLAVE_IZQ KW_INT ID COMA ID PUNTO_COMA LLAVE_DER PUNTO_COMA` |
| Acceso a miembro | `p.x` | `ID OP_PUNTO ID` |
| Acceso por puntero | `r->izq` | `ID OP_FLECHA ID` |
| Declarar puntero | `Nodo *p;` | `ID OP_MULT ID PUNTO_COMA` |
| Obtener dirección | `&x` | `OP_AND_BIT ID` |
| Desreferenciar | `*p` | `OP_MULT ID` |
| Puntero nulo | `p = nullptr;` | `ID OP_ASIG LIT_NULLPTR PUNTO_COMA` |
| Reservar memoria | `new Nodo(3)` | `KW_NEW ID PAR_IZQ LIT_INT PAR_DER` |
| Liberar memoria | `delete p;` | `KW_DELETE ID PUNTO_COMA` |
| Lista de inicialización | `: val(v)` | `DOS_PUNTOS ID PAR_IZQ ID PAR_DER` |
| Sobrecarga de operador | `operator<(const Arista &o)` | `KW_OPERATOR OP_MENOR PAR_IZQ KW_CONST ID OP_AND_BIT ID PAR_DER` |
| Puntero al propio struct | `this->val` | `KW_THIS OP_FLECHA ID` |

Los símbolos conservan su nombre de operador (`OP_MULT`, `OP_AND_BIT`) aunque aquí funcionen como puntero, referencia o dirección: el lexer no puede saber qué papel cumplen y eso lo decide el parser. El nombre de un struct (`Nodo`, `Arista`) es un `ID`; el semántico lo registra como tipo en la tabla de símbolos.

## Directivas, espacios y comentarios

Solo se aceptan dos directivas, `#include` y `#define` simple, y cada una se emite como un único token con toda la línea. El lexer no expande macros: el semántico puede registrar el nombre de un `#define` como constante.

| Tipo de token | Ejemplos | Expresión regular | ¿Se emite? |
| --- | --- | --- | --- |
| `DIR_INCLUDE` | `#include <bits/stdc++.h>`, `#include "util.h"` | `#[ \t]*include[ \t]*(<[^>\n]+>\|"[^"\n]+")` | Sí (guarda el nombre del archivo) |
| `DIR_DEFINE` | `#define MOD 1000000007`, `#define ll long long` | `#[ \t]*define[ \t]+letra(letra\|digito)*[^\n]*` | Sí (guarda nombre y texto de reemplazo) |
| `ESPACIO` | espacios, tabulaciones | `[ \t\r]+` | No |
| `NUEVA_LINEA` | salto de línea | `\n` | No (solo suma 1 a la línea) |
| `COMENTARIO_LINEA` | `// O(n log n)` | `//[^\n]*` | No |
| `COMENTARIO_BLOQUE` | `/* ... */` en varias líneas | `/\*[\s\S]*?\*/` | No (cuenta los saltos de línea que contiene) |

Al final del archivo se agrega siempre un token `EOF` con la línea y la columna donde termina el texto.

## Errores léxicos

El lexer reconoce 10 errores. Cada uno se reporta con el formato `Error léxico [línea L, col C]: <mensaje>`; luego el lexer salta el lexema que falló y sigue leyendo (recuperación en modo pánico), así que una sola corrida muestra todos los errores.

| # | Error | Ejemplo | Cómo se detecta | Mensaje |
| --- | --- | --- | --- | --- |
| 1 | Carácter inválido | `int a@b;`, `` ` ``, `$` | patrón `.` al final de la lista | carácter inválido '@' |
| 2 | Número mal formado | `123abc`, `1.2.3`, `1e`, `0x`, `5LLL` | `\d[\w.]*`, después de los literales válidos | número mal formado '123abc' |
| 3 | Literal octal | `017` | `0\d+`, antes de `LIT_INT` | literales octales no soportados '017' |
| 4 | Cadena sin cerrar | `cout << "hola;` | `"` sin `"` de cierre antes del fin de línea | cadena sin cerrar |
| 5 | Escape inválido | `"\q"`, `'\a'` | al decodificar el literal | secuencia de escape inválida '\\q' |
| 6 | Carácter sin cerrar | `char c = 'a;` | `'` sin `'` de cierre | literal de carácter sin cerrar |
| 7 | Carácter vacío | `''` | 0 caracteres entre comillas | literal de carácter vacío |
| 8 | Varios caracteres | `'ab'` | más de 1 carácter entre comillas | literal de carácter con varios caracteres |
| 9 | Comentario sin cerrar | `/* ...` hasta el final | `/\*[\s\S]*`, después del comentario válido | comentario sin cerrar (abierto en línea L) |
| 10 | Directiva no soportada o mal formada | `#pragma GCC optimize("O3")`, `#include bits`, `#` suelto | `#[^\n]*`, después de las directivas válidas | directiva no soportada '#pragma' |

Los errores 4 a 8 se detectan en el código y no solo con la expresión regular. Los patrones `"([^"\\\n]|\\.)*"?` y `'([^'\\\n]|\\.)*'?` aceptan el literal aunque esté sin cerrar, vacío o largo; después el código revisa la comilla final, cuenta los caracteres y valida cada escape. Así el mensaje dice exactamente qué está mal.

## Orden de prioridad y casos ambiguos

Con una expresión regular maestra (`re.finditer` y grupos con nombre), Python prueba las alternativas en orden y se queda con la primera que coincide, no con la más larga. Por eso el orden de la lista es parte de la especificación:

1. Comentarios válidos (`//`, `/* */`) y luego comentario sin cerrar, antes que `OP_DIV`.
2. `DIR_INCLUDE`, `DIR_DEFINE` y luego la directiva no soportada (`#[^\n]*`).
3. `LIT_STRING` y `LIT_CHAR`.
4. Literales numéricos: `LIT_HEX`, `LIT_FLOAT`, octal (error), `LIT_INT`. Cada uno termina con `(?![\w.])`, para que `123abc` no se parta en `123` + `abc`.
5. Número mal formado (`\d[\w.]*`).
6. `ID`, que después se busca en `RESERVADAS`.
7. Operadores de 3 caracteres: `<<=` `>>=`.
8. Operadores de 2 caracteres: `++` `--` `==` `!=` `<=` `>=` `&&` `||` `<<` `>>` `+=` `-=` `*=` `/=` `%=` `&=` `|=` `^=` `::` `->`.
9. Operadores de 1 carácter y delimitadores. `OP_PUNTO` va después de `LIT_FLOAT` para que `.5` sea número.
10. Espacios y saltos de línea.
11. Carácter inválido (`.`), siempre al final.

Casos ambiguos que el lexer **no** resuelve y deja al parser, porque dependen del contexto:

- **`>>` en plantillas:** `vector<vector<int>>` produce `OP_SHR` al final. El parser debe tratarlo como dos `>` cuando cierra una plantilla, igual que hace C++ desde C++11.
- **`<` y `>`:** en `vector<int>` son delimitadores de plantilla; en `a < b`, comparación. El lexer emite `OP_MENOR` / `OP_MAYOR` en ambos casos.
- **`*` y `&`:** `*` puede ser multiplicación, declaración de puntero (`Nodo *p`) o desreferencia (`*p`); `&` puede ser AND de bits, referencia (`auto &x`) u obtener dirección (`&x`). El lexer siempre emite `OP_MULT` y `OP_AND_BIT`.
- **`a * b;`:** puede ser una multiplicación o la declaración de un puntero `b` de tipo `a`. Solo se sabe consultando la tabla de símbolos para ver si `a` es un tipo, por ejemplo un struct. Es un ejemplo directo de dependencia del contexto.
- **`<<` y `>>`:** con `cin`/`cout` son entrada y salida; con números, desplazamiento.

Estos casos sirven para la reflexión del video: el lexer trabaja con un lenguaje regular y no tiene memoria del contexto, así que esas decisiones solo pueden tomarse en un nivel superior de la jerarquía.

## Ejemplo de tokenización

La línea 5 de un programa, con 4 espacios de sangría, produce 21 tokens:

```cpp
    for (int i = 0; i < n; i++) cin >> a[i];
```

| Tipo | Lexema | Línea | Col |
| --- | --- | --- | --- |
| `KW_FOR` | `for` | 5 | 5 |
| `PAR_IZQ` | `(` | 5 | 9 |
| `KW_INT` | `int` | 5 | 10 |
| `ID` | `i` | 5 | 14 |
| `OP_ASIG` | `=` | 5 | 16 |
| `LIT_INT` | `0` | 5 | 18 |
| `PUNTO_COMA` | `;` | 5 | 19 |
| `ID` | `i` | 5 | 21 |
| `OP_MENOR` | `<` | 5 | 23 |
| `ID` | `n` | 5 | 25 |
| `PUNTO_COMA` | `;` | 5 | 26 |
| `ID` | `i` | 5 | 28 |
| `OP_INC` | `++` | 5 | 29 |
| `PAR_DER` | `)` | 5 | 31 |
| `ID` | `cin` | 5 | 33 |
| `OP_SHR` | `>>` | 5 | 37 |
| `ID` | `a` | 5 | 40 |
| `COR_IZQ` | `[` | 5 | 41 |
| `ID` | `i` | 5 | 42 |
| `COR_DER` | `]` | 5 | 43 |
| `PUNTO_COMA` | `;` | 5 | 44 |

Una línea con errores sigue tokenizándose después de cada uno:

```cpp
int x@ = 08 + 'ab';
```

```text
Error léxico [línea 7, col 6]: carácter inválido '@'
Error léxico [línea 7, col 10]: literales octales no soportados '08'
Error léxico [línea 7, col 15]: literal de carácter con varios caracteres
```

## Fuera del alcance

Estas construcciones de C++ no se reconocen; si aparecen, generan un error léxico o tokens que el parser rechazará:

- `#pragma`, `#ifdef`/`#endif` y macros con parámetros (`#define F(x) ...` se emite como `DIR_DEFINE`, pero no se expande).
- Literales octales (`017`), binarios (`0b101`) y separadores de dígitos (`1'000'000`).
- Cadenas crudas (`R"(...)"`) y con prefijo (`u8""`, `L""`).
- Palabras reservadas de clases y plantillas: `class`, `template`, `typename`, `public`, `private`, `virtual`.
- Operadores `<=>`, `.*`, `->*` y `...`.
