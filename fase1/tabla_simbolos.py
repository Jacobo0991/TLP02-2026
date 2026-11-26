"""Tabla de símbolos y modelo de tipos para la fase semántica.

No depende de bibliotecas externas ni modifica el lexer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Tipo:
    nombre: str
    punteros: int = 0
    argumentos: tuple['Tipo', ...] = ()
    arreglo: bool = False
    constante: bool = False
    referencia: bool = False

    def __str__(self) -> str:
        s = ('const ' if self.constante else '') + self.nombre
        if self.argumentos:
            s += '<' + ', '.join(map(str, self.argumentos)) + '>'
        s += '*' * self.punteros
        if self.arreglo:
            s += '[]'
        if self.referencia:
            s += '&'
        return s

    def sin_referencia(self) -> 'Tipo':
        return Tipo(self.nombre, self.punteros, self.argumentos, self.arreglo, self.constante)

    def sin_const(self) -> 'Tipo':
        return Tipo(self.nombre, self.punteros, self.argumentos, self.arreglo)

    def puntero_a(self) -> 'Tipo':
        return Tipo(self.nombre, self.punteros + 1, self.argumentos)

    def contenido(self) -> 'Tipo':
        if self.punteros:
            return Tipo(self.nombre, self.punteros - 1, self.argumentos)
        if self.arreglo:
            return Tipo(self.nombre, self.punteros, self.argumentos)
        if self.nombre in {'vector', 'array', 'deque', 'set', 'unordered_set'} and self.argumentos:
            return self.argumentos[0]
        if self.nombre in {'string', 'const char*'}:
            return Tipo('char')
        return DESCONOCIDO


DESCONOCIDO = Tipo('?')
NULO = Tipo('nullptr')
NUMERICOS = {'bool', 'char', 'short', 'int', 'long', 'long long',
             'unsigned char', 'unsigned short', 'unsigned int', 'unsigned long',
             'unsigned long long', 'signed char', 'float', 'double', 'long double'}
INTEGRALES = NUMERICOS - {'float', 'double', 'long double'}


def es_numerico(t: Tipo) -> bool:
    return t.punteros == 0 and not t.arreglo and t.nombre in NUMERICOS


def es_integral(t: Tipo) -> bool:
    return t.punteros == 0 and not t.arreglo and t.nombre in INTEGRALES


def compatibles(dest: Tipo, fuente: Tipo) -> bool:
    """Conversión de asignación permisible en el subconjunto de C++ soportado.

    A diferencia de inicialización por llaves, = permite conversiones numéricas
    implícitas (incluida posible pérdida de precisión).
    """
    if DESCONOCIDO in (dest, fuente) or dest.nombre == '?' or fuente.nombre == '?':
        return True  # Evitar errores derivados de uno anterior.
    dest, fuente = dest.sin_referencia(), fuente.sin_referencia()
    if fuente == NULO:
        return dest.punteros > 0
    if dest.punteros or fuente.punteros or dest.arreglo or fuente.arreglo:
        if dest.punteros and fuente.arreglo:
            return dest.nombre == fuente.nombre or dest.nombre == 'void'
        if dest.punteros and fuente.nombre == 'const char*' and dest.nombre == 'char':
            return True
        return (dest.punteros == fuente.punteros and dest.punteros > 0
                and (dest.nombre == fuente.nombre or dest.nombre == 'void'))
    if dest.nombre == fuente.nombre:
        if dest.argumentos or fuente.argumentos:
            return dest.argumentos == fuente.argumentos
        return True
    if es_numerico(dest) and es_numerico(fuente):
        return True
    if dest.nombre == 'bool' and (fuente.punteros or fuente.nombre == 'nullptr'):
        return True
    if dest.nombre == 'string' and fuente.nombre in {'const char*', 'char*'}:
        return True
    return False


def tipo_comun(a: Tipo, b: Tipo) -> Tipo:
    if a.nombre == '?':
        return b
    if b.nombre == '?':
        return a
    if a == b:
        return a
    if es_numerico(a) and es_numerico(b):
        if 'double' in (a.nombre, b.nombre):
            return Tipo('double')
        if 'float' in (a.nombre, b.nombre):
            return Tipo('float')
        if 'long long' in (a.nombre, b.nombre):
            return Tipo('long long')
        return Tipo('int')
    if a == NULO and b.punteros:
        return b
    if b == NULO and a.punteros:
        return a
    return DESCONOCIDO


@dataclass
class Simbolo:
    nombre: str
    tipo: Tipo
    clase: str  # variable, parametro, funcion, tipo, macro, campo, biblioteca
    linea: int = 0
    columna: int = 0
    ambito: str = 'global'
    parametros: list[Tipo] = field(default_factory=list)
    campos: dict[str, 'Simbolo'] = field(default_factory=dict)
    elemento_tipo: Optional[Tipo] = None  # alias typedef o macro de tipo
    interno: bool = False
    definida: bool = False  # Una función solo puede tener una definición.

    def serializar(self) -> dict:
        return {'nombre': self.nombre, 'tipo': str(self.tipo),
                'clase': self.clase, 'ambito': self.ambito,
                'linea': self.linea, 'columna': self.columna,
                'parametros': [str(p) for p in self.parametros]}


class TablaSimbolos:
    def __init__(self) -> None:
        self.pilas: list[dict[str, Simbolo]] = [{}]
        self.nombres: list[str] = ['global']
        self.historial: list[Simbolo] = []
        self.contador = 0

    @property
    def ambito(self) -> str:
        return '::'.join(self.nombres)

    def abrir(self, nombre: str = 'bloque') -> None:
        self.contador += 1
        self.nombres.append(f'{nombre}#{self.contador}')
        self.pilas.append({})

    def cerrar(self) -> None:
        if len(self.pilas) == 1:
            raise ValueError('No se puede cerrar el ámbito global')
        self.pilas.pop()
        self.nombres.pop()

    def definir(self, simbolo: Simbolo) -> bool:
        if simbolo.nombre in self.pilas[-1]:
            return False
        simbolo.ambito = self.ambito
        self.pilas[-1][simbolo.nombre] = simbolo
        if not simbolo.interno:
            self.historial.append(simbolo)
        return True

    def actual(self, nombre: str) -> Simbolo | None:
        return self.pilas[-1].get(nombre)

    def buscar(self, nombre: str) -> Simbolo | None:
        for scope in reversed(self.pilas):
            if nombre in scope:
                return scope[nombre]
        return None
