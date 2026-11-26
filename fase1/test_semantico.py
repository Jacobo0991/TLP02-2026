"""Pruebas de regresión para la fase semántica; ejecutar: python -m pytest -v."""
from pathlib import Path

import pytest

from lexer import tokenizar
from semantico import analizar, analizar_tokens


@pytest.mark.parametrize('archivo', ['valido_basico.cpp', 'valido_structs.cpp'])
def test_programas_originales_del_lexer(archivo):
    fuente = Path(__file__).parent / 'pruebas' / 'lexer' / archivo
    r = analizar(fuente.read_text(encoding='utf-8'))
    assert r.correcto, '\n'.join(map(str, r.errores))


@pytest.mark.parametrize('codigo', [
    'int a = 1; a = a + 2;',
    'int a = 1; { int a = 2; a++; } a++;',
    'int a, b, c = 2; a = b + c;',
    'float x = 3; double y = x + 2.5;',
    'int main(){ int n = 3; for (int i=0; i<n; ++i) n += i; return n; }',
    'int main(){int i=1; if(i) i=2; else i=3; while(i) i--; return 0;}',
    'int* p = nullptr; int x = 3; p = &x; x = *p;',
    'struct Punto {int x; int y;}; Punto p; p.x = 5; int n = p.y;',
    'struct Nodo {int v;}; Nodo n; Nodo *p = &n; int x = p->v;',
    'typedef long long ll; ll n = 1LL; long long t = n;',
    '#define ll long long\nll x = 2;',
    '#define MOD 1000000007\nint x = MOD;',
    'vector<vector<int>> datos; vector<int> a; a.push_back(5);',
    'std::vector<std::vector<int>> a; std::string s = "hola";',
    'vector<int> a(3); for (auto &x : a) x = 2;',
    'int inc(int a){ return a + 1;} int main(){ return inc(2); }',
    'int inc(int); int inc(int a){ return a; } int x = inc(4);',
    'int a = 2; int b = a * 3;',
    'typedef int T; T *p = nullptr;',
    'bool b = true; char c = \'z\'; string s = "hola";',
    'unsigned long long a = 2ULL; const long long x = 1e18;',
    'int main(){ for (int i=0; i<5; i++){ int x=i; } return 0; }',
    'int a[4]; a[0] = 3; int b = a[1];',
    'int a = 1; do { a++; } while (a < 2);',
    'int sum(int a,int b){return a+b;} int x=sum(1,2);',
    'int a[2] = {1,2}; int b=a[0];',
    'vector<int> a = {1,2,3};',
    "string s=\"texto\"; s += \" otro\"; s += 'x';",
])
def test_valido(codigo):
    r = analizar(codigo)
    assert r.correcto, '\n'.join(map(str, r.errores))


@pytest.mark.parametrize('codigo,fragmento', [
    ('x = 3;', 'no declarado'),
    ('int a; a = b;', 'no declarado'),
    ('int a; int a;', 'ya fue declarado'),
    ('int a; {int b;} b=1;', 'no declarado'),
    ('int a = "hola";', 'no se puede asignar'),
    ('string s = "hola"; int x = s;', 'no se puede asignar'),
    ('int n = nullptr;', 'no se puede asignar'),
    ('int a=1; a->m = 3;', "'->' requiere puntero"),
    ('struct A { int x; }; A a; A *p=&a; p.x = 2;', "'.' no accede a punteros"),
    ('struct A {int x;}; A a; a.inexistente=2;', 'no tiene miembro'),
    ('int a; a.foo();', 'no contiene miembros accesibles'),
    ('int a; a = 3 + "hola";', 'operador'),
    ('int a=3; int b = *a;', 'no se puede desreferenciar'),
    ('int a=3; int b = a[0];', 'no admite indexación'),
    ('int a=1; (a+2)=3;', 'no es modificable'),
    ('const int a=1; a=4;', 'variable const'),
    ('int f(int a){return "hola";}', 'return de tipo'),
    ('int f(){return;}', 'debe retornar'),
    ('void f(){return 1;}', 'no puede devolver'),
    ('int f(int a){return a;} int b=f(1,2);', 'espera 1 argumentos'),
    ('int f(int a){return a;} int b=f("hola");', 'argumento 1'),
    ('void f(){ y = 2; }', 'no declarado'),
    ('for(int i=0;i<2;i++) {} i=3;', 'no declarado'),
    ('if (true) int x = 1; x = 2;', 'no declarado'),
    ('float x=1.0; int i = x % 2;', 'requiere operandos enteros'),
    ('int x=1; x ^ "hola";', 'requiere operandos enteros'),
    ('int x = noExiste(3);', 'no declarado'),
    ('auto x;', 'requiere inicializador'),
    ('void x;', 'no puede ser de tipo void'),
    ('int x=2; int y = &x + "hola";', 'operador'),
    ('continue;', 'fuera de un ciclo'),
    ('return 3;', 'fuera de una función'),
    ('int a=1; int *p=&a; p->foo=1;', "no contiene miembros"),
    ('int a[2]={1,"x"};', 'elemento'),
    ('int a[2], b[2]; a=b;', 'asignación incompatible'),
    ('for (auto x : 42) {}', 'no se puede recorrer'),
    ('float f=1.0; f%=2;', "no aplicable"),
    ('int f(){return 1;} int f(){return 2;}', 'definición duplicada'),
])
def test_error_semantico(codigo, fragmento):
    r = analizar(codigo)
    assert any(fragmento in e.mensaje for e in r.errores), (
        f'No se encontró {fragmento!r}: {list(map(str, r.errores))}')


def test_corte_por_error_lexico():
    r = analizar('int a = @; b = 1;')
    assert r.errores_lexicos
    assert not r.errores
    assert not r.simbolos


def test_analizar_tokens_y_posiciones():
    tokens, lexicos = tokenizar('int x=1;\nint x=2;')
    assert not lexicos
    resultado = analizar_tokens(tokens)
    assert len(resultado.errores) == 1
    assert (resultado.errores[0].linea, resultado.errores[0].columna) == (2, 5)
    assert any(s.nombre == 'x' for s in resultado.simbolos)


def test_contextos_de_tabla():
    r = analizar('int n=1; void f(int x){int y=x;}')
    assert r.correcto
    assert [(s.nombre, s.clase) for s in r.simbolos] == [
        ('n', 'variable'), ('f', 'funcion'), ('x', 'parametro'), ('y', 'variable')]
    assert 'funcion_f' in r.simbolos[2].ambito


def test_informar_multiples_errores():
    r = analizar('int n=0; int n=2; x = "texto";')
    assert len(r.errores) >= 2


def test_lexico_sigue_siendo_independiente():
    tokens, errores = tokenizar('int n = 12;')
    assert not errores
    assert [t.tipo for t in tokens] == [
        'KW_INT', 'ID', 'OP_ASIG', 'LIT_INT', 'PUNTO_COMA', 'EOF']
