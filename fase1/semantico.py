"""Analizador semántico para los tokens producidos por lexer.py.

Fase 3 de TLP02-2026: tabla de símbolos, ámbitos, declaraciones,
identificadores, tipos de expresiones/asignaciones, funciones y estructuras.
Incluye un agrupador/lector de sentencias (NO es un parser C++ completo).

API:
    resultado = analizar(codigo_cpp)
    resultado = analizar_tokens(tokens)
    resultado.errores, resultado.simbolos, resultado.errores_lexicos

CLI:
    python semantico.py pruebas/semantico/valido_basico.cpp --tabla
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from lexer import Token, tokenizar
from tabla_simbolos import (
    Tipo, Simbolo, TablaSimbolos, DESCONOCIDO, NULO,
    compatibles, tipo_comun, es_numerico, es_integral,
)


@dataclass
class ErrorSemantico:
    mensaje: str
    linea: int
    columna: int

    def __str__(self) -> str:
        return f'Error semántico [línea {self.linea}, col {self.columna}]: {self.mensaje}'


@dataclass
class ResultadoSemantico:
    simbolos: list[Simbolo]
    errores: list[ErrorSemantico]
    errores_lexicos: list | None = None

    @property
    def correcto(self) -> bool:
        return not self.errores and not self.errores_lexicos

    def como_diccionario(self) -> dict:
        return {
            'correcto': self.correcto,
            'errores_lexicos': [str(e) for e in (self.errores_lexicos or [])],
            'errores_semanticos': [str(e) for e in self.errores],
            'tabla_simbolos': [s.serializar() for s in self.simbolos],
        }


@dataclass
class Expresion:
    tipo: Tipo = DESCONOCIDO
    asignable: bool = False
    simbolo: Simbolo | None = None


_TIPOS_PRIMITIVOS = {
    'KW_INT', 'KW_LONG', 'KW_SHORT', 'KW_CHAR', 'KW_BOOL',
    'KW_FLOAT', 'KW_DOUBLE', 'KW_VOID', 'KW_AUTO',
}
_MODIFICADORES = {'KW_CONST', 'KW_CONSTEXPR', 'KW_STATIC', 'KW_UNSIGNED', 'KW_SIGNED'}
_CONTENEDORES = {'vector', 'array', 'deque', 'set', 'unordered_set', 'map',
                'unordered_map', 'pair', 'queue', 'stack', 'priority_queue'}
_BIB_TIPOS = _CONTENEDORES | {'string', 'size_t', 'iterator'}
_BIB_FUNCIONES = {
    'sort', 'max', 'min', 'swap', 'reverse', 'unique', 'lower_bound',
    'upper_bound', 'binary_search', 'accumulate', 'find', 'count', 'abs',
    'sqrt', 'pow', 'gcd', '__gcd', 'lcm', 'make_pair', 'begin', 'end',
    'printf', 'scanf', 'getline', 'to_string', 'stoi', 'stoll', 'push', 'pop',
}
_BIB_OBJETOS = {'cin': 'istream', 'cout': 'ostream', 'cerr': 'ostream',
                'clog': 'ostream', 'endl': 'manipulador', 'ios': 'namespace',
                'std': 'namespace', 'INT_MAX': 'int', 'LLONG_MAX': 'long long',
                'NULL': 'nullptr'}
_ASIGNACIONES = {
    'OP_ASIG', 'OP_SUMA_ASIG', 'OP_RESTA_ASIG', 'OP_MULT_ASIG',
    'OP_DIV_ASIG', 'OP_MOD_ASIG', 'OP_AND_ASIG', 'OP_OR_ASIG',
    'OP_XOR_ASIG', 'OP_SHL_ASIG', 'OP_SHR_ASIG',
}
# precedencia C++ simplificada, mayor número = se evalúa primero.
_BINARIOS = {
    'OP_OR': 3, 'OP_AND': 4,
    'OP_OR_BIT': 5, 'OP_XOR': 6, 'OP_AND_BIT': 7,
    'OP_IGUAL': 8, 'OP_DIST': 8,
    'OP_MENOR': 9, 'OP_MAYOR': 9, 'OP_MENOR_IG': 9, 'OP_MAYOR_IG': 9,
    'OP_SHL': 10, 'OP_SHR': 10,
    'OP_SUMA': 11, 'OP_RESTA': 11,
    'OP_MULT': 12, 'OP_DIV': 12, 'OP_MOD': 12,
}


class AnalizadorSemantico:
    def __init__(self, tokens: list[Token]):
        self.tokens = list(tokens)
        if not self.tokens or self.tokens[-1].tipo != 'EOF':
            ultimo = self.tokens[-1] if self.tokens else Token('EOF', '', 1, 1)
            self.tokens.append(Token('EOF', '', ultimo.linea, ultimo.columna))
        self.i = 0
        self.tabla = TablaSimbolos()
        self.errores: list[ErrorSemantico] = []
        self.estructuras: dict[str, Simbolo] = {}
        self.retorno: list[Tipo] = []
        self.en_bucle = 0
        self.struct_actual: str | None = None
        self._precargar_biblioteca()

    def _precargar_biblioteca(self) -> None:
        for nombre in _BIB_TIPOS:
            s = Simbolo(nombre, Tipo(nombre), 'tipo', interno=True, elemento_tipo=Tipo(nombre))
            self.tabla.definir(s)
        for nombre in _BIB_FUNCIONES:
            self.tabla.definir(Simbolo(nombre, DESCONOCIDO, 'funcion', interno=True))
        for nombre, nombre_tipo in _BIB_OBJETOS.items():
            clase = 'biblioteca' if nombre_tipo != 'namespace' else 'namespace'
            self.tabla.definir(Simbolo(nombre, Tipo(nombre_tipo), clase, interno=True))

    def actual(self) -> Token:
        return self.tokens[min(self.i, len(self.tokens) - 1)]

    def sig(self, n: int = 1) -> Token:
        return self.tokens[min(self.i + n, len(self.tokens) - 1)]

    def es(self, *tipos: str) -> bool:
        return self.actual().tipo in tipos

    def tomar(self) -> Token:
        tok = self.actual()
        if self.i < len(self.tokens) - 1:
            self.i += 1
        return tok

    def aceptar(self, tipo: str) -> Token | None:
        return self.tomar() if self.es(tipo) else None

    def error(self, token: Token, mensaje: str) -> None:
        self.errores.append(ErrorSemantico(mensaje, token.linea, token.columna))

    def esperar(self, tipo: str, motivo: str = '') -> Token | None:
        if self.es(tipo):
            return self.tomar()
        # Se reporta, pero no se inventa un token ni se salta al azar.
        self.error(self.actual(), motivo or f'se esperaba {tipo} y se encontró {self.actual().lexema!r}')
        return None

    def _declarar(self, nombre: Token, tipo: Tipo, clase: str,
                  parametros: list[Tipo] | None = None,
                  elemento_tipo: Tipo | None = None) -> Simbolo | None:
        # Prototipo + definición de la misma función: permitido si la firma coincide.
        anterior = self.tabla.actual(nombre.lexema)
        if anterior and clase == anterior.clase == 'funcion' and (
                parametros is not None and anterior.parametros == parametros
                and anterior.tipo == tipo):
            return anterior
        sim = Simbolo(nombre.lexema, tipo, clase, nombre.linea, nombre.columna,
                      parametros=parametros or [], elemento_tipo=elemento_tipo)
        if not self.tabla.definir(sim):
            self.error(nombre, f"'{nombre.lexema}' ya fue declarado en este ámbito")
            return anterior
        return sim

    def _es_tipo(self, pos: int | None = None) -> bool:
        j = self.i if pos is None else pos
        if j >= len(self.tokens):
            return False
        t = self.tokens[j]
        if t.tipo in _TIPOS_PRIMITIVOS | _MODIFICADORES | {'KW_STRUCT'}:
            return True
        if t.tipo == 'ID':
            sim = self.tabla.buscar(t.lexema)
            if sim is not None and sim.clase == 'tipo':
                return True
            if t.lexema == 'std' and j + 2 < len(self.tokens):
                nxt = self.tokens[j + 2]
                if self.tokens[j + 1].tipo == 'OP_AMBITO':
                    otro = self.tabla.buscar(nxt.lexema)
                    return bool(otro and otro.clase == 'tipo')
        return False

    def _tipo(self) -> Tipo:
        const = False
        signos: list[str] = []
        while self.es(*_MODIFICADORES):
            t = self.tomar()
            if t.tipo in {'KW_CONST', 'KW_CONSTEXPR'}:
                const = True
            elif t.tipo in {'KW_SIGNED', 'KW_UNSIGNED'}:
                signos.append(t.lexema)
        if self.es('KW_STRUCT'):
            self.tomar()
        if self.actual().lexema == 'std' and self.sig().tipo == 'OP_AMBITO':
            self.tomar()
            self.tomar()
        if self.es('ID'):
            t = self.tomar()
            simbolo = self.tabla.buscar(t.lexema)
            if simbolo and simbolo.clase == 'tipo':
                base = simbolo.elemento_tipo or Tipo(t.lexema)
            else:
                self.error(t, f"tipo '{t.lexema}' no declarado")
                base = DESCONOCIDO
        elif self.es(*_TIPOS_PRIMITIVOS):
            partes = [self.tomar().lexema]
            while self.es('KW_LONG', 'KW_INT', 'KW_SHORT', 'KW_DOUBLE'):
                partes.append(self.tomar().lexema)
            # 'long int' -> long, 'long long int' -> long long
            if len(partes) > 1 and partes[-1] == 'int':
                partes.pop()
            base = Tipo(' '.join(partes))
        else:
            self.error(self.actual(), 'se esperaba un tipo de dato')
            return DESCONOCIDO
        if signos and base.nombre != '?':
            if base.nombre in {'int', 'short', 'long', 'long long', 'char'}:
                prefijo = signos[-1]
                base = Tipo(f'{prefijo} {base.nombre}', base.punteros, base.argumentos)
            else:
                self.error(self.actual(), 'modificador signed/unsigned no válido para este tipo')
        if self.es('OP_MENOR') and base.nombre in _CONTENEDORES | {'iterator'}:
            self.tomar()
            args: list[Tipo] = []
            while not self.es('EOF', 'OP_MAYOR', 'OP_SHR'):
                if not self._es_tipo():
                    self.error(self.actual(), 'argumento de plantilla no es un tipo conocido')
                    self._saltar_hasta({'OP_MAYOR', 'OP_SHR', 'PUNTO_COMA'})
                    break
                args.append(self._tipo())
                # Si los argumentos son punteros, preservarlos.
                args[-1] = self._aplicar_indireccion(args[-1])
                if not self.aceptar('COMA'):
                    break
            self._cerrar_plantilla()
            base = Tipo(base.nombre, base.punteros, tuple(args))
        if const:
            base = Tipo(base.nombre, base.punteros, base.argumentos,
                        base.arreglo, True, base.referencia)
        return base

    def _cerrar_plantilla(self) -> None:
        if self.aceptar('OP_MAYOR'):
            return
        if self.es('OP_SHR'):
            original = self.tomar()
            # >> en plantillas anidadas equivale a dos >; el segundo queda
            # disponible para el nivel exterior, sin alterar el lexer.
            self.tokens.insert(self.i, Token('OP_MAYOR', '>', original.linea,
                                             original.columna + 1))
            return
        self.error(self.actual(), 'faltó > al cerrar los argumentos de plantilla')

    def _aplicar_indireccion(self, base: Tipo) -> Tipo:
        ptrs = 0
        ref = False
        while self.es('OP_MULT', 'OP_AND_BIT'):
            t = self.tomar()
            if t.tipo == 'OP_MULT':
                ptrs += 1
            else:
                ref = True
        return Tipo(base.nombre, base.punteros + ptrs, base.argumentos,
                    base.arreglo, base.constante, ref)

    def _saltar_hasta(self, topes: set[str]) -> None:
        while not self.es('EOF') and not self.es(*topes):
            self.tomar()

    def _macro(self) -> None:
        t = self.tomar()
        nombre, reemplazo = t.valor
        nombre_tok = Token('ID', nombre, t.linea, t.columna, nombre)
        rtokens, errores = tokenizar(reemplazo)
        tip = DESCONOCIDO
        clase = 'macro'
        destino = None
        utiles = [x for x in rtokens if x.tipo != 'EOF']
        if not errores and utiles:
            if len(utiles) == 1:
                u = utiles[0]
                if u.tipo in {'LIT_INT', 'LIT_HEX'}:
                    tip = self._tipo_entero(u)
                elif u.tipo == 'LIT_FLOAT':
                    tip = self._tipo_float(u)
                elif u.tipo == 'LIT_STRING':
                    tip = Tipo('const char*')
                elif u.tipo == 'LIT_BOOL':
                    tip = Tipo('bool')
                elif u.tipo == 'ID':
                    origen = self.tabla.buscar(u.lexema)
                    if origen:
                        tip = origen.tipo
                        if origen.clase == 'tipo':
                            clase = 'tipo'
                            destino = origen.elemento_tipo or origen.tipo
            elif all(x.tipo in _TIPOS_PRIMITIVOS | _MODIFICADORES for x in utiles):
                # Ej.: #define ll long long
                texto = [x.lexema for x in utiles if x.tipo not in {'KW_CONSTEXPR', 'KW_STATIC'}]
                if texto and texto[-1] == 'int' and len(texto) > 1:
                    texto.pop()
                tip = Tipo(' '.join(texto))
                clase = 'tipo'
                destino = tip
        self._declarar(nombre_tok, tip, clase, elemento_tipo=destino)

    def _typedef(self) -> None:
        self.tomar()
        base = self._tipo()
        base = self._aplicar_indireccion(base)
        alias = self.esperar('ID', 'se esperaba el nombre del alias typedef')
        if alias:
            self._declarar(alias, base, 'tipo', elemento_tipo=base)
        self.esperar('PUNTO_COMA')

    def _using(self) -> None:
        self.tomar()
        if self.aceptar('KW_NAMESPACE'):
            self._saltar_hasta({'PUNTO_COMA', 'EOF'})
            self.aceptar('PUNTO_COMA')
            return
        if self.es('ID') and self.sig().tipo == 'OP_ASIG':
            nombre = self.tomar()
            self.tomar()
            tp = self._aplicar_indireccion(self._tipo())
            self._declarar(nombre, tp, 'tipo', elemento_tipo=tp)
            self.esperar('PUNTO_COMA')
            return
        self._saltar_hasta({'PUNTO_COMA', 'EOF'})
        self.aceptar('PUNTO_COMA')

    def _struct(self) -> None:
        self.tomar()  # struct
        nombre = self.esperar('ID', 'se esperaba el nombre de la estructura')
        if not nombre:
            return
        if not self.es('LLAVE_IZQ'):
            # 'struct Nodo *x;' se resuelve como declaración.
            self.i -= 2
            self._declaracion()
            return
        sim = self._declarar(nombre, Tipo(nombre.lexema), 'tipo',
                            elemento_tipo=Tipo(nombre.lexema))
        if sim:
            self.estructuras[nombre.lexema] = sim
        self.tomar()
        previo = self.struct_actual
        self.struct_actual = nombre.lexema
        self.tabla.abrir('struct_' + nombre.lexema)
        while not self.es('EOF', 'LLAVE_DER'):
            inicio = self.i
            if self.es('KW_USING'):
                self._using()
            elif self.es('ID') and self.actual().lexema == nombre.lexema and self.sig().tipo == 'PAR_IZQ':
                self._constructor(nombre.lexema)
            else:
                self._sentencia()
            if self.i == inicio:
                self.error(self.actual(), 'declaración de miembro no reconocida')
                self.tomar()
        self.esperar('LLAVE_DER', 'faltó cerrar estructura con }')
        self.tabla.cerrar()
        self.struct_actual = previo
        self.aceptar('PUNTO_COMA')

    def _constructor(self, clase: str) -> None:
        nombre = self.tomar()
        parametros = self._parametros()
        actual = self.estructuras.get(clase)
        if actual:
            actual.campos[f'{clase}()'] = Simbolo(nombre.lexema, Tipo(clase),
                                                'constructor', parametros=[p[1] for p in parametros])
        self._cuerpo_funcion(nombre, Tipo('void'), parametros, clase)

    def _parametros(self) -> list[tuple[Token, Tipo]]:
        self.esperar('PAR_IZQ')
        resultado: list[tuple[Token, Tipo]] = []
        if self.es('KW_VOID') and self.sig().tipo == 'PAR_DER':
            self.tomar()
        else:
            while not self.es('EOF', 'PAR_DER'):
                inicio = self.i
                if not self._es_tipo():
                    self.error(self.actual(), 'parámetro sin tipo declarado')
                    self._saltar_hasta({'COMA', 'PAR_DER', 'EOF'})
                else:
                    tp = self._aplicar_indireccion(self._tipo())
                    if self.es('ID'):
                        nombre = self.tomar()
                    else:
                        nombre = Token('ID', f'__param{len(resultado)}',
                                       self.actual().linea, self.actual().columna)
                    if self.aceptar('COR_IZQ'):
                        if not self.es('COR_DER'):
                            self._expr()
                        self.esperar('COR_DER')
                        tp = Tipo(tp.nombre, tp.punteros, tp.argumentos, True)
                    resultado.append((nombre, tp))
                    if self.aceptar('OP_ASIG'):
                        self._expr(2)
                if self.i == inicio:
                    self.tomar()
                if not self.aceptar('COMA'):
                    break
        self.esperar('PAR_DER', 'faltó ) en los parámetros')
        return resultado

    def _parece_funcion(self) -> bool:
        if not self.es('PAR_IZQ'):
            return False
        return self.sig().tipo == 'PAR_DER' or self._es_tipo(self.i + 1)

    def _declaracion(self, terminar: str = 'PUNTO_COMA') -> None:
        base = self._tipo()
        while True:
            tp = self._aplicar_indireccion(base)
            if self.es('KW_OPERATOR'):
                op = self.tomar()
                suf = self.tomar()
                nombre = Token('ID', 'operator' + suf.lexema, op.linea, op.columna)
            else:
                nombre = self.esperar('ID', 'se esperaba nombre de variable o función')
            if not nombre:
                self._saltar_hasta({terminar, 'PUNTO_COMA', 'LLAVE_DER', 'EOF'})
                self.aceptar(terminar)
                return
            if self.es('PAR_IZQ') and (self._parece_funcion() or nombre.lexema.startswith('operator')):
                params = self._parametros()
                firmas = [t for _, t in params]
                sim = self._declarar(nombre, tp, 'funcion', firmas)
                if self.struct_actual and sim:
                    estr = self.estructuras.get(self.struct_actual)
                    if estr:
                        estr.campos[nombre.lexema] = sim
                self._cuerpo_funcion(nombre, tp, params, self.struct_actual)
                return
            if self.aceptar('COR_IZQ'):
                if not self.es('COR_DER'):
                    tam = self._expr()
                    if tam.tipo.nombre != '?' and not es_integral(tam.tipo):
                        self.error(nombre, 'el tamaño del arreglo debe ser un entero')
                self.esperar('COR_DER')
                tp = Tipo(tp.nombre, tp.punteros, tp.argumentos, True)
            inicial = None
            init_con_llaves = False
            if self.aceptar('OP_ASIG'):
                init_con_llaves = self.es('LLAVE_IZQ')
                inicial = self._inicializador(tp)
            elif self.es('PAR_IZQ'):
                self.tomar()
                if not self.es('PAR_DER'):
                    inicial = self._expr(2)
                    while self.aceptar('COMA'):
                        self._expr(2)
                self.esperar('PAR_DER')
                # constructor estilo vector<int> a(n), no se compara n con vector.
                if tp.nombre in _CONTENEDORES or tp.nombre in self.estructuras:
                    inicial = None
            elif self.es('LLAVE_IZQ'):
                init_con_llaves = True
                inicial = self._inicializador(tp)
            if tp.nombre == 'auto':
                if inicial is None or inicial.tipo.nombre == '?':
                    if terminar != 'DOS_PUNTOS':
                        self.error(nombre, f"'auto {nombre.lexema}' requiere inicializador con tipo deducible")
                        tp = DESCONOCIDO
                else:
                    tp = inicial.tipo.sin_referencia()
            if tp.nombre == 'void' and tp.punteros == 0:
                self.error(nombre, f"variable '{nombre.lexema}' no puede ser de tipo void")
            if inicial and not (init_con_llaves and tp.arreglo) and not compatibles(tp, inicial.tipo):
                self.error(nombre, f"no se puede asignar '{inicial.tipo}' a '{tp}' en '{nombre.lexema}'")
            clase = 'campo' if self.struct_actual and len(self.tabla.nombres) == 2 else 'variable'
            sim = self._declarar(nombre, tp, clase)
            if clase == 'campo' and sim:
                estructura = self.estructuras.get(self.struct_actual or '')
                if estructura:
                    estructura.campos[nombre.lexema] = sim
            if not self.aceptar('COMA'):
                break
        if terminar == 'DOS_PUNTOS':
            return
        self.esperar(terminar, 'faltó ; después de una declaración')

    def _inicializador(self, esperado: Tipo | None = None) -> Expresion:
        if self.aceptar('LLAVE_IZQ'):
            elementos: list[Expresion] = []
            elemento_esperado = (esperado.contenido() if esperado and
                                 (esperado.arreglo or esperado.nombre in _CONTENEDORES)
                                 else esperado)
            while not self.es('LLAVE_DER', 'EOF'):
                inicio = self.i
                valor = self._inicializador(elemento_esperado) if self.es('LLAVE_IZQ') else self._expr(2)
                elementos.append(valor)
                if elemento_esperado and not compatibles(elemento_esperado, valor.tipo):
                    self.error(self.tokens[inicio],
                               f"elemento '{valor.tipo}' incompatible con '{elemento_esperado}'")
                if not self.aceptar('COMA'):
                    break
            self.esperar('LLAVE_DER')
            if esperado:
                if (not esperado.arreglo and esperado.nombre not in _CONTENEDORES
                        and len(elementos) > 1):
                    self.error(self.actual(),
                               f"inicializador de '{esperado}' contiene más de un elemento")
                return Expresion(esperado)
            return elementos[0] if elementos else Expresion()
        return self._expr(2)

    def _cuerpo_funcion(self, nombre: Token, retorno: Tipo,
                       parametros: list[tuple[Token, Tipo]],
                       clase: str | None) -> None:
        self.aceptar('KW_CONST')  # método ...() const
        if self.aceptar('DOS_PUNTOS'):
            # Los inicializadores de constructor se evalúan con acceso a
            # parámetros y a los campos del struct, ANTES de entrar al cuerpo.
            self.tabla.abrir('inicializadores_' + nombre.lexema)
            estr = self.estructuras.get(clase or '')
            if estr:
                for campo in estr.campos.values():
                    if campo.clase == 'campo':
                        self.tabla.definir(Simbolo(campo.nombre, campo.tipo,
                                                  'campo', interno=True))
            for parametro, tipo_param in parametros:
                self.tabla.definir(Simbolo(parametro.lexema, tipo_param,
                                          'parametro', interno=True))
            while not self.es('LLAVE_IZQ', 'EOF', 'PUNTO_COMA'):
                campo = self.esperar('ID', 'se esperaba campo en lista de inicializadores')
                if not campo:
                    break
                s = estr.campos.get(campo.lexema) if estr else None
                if estr and not s:
                    self.error(campo, f"estructura '{clase}' no tiene campo '{campo.lexema}'")
                if self.aceptar('PAR_IZQ'):
                    argumentos = self._argumentos('PAR_DER')
                elif self.es('LLAVE_IZQ'):
                    argumentos = [self._inicializador(s.tipo if s else None)]
                else:
                    self.error(self.actual(), 'se esperaba ( o { en el inicializador')
                    break
                if s and argumentos and not compatibles(s.tipo, argumentos[0].tipo):
                    self.error(campo, f"inicialización de '{campo.lexema}' incompatible: "
                                      f"'{argumentos[0].tipo}' no es '{s.tipo}'")
                if not self.aceptar('COMA'):
                    break
            self.tabla.cerrar()
        if self.aceptar('PUNTO_COMA'):
            return  # prototipo
        if not self.es('LLAVE_IZQ'):
            self.error(self.actual(), f"se esperaba cuerpo o ; en función '{nombre.lexema}'")
            return
        sim = self.tabla.actual(nombre.lexema)
        if sim and sim.clase == 'funcion':
            if sim.definida:
                self.error(nombre, f"definición duplicada de la función '{nombre.lexema}'")
            else:
                sim.definida = True
        self.retorno.append(retorno)
        self._bloque('funcion_' + nombre.lexema, parametros, clase)
        self.retorno.pop()

    def _bloque(self, nombre: str = 'bloque',
                parametros: list[tuple[Token, Tipo]] | None = None,
                clase: str | None = None) -> None:
        self.esperar('LLAVE_IZQ')
        self.tabla.abrir(nombre)
        if clase:
            estr = self.estructuras.get(clase)
            if estr:
                for campo in estr.campos.values():
                    if campo.clase == 'campo':
                        copia = Simbolo(campo.nombre, campo.tipo, 'campo', interno=True)
                        self.tabla.definir(copia)
        for tok, tipo in parametros or []:
            self._declarar(tok, tipo, 'parametro')
        while not self.es('EOF', 'LLAVE_DER'):
            i = self.i
            self._sentencia()
            if i == self.i:
                self.error(self.actual(), 'no se pudo analizar la instrucción')
                self.tomar()
        self.esperar('LLAVE_DER', 'faltó } al cerrar el bloque')
        self.tabla.cerrar()

    def _condicion(self) -> None:
        self.esperar('PAR_IZQ')
        if self._es_tipo():
            self._declaracion(terminar='PAR_DER')
        else:
            valor = self._expr()
            if valor.tipo.nombre not in {'?', 'bool', 'nullptr'} and not (
                    es_numerico(valor.tipo) or valor.tipo.punteros):
                self.error(self.actual(), f"condición de tipo '{valor.tipo}' no convertible a bool")
            self.esperar('PAR_DER')

    def _if(self) -> None:
        self.tomar()
        self.tabla.abrir('if')
        self._condicion()
        self._sentencia()
        if self.aceptar('KW_ELSE'):
            self._sentencia()
        self.tabla.cerrar()

    def _while(self) -> None:
        self.tomar()
        self.tabla.abrir('while')
        self._condicion()
        self.en_bucle += 1
        self._sentencia()
        self.en_bucle -= 1
        self.tabla.cerrar()

    def _for(self) -> None:
        self.tomar()
        self.tabla.abrir('for')
        self.esperar('PAR_IZQ')
        rango = False
        if self._es_tipo():
            previo = len(self.tabla.historial)
            self._declaracion(terminar='DOS_PUNTOS')
            if self.aceptar('DOS_PUNTOS'):
                rango = True
                iterable = self._expr(2)
                if len(self.tabla.historial) > previo:
                    var = self.tabla.historial[-1]
                    elemento = iterable.tipo.contenido()
                    if elemento.nombre == '?' and iterable.tipo.nombre != '?':
                        self.error(self.actual(),
                                   f"no se puede recorrer el tipo '{iterable.tipo}' en for de rango")
                    if var.tipo.nombre in {'auto', '?'}:
                        var.tipo = elemento
                    elif elemento.nombre != '?' and not compatibles(var.tipo, elemento):
                        self.error(self.actual(),
                                   f"variable de rango '{var.tipo}' incompatible con elemento '{elemento}'")
                self.esperar('PAR_DER')
            else:
                self.esperar('PUNTO_COMA')
        else:
            if not self.es('PUNTO_COMA'):
                self._expr(2)
            if self.aceptar('DOS_PUNTOS'):
                rango = True
                self._expr(2)
                self.esperar('PAR_DER')
            else:
                self.esperar('PUNTO_COMA')
        if not rango:
            # En el for tradicional, auto también requiere un inicializador.
            if self.tabla.pilas[-1]:
                for sim in self.tabla.pilas[-1].values():
                    if sim.tipo.nombre == 'auto':
                        self.error(Token('ID', sim.nombre, sim.linea, sim.columna),
                                   f"'auto {sim.nombre}' requiere inicializador con tipo deducible")
            if not self.es('PUNTO_COMA'):
                self._expr()
            self.esperar('PUNTO_COMA')
            if not self.es('PAR_DER'):
                self._expr()
            self.esperar('PAR_DER')
        self.en_bucle += 1
        self._sentencia()
        self.en_bucle -= 1
        self.tabla.cerrar()

    def _return(self) -> None:
        tok = self.tomar()
        valor = None if self.es('PUNTO_COMA') else self._expr()
        if not self.retorno:
            self.error(tok, 'return fuera de una función')
        else:
            esperado = self.retorno[-1]
            if esperado.nombre == 'void' and valor is not None:
                self.error(tok, 'una función void no puede devolver un valor')
            elif esperado.nombre != 'void' and valor is None:
                self.error(tok, f"la función debe retornar un valor de tipo '{esperado}'")
            elif valor is not None and not compatibles(esperado, valor.tipo):
                self.error(tok, f"return de tipo '{valor.tipo}' incompatible con '{esperado}'")
        self.esperar('PUNTO_COMA')

    def _sentencia(self) -> None:
        if self.es('EOF'):
            return
        if self.es('DIR_INCLUDE'):
            self.tomar()
        elif self.es('DIR_DEFINE'):
            self._macro()
        elif self.es('KW_USING'):
            self._using()
        elif self.es('KW_TYPEDEF'):
            self._typedef()
        elif self.es('KW_STRUCT') and self.sig().tipo == 'ID' and self.sig(2).tipo == 'LLAVE_IZQ':
            self._struct()
        elif self.es('LLAVE_IZQ'):
            self._bloque()
        elif self.es('KW_IF'):
            self._if()
        elif self.es('KW_WHILE', 'KW_SWITCH'):
            self._while()
        elif self.es('KW_FOR'):
            self._for()
        elif self.es('KW_DO'):
            self.tomar()
            self.en_bucle += 1
            self._sentencia()
            self.en_bucle -= 1
            if self.aceptar('KW_WHILE'):
                self._condicion()
            self.esperar('PUNTO_COMA')
        elif self.es('KW_RETURN'):
            self._return()
        elif self.es('KW_CASE', 'KW_DEFAULT'):
            if self.aceptar('KW_CASE'):
                self._expr(2)
            else:
                self.tomar()
            self.esperar('DOS_PUNTOS')
        elif self.es('KW_BREAK', 'KW_CONTINUE'):
            t = self.tomar()
            if self.en_bucle == 0 and t.tipo == 'KW_CONTINUE':
                self.error(t, 'continue fuera de un ciclo')
            self.esperar('PUNTO_COMA')
        elif self.aceptar('PUNTO_COMA'):
            pass
        elif self._es_tipo():
            self._declaracion()
        else:
            self._expr()
            self.esperar('PUNTO_COMA', 'faltó ; al terminar la instrucción')

    def _tipo_entero(self, tok: Token) -> Tipo:
        lex = tok.lexema.lower()
        # Ignorar parte hexadecimal al revisar el sufijo.
        suf = re.search(r'(ull|llu|ll|ul|lu|u|l)$', lex)
        x = suf.group(1) if suf else ''
        return Tipo(('unsigned ' if 'u' in x else '') +
                    ('long long' if 'll' in x else 'long' if 'l' in x else 'int'))

    def _tipo_float(self, tok: Token) -> Tipo:
        return Tipo('float' if tok.lexema[-1:] in ('f', 'F') else 'double')

    def _expr(self, minimo: int = 1) -> Expresion:
        izquierda = self._unaria()
        while True:
            tok = self.actual()
            if tok.tipo == 'OP_TERNARIO' and minimo <= 2:
                self.tomar()
                positivo = self._expr(1)
                self.esperar('DOS_PUNTOS')
                negativo = self._expr(2)
                izquierda = Expresion(tipo_comun(positivo.tipo, negativo.tipo))
                continue
            prec = 1 if tok.tipo in _ASIGNACIONES else _BINARIOS.get(tok.tipo, -1)
            if prec < minimo:
                break
            self.tomar()
            derecha = self._expr(prec if tok.tipo in _ASIGNACIONES else prec + 1)
            if tok.tipo in _ASIGNACIONES:
                if not izquierda.asignable and izquierda.tipo.nombre != '?':
                    self.error(tok, 'el lado izquierdo de la asignación no es modificable')
                if izquierda.tipo.constante:
                    self.error(tok, 'no se puede modificar una variable const')
                agrega_char_a_string = (tok.tipo == 'OP_SUMA_ASIG' and
                                       izquierda.tipo.nombre == 'string' and
                                       derecha.tipo.nombre == 'char')
                if not agrega_char_a_string and not compatibles(izquierda.tipo, derecha.tipo):
                    self.error(tok, f"asignación incompatible: '{derecha.tipo}' a '{izquierda.tipo}'")
                if tok.tipo != 'OP_ASIG' and izquierda.tipo.nombre != '?':
                    tipo_izq = izquierda.tipo
                    tipo_der = derecha.tipo
                    if (tok.tipo == 'OP_SUMA_ASIG' and tipo_izq.nombre == 'string'
                            and tipo_der.nombre in {'string', 'const char*', 'char'}):
                        permitido = True
                    elif tok.tipo in {'OP_MOD_ASIG', 'OP_AND_ASIG', 'OP_OR_ASIG',
                                      'OP_XOR_ASIG', 'OP_SHL_ASIG', 'OP_SHR_ASIG'}:
                        permitido = es_integral(tipo_izq) and es_integral(tipo_der)
                    else:
                        permitido = es_numerico(tipo_izq) and es_numerico(tipo_der)
                    if not permitido and tipo_der.nombre != '?':
                        self.error(tok, f"operador '{tok.lexema}' no aplicable a "
                                        f"'{tipo_izq}' y '{tipo_der}'")
                izquierda = Expresion(izquierda.tipo)
            else:
                izquierda = self._operar(tok, izquierda, derecha)
        return izquierda

    def _operar(self, tok: Token, izq: Expresion, der: Expresion) -> Expresion:
        a, b = izq.tipo, der.tipo
        if a.nombre == '?' or b.nombre == '?':
            return Expresion(DESCONOCIDO)
        if tok.tipo in {'OP_SHL', 'OP_SHR'} and a.nombre in {'istream', 'ostream'}:
            return Expresion(a)
        if tok.tipo in {'OP_IGUAL', 'OP_DIST'}:
            if not (compatibles(a, b) or compatibles(b, a)):
                self.error(tok, f"comparación incompatible entre '{a}' y '{b}'")
            return Expresion(Tipo('bool'))
        if tok.tipo in {'OP_MENOR', 'OP_MENOR_IG', 'OP_MAYOR', 'OP_MAYOR_IG'}:
            if not (es_numerico(a) and es_numerico(b)) and a != b:
                self.error(tok, f"comparación de orden incompatible entre '{a}' y '{b}'")
            return Expresion(Tipo('bool'))
        if tok.tipo in {'OP_OR', 'OP_AND'}:
            if not all(es_numerico(t) or t.punteros for t in (a, b)):
                self.error(tok, f"operador lógico '{tok.lexema}' no acepta '{a}' y '{b}'")
            return Expresion(Tipo('bool'))
        if tok.tipo in {'OP_AND_BIT', 'OP_OR_BIT', 'OP_XOR', 'OP_SHL', 'OP_SHR', 'OP_MOD'}:
            if not (es_integral(a) and es_integral(b)):
                self.error(tok, f"operador '{tok.lexema}' requiere operandos enteros: '{a}', '{b}'")
            return Expresion(tipo_comun(a, b))
        if tok.tipo == 'OP_SUMA' and (a.nombre == 'string' or b.nombre == 'string'):
            if a.nombre == b.nombre == 'string' or {a.nombre, b.nombre} == {'string', 'const char*'}:
                return Expresion(Tipo('string'))
        if tok.tipo in {'OP_SUMA', 'OP_RESTA'} and a.punteros and es_integral(b):
            return Expresion(a)
        if not (es_numerico(a) and es_numerico(b)):
            self.error(tok, f"operador '{tok.lexema}' incompatible con '{a}' y '{b}'")
        return Expresion(tipo_comun(a, b))

    def _unaria(self) -> Expresion:
        tok = self.actual()
        if tok.tipo in {'OP_NOT', 'OP_NOT_BIT', 'OP_SUMA', 'OP_RESTA',
                        'OP_MULT', 'OP_AND_BIT', 'OP_INC', 'OP_DEC'}:
            self.tomar()
            op = self._unaria()
            if tok.tipo == 'OP_AND_BIT':
                if not op.asignable:
                    self.error(tok, 'el operador & requiere una expresión direccionable')
                return Expresion(op.tipo.puntero_a())
            if tok.tipo == 'OP_MULT':
                if not op.tipo.punteros and op.tipo.nombre != '?':
                    self.error(tok, f"no se puede desreferenciar '{op.tipo}'")
                return Expresion(op.tipo.contenido(), True)
            if tok.tipo in {'OP_INC', 'OP_DEC'}:
                if not op.asignable or op.tipo.constante:
                    self.error(tok, f"'{tok.lexema}' requiere variable modificable")
            if tok.tipo == 'OP_NOT':
                return Expresion(Tipo('bool'))
            if tok.tipo == 'OP_NOT_BIT' and not es_integral(op.tipo) and op.tipo.nombre != '?':
                self.error(tok, 'operador ~ requiere entero')
            if tok.tipo in {'OP_SUMA', 'OP_RESTA'} and not es_numerico(op.tipo) and op.tipo.nombre != '?':
                self.error(tok, f"operador unario '{tok.lexema}' requiere número")
            return Expresion(op.tipo)
        if tok.tipo == 'KW_NEW':
            self.tomar()
            if not self._es_tipo():
                self.error(tok, 'new requiere un tipo declarado')
                return Expresion()
            tp = self._tipo()
            if self.aceptar('PAR_IZQ'):
                self._argumentos('PAR_DER')
            elif self.aceptar('COR_IZQ'):
                self._expr()
                self.esperar('COR_DER')
            return Expresion(tp.puntero_a())
        if tok.tipo == 'KW_DELETE':
            self.tomar()
            if self.aceptar('COR_IZQ'):
                self.esperar('COR_DER')
            valor = self._unaria()
            if not valor.tipo.punteros and valor.tipo.nombre != '?':
                self.error(tok, f"delete requiere puntero, recibió '{valor.tipo}'")
            return Expresion(Tipo('void'))
        if tok.tipo == 'KW_SIZEOF':
            self.tomar()
            if self.aceptar('PAR_IZQ'):
                if self._es_tipo():
                    self._aplicar_indireccion(self._tipo())
                else:
                    self._expr()
                self.esperar('PAR_DER')
            else:
                self._unaria()
            return Expresion(Tipo('unsigned long'))
        return self._postfija()

    def _postfija(self) -> Expresion:
        valor = self._primaria()
        while True:
            if self.aceptar('PAR_IZQ'):
                argumentos = self._argumentos('PAR_DER')
                sim = valor.simbolo
                if sim and sim.clase == 'funcion' and not sim.interno:
                    if len(sim.parametros) != len(argumentos):
                        self.error(self.tokens[self.i - 1],
                                   f"función '{sim.nombre}' espera {len(sim.parametros)} argumentos, recibió {len(argumentos)}")
                    for ix, (esperado, obtenido) in enumerate(zip(sim.parametros, argumentos), 1):
                        if not compatibles(esperado, obtenido.tipo):
                            self.error(self.tokens[self.i - 1],
                                       f"argumento {ix} de '{sim.nombre}': '{obtenido.tipo}' no compatible con '{esperado}'")
                elif sim and sim.clase not in {'funcion', 'constructor', 'biblioteca'} and valor.tipo.nombre != '?':
                    self.error(self.actual(), f"'{sim.nombre}' no es una función")
                valor = Expresion(valor.tipo)
            elif self.aceptar('COR_IZQ'):
                indice = self._expr()
                self.esperar('COR_DER')
                if indice.tipo.nombre != '?' and not es_integral(indice.tipo):
                    self.error(self.actual(), 'índice de arreglo o vector debe ser entero')
                tipo = valor.tipo.contenido()
                if tipo.nombre == '?' and valor.tipo.nombre != '?':
                    self.error(self.actual(), f"el tipo '{valor.tipo}' no admite indexación")
                valor = Expresion(tipo, True)
            elif self.es('OP_PUNTO', 'OP_FLECHA', 'OP_AMBITO'):
                operador = self.tomar()
                miembro = self.esperar('ID', 'se esperaba nombre de miembro')
                if not miembro:
                    break
                valor = self._acceso_miembro(valor, operador, miembro)
            elif self.es('OP_INC', 'OP_DEC'):
                tok = self.tomar()
                if (not valor.asignable or valor.tipo.constante) and valor.tipo.nombre != '?':
                    self.error(tok, f"'{tok.lexema}' requiere variable modificable")
                valor = Expresion(valor.tipo)
            else:
                break
        return valor

    def _argumentos(self, cierre: str) -> list[Expresion]:
        args: list[Expresion] = []
        while not self.es(cierre, 'EOF'):
            j = self.i
            args.append(self._expr(2))
            if self.i == j:
                self.tomar()
            if not self.aceptar('COMA'):
                break
        self.esperar(cierre)
        return args

    def _acceso_miembro(self, objeto: Expresion, operador: Token, miembro: Token) -> Expresion:
        t = objeto.tipo
        if t.nombre == '?':
            return Expresion()
        if operador.tipo == 'OP_AMBITO':
            if t.nombre not in {'namespace'} and not (
                    objeto.simbolo and objeto.simbolo.clase in {'tipo', 'namespace'}):
                self.error(operador, f"'::' requiere namespace o tipo, recibió '{t}'")
            # std::vector, ios::sync_with_stdio, etc.
            sim = self.tabla.buscar(miembro.lexema)
            if sim and sim.clase == 'tipo':
                return Expresion(sim.tipo, simbolo=sim)
            return Expresion(DESCONOCIDO, simbolo=Simbolo(miembro.lexema, DESCONOCIDO,
                                                           'funcion', interno=True))
        if operador.tipo == 'OP_FLECHA' and not t.punteros:
            self.error(operador, f"'->' requiere puntero, recibió '{t}'")
            return Expresion()
        if operador.tipo == 'OP_PUNTO' and t.punteros:
            self.error(operador, f"'.' no accede a punteros '{t}'; use '->'")
            return Expresion()
        base = t.contenido() if operador.tipo == 'OP_FLECHA' else t
        est = self.estructuras.get(base.nombre)
        if est:
            simbolo = est.campos.get(miembro.lexema)
            if not simbolo:
                self.error(miembro, f"estructura '{base.nombre}' no tiene miembro '{miembro.lexema}'")
                return Expresion()
            return Expresion(simbolo.tipo, simbolo.clase == 'campo', simbolo)
        if base.nombre in _CONTENEDORES | {'string', 'istream', 'ostream'}:
            # Métodos de STL permitidos en este subconjunto.
            metodos = {'size', 'empty', 'begin', 'end', 'push_back', 'pop_back',
                       'front', 'back', 'clear', 'resize', 'reserve', 'at', 'insert',
                       'erase', 'find', 'count', 'top', 'push', 'pop', 'first', 'second',
                       'tie', 'sync_with_stdio', 'good', 'fail', 'substr', 'c_str'}
            if miembro.lexema not in metodos:
                self.error(miembro, f"miembro '{miembro.lexema}' desconocido para '{base.nombre}'")
            if miembro.lexema in {'size', 'count'}:
                salida = Tipo('size_t')
            elif miembro.lexema in {'empty', 'good', 'fail'}:
                salida = Tipo('bool')
            elif miembro.lexema in {'front', 'back', 'at', 'first', 'second', 'top'}:
                salida = base.contenido()
            elif miembro.lexema in {'begin', 'end', 'find'}:
                salida = Tipo('iterator', argumentos=(base.contenido(),))
            elif miembro.lexema == 'tie':
                salida = Tipo('ostream')
            else:
                salida = Tipo('void')
            if miembro.lexema in {'first', 'second'}:
                if base.nombre == 'pair' and len(base.argumentos) == 2:
                    salida = base.argumentos[0 if miembro.lexema == 'first' else 1]
                return Expresion(salida, True)
            return Expresion(salida, simbolo=Simbolo(miembro.lexema, salida,
                                                     'funcion', interno=True))
        self.error(miembro, f"el tipo '{base}' no contiene miembros accesibles")
        return Expresion()

    def _primaria(self) -> Expresion:
        tok = self.actual()
        if tok.tipo in {'LIT_INT', 'LIT_HEX'}:
            self.tomar()
            return Expresion(self._tipo_entero(tok))
        if tok.tipo == 'LIT_FLOAT':
            self.tomar()
            return Expresion(self._tipo_float(tok))
        if tok.tipo == 'LIT_CHAR':
            self.tomar()
            return Expresion(Tipo('char'))
        if tok.tipo == 'LIT_STRING':
            self.tomar()
            return Expresion(Tipo('const char*'))
        if tok.tipo == 'LIT_BOOL':
            self.tomar()
            return Expresion(Tipo('bool'))
        if tok.tipo == 'LIT_NULLPTR':
            self.tomar()
            return Expresion(NULO)
        if tok.tipo == 'ID':
            self.tomar()
            sim = self.tabla.buscar(tok.lexema)
            if not sim:
                self.error(tok, f"identificador '{tok.lexema}' no declarado")
                return Expresion()
            return Expresion(sim.tipo, sim.clase in {'variable', 'parametro', 'campo'}, sim)
        if tok.tipo == 'KW_THIS':
            self.tomar()
            if not self.struct_actual:
                self.error(tok, 'this fuera de un método de estructura')
                return Expresion()
            return Expresion(Tipo(self.struct_actual, punteros=1))
        if self.aceptar('PAR_IZQ'):
            val = self._expr()
            self.esperar('PAR_DER')
            return val
        if tok.tipo == 'LLAVE_IZQ':
            return self._inicializador()
        # Fallo estructural: evita loops y evita declarar falsos positivos.
        self.error(tok, f"expresión no reconocida cerca de '{tok.lexema}'")
        if tok.tipo != 'EOF':
            self.tomar()
        return Expresion()

    def ejecutar(self) -> ResultadoSemantico:
        while not self.es('EOF'):
            j = self.i
            self._sentencia()
            if self.i == j:
                self.error(self.actual(), 'no se pudo avanzar en el análisis')
                self.tomar()
        return ResultadoSemantico(self.tabla.historial[:], self.errores[:])


def analizar_tokens(tokens: list[Token]) -> ResultadoSemantico:
    """Analiza tokens ya generados SIN volver a ejecutar el lexer.

    Debe llamarse solo si no hubo errores léxicos, porque los lexemas
    inválidos no generan token y provocarían diagnósticos falsos.
    """
    return AnalizadorSemantico(tokens).ejecutar()


def analizar(codigo: str) -> ResultadoSemantico:
    """Punto de entrada recomendado: léxico -> semántico, con corte por errores."""
    tokens, errores_lexicos = tokenizar(codigo)
    if errores_lexicos:
        return ResultadoSemantico([], [], errores_lexicos)
    resultado = analizar_tokens(tokens)
    resultado.errores_lexicos = []
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description='Analizador semántico TLP02-2026')
    parser.add_argument('archivo', help='Archivo C++ (.cpp) que se analizará')
    parser.add_argument('--tabla', action='store_true', help='Mostrar tabla de símbolos')
    parser.add_argument('--json', action='store_true', help='Mostrar reporte JSON')
    args = parser.parse_args()
    try:
        codigo = Path(args.archivo).read_text(encoding='utf-8')
    except OSError as e:
        parser.error(str(e))
    reporte = analizar(codigo)
    if args.json:
        print(json.dumps(reporte.como_diccionario(), ensure_ascii=False, indent=2))
    else:
        for e in reporte.errores_lexicos or []:
            print(e)
        for e in reporte.errores:
            print(e)
        if reporte.correcto:
            print('Análisis semántico correcto: sin errores léxicos ni semánticos.')
        else:
            print(f'Análisis finalizado: {len(reporte.errores_lexicos or [])} error(es) léxico(s), '
                  f'{len(reporte.errores)} error(es) semántico(s).')
        if args.tabla:
            print('\nTABLA DE SÍMBOLOS (sin biblioteca precargada)')
            print(f"{'Nombre':<20} {'Clase':<14} {'Tipo':<26} {'Ámbito'}")
            print('-' * 90)
            for s in reporte.simbolos:
                print(f'{s.nombre:<20} {s.clase:<14} {str(s.tipo):<26} {s.ambito}')
    return 0 if reporte.correcto else 1


if __name__ == '__main__':
    raise SystemExit(main())
