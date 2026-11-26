# Fase 3 — Analizador semántico (Python + tokens C++)

## Objetivo

Este analizador **trabaja sobre los tokens que entrega `lexer.py`**, sin modificar la Fase 1. Comprueba las cuatro reglas obligatorias del documento `contexto_lexer.md` y algunos casos útiles del subconjunto C++ usado en competición.

## Flujo

```text
archivo.cpp
   │
   ▼
lexer.tokenizar(codigo)
   ├─ errores léxicos → informar y detener (los tokens inválidos se omiten)
   └─ tokens (incluido EOF)
          │
          ▼
AnalizadorSemantico(tokens)
   ├─ análisis/agrupación de declaraciones, bloques, sentencias y expresiones
   ├─ TablaSimbolos: pilas de ámbitos, nombres, tipos y funciones
   ├─ resolución de identificadores, aliases, campos y métodos conocidos
   ├─ compatibilidad de tipos y validación de operadores
   └─ ResultadoSemantico: errores y símbolos declarados
```

## Reglas verificadas

1. **Identificadores declarados antes de usarse.** Incluye búsqueda en el ámbito actual y padres; ciertos nombres estándar se precargan.
2. **Redeclaraciones dentro del mismo ámbito.** Permite ocultamiento (*shadowing*) en subámbitos. Permite prototipo/definición de función con la misma firma.
3. **Compatibilidad de tipos.** Asignaciones, declaraciones con inicializador, operadores, expresiones, argumentos y retornos. Sigue la conversión numérica implícita de C++ (por ejemplo, `double` a `int` con `=`, aunque pueda perder precisión). Las inicializaciones entre llaves son un subconjunto simplificado; no se modelan todas las reglas de *narrowing* del estándar.
4. **Ámbitos.** Global, funciones y parámetros, `{}` anidados, `if`/`else`, `while` y `for`, incluidos `for` por rango. Los parámetros son visibles dentro de la función; la variable del `for` no escapa al ciclo.

### Extras implementados

- `long long`, `unsigned int`, `const`, punteros, referencias, arreglos de una dimensión y literales con sufijos.
- `typedef`, `using Alias = Tipo`, macros simples de valores y `#define alias Tipo` (por ejemplo `#define ll long long`).
- `struct` con campos, acceso `.`, `->` y métodos declarados; constructores sencillos con lista de inicializadores.
- `nullptr` se acepta en punteros y se rechaza en enteros; `*` para desreferenciación y `&` para dirección.
- `vector<vector<int>>`: dentro de listas de tipos, `OP_SHR` se trata como dos `>`.
- Operadores de asignación y expresiones con precedencia; llamadas a funciones y chequeo de cantidad y tipos de argumentos en funciones del usuario.
- Biblioteca precargada (`cin`, `cout`, `endl`, `std`, `ios`, `string`, `vector`, `pair`, `sort`, `max`, `min`, etc.) para evitar falsos errores de variables no declaradas en los ejemplos del lexer.
- Diagnósticos con **línea y columna** de los tokens originales y salida JSON opcional.

## Archivos

- `lexer.py`: lexer original, sin cambios.
- `tabla_simbolos.py`: modelos `Tipo`, `Simbolo`, `TablaSimbolos`; reglas de compatibilidad.
- `semantico.py`: API de análisis, lector de sentencias y expresiones, CLI.
- `test_semantico.py`: pruebas con `pytest` (casos válidos, errores, ámbitos y API).
- `pruebas/semantico/*.cpp`: ejemplos de demo.
- `docs/contexto_lexer.md`: contexto recibido por el equipo.

## Cómo ejecutar

En la carpeta raíz del proyecto:

```bash
python semantico.py pruebas/semantico/valido.cpp --tabla
python semantico.py pruebas/semantico/errores_semanticos.cpp --tabla
python semantico.py pruebas/semantico/valido.cpp --json
python semantico.py pruebas/lexer/valido_basico.cpp
python semantico.py pruebas/lexer/valido_structs.cpp
```

`--tabla` muestra las declaraciones del usuario y su ámbito (sin símbolos estándar precargados). `--json` permite integrar con una GUI/otra herramienta. El código de salida es `0` si no hay errores y `1` en caso contrario.

Pruebas (si falta `pytest`, instalar con `python -m pip install pytest`):

```bash
python -m pytest -v
```

## Uso programático

```python
from semantico import analizar, analizar_tokens
from lexer import tokenizar

codigo = 'int numero = 10; numero = "texto";'
reporte = analizar(codigo)  # recomendado: incluye control de errores léxicos
print(reporte.correcto)
for error in reporte.errores:
    print(error)
for simbolo in reporte.simbolos:
    print(simbolo.serializar())

# Cuando ya hay tokens sin errores léxicos:
tokens, errores_lexicos = tokenizar(codigo)
if not errores_lexicos:
    reporte = analizar_tokens(tokens)
```

## Limitaciones conocidas / alcance

**No es un compilador C++ ni un parser completo.** Se implementó un lector de sentencias y expresiones para la Fase 3 a partir de los tokens. Para un proyecto de compilación de C++ de producción necesitaríamos un parser real y un sistema de tipos/plantillas completo.

- Las declaraciones, `struct`, funciones y ciclos habituales del subconjunto están soportadas, pero no toda la gramática C++. No se admiten clases completas, herencia, `enum`, lambdas, sobrecargas de funciones distintas, plantillas de usuario, `try`/`catch`, deducción avanzada ni preprocesador real.
- Las macros se reconocen por nombre y valores simples; **no se expanden macros funcionales ni se interpretan condicionales del preprocesador**.
- Las funciones y métodos STL precargados tienen verificación limitada (su objetivo es evitar falsos identificadores no declarados, **no** reproducir todas las firmas ni las reglas de plantillas de `<bits/stdc++.h>`).
- Se aceptan algunas conversiones numéricas que C++ acepta pero que podrían perder precisión. No se analiza flujo de control para confirmar retorno en todas las rutas, ni uso de variables sin inicializar, ni toda la sobrecarga de operadores.
- La validación de arreglos multidimensionales, inicialización agregada de `struct`, tipos `auto` complejos y reglas `const` profundas no es completa.
- `analizar_tokens` supone que el flujo procede del lexer **sin errores**. Usar `analizar(codigo)` evita diagnósticos falsos en presencia de errores léxicos.
- Las incidencias estructurales sencillas se reportan mediante `ErrorSemantico`; ello **no reemplaza** una fase sintáctica rigurosa.
