"""Validacion de lo que devuelve el modelo de IA (TR-80), sin dependencias externas.

El modelo solo propone: antes de usar cualquier dato se valida contra un esquema. Lo que no cumple se rechaza entero
(no se corrige a medias) y los campos que el esquema no declara se descartan.
"""
from __future__ import annotations


class ErrorEsquema(ValueError):
    """La salida del modelo no cumple el esquema. El mensaje dice donde, nunca incluye el contenido completo."""


def _ruta(ruta: str, extra: str) -> str:
    return f"{ruta}.{extra}" if ruta else extra


class _Tipo:
    def __init__(self, nullable: bool = False):
        self.nullable = nullable

    def validar(self, valor, ruta: str = ""):
        if valor is None:
            if self.nullable:
                return None
            raise ErrorEsquema(f"{ruta or 'valor'}: es obligatorio")
        return self._validar(valor, ruta or "valor")

    def _validar(self, valor, ruta: str):  # pragma: no cover - lo implementa cada tipo
        raise NotImplementedError


class Texto(_Tipo):
    def __init__(self, max_len: int = 200, nullable: bool = False):
        super().__init__(nullable)
        self.max_len = max_len

    def _validar(self, valor, ruta):
        if not isinstance(valor, str):
            raise ErrorEsquema(f"{ruta}: debe ser texto")
        limpio = valor.strip()
        if not limpio:
            if self.nullable:
                return None
            raise ErrorEsquema(f"{ruta}: no puede estar vacío")
        if len(limpio) > self.max_len:
            raise ErrorEsquema(f"{ruta}: supera {self.max_len} caracteres")
        return limpio


class Entero(_Tipo):
    def __init__(self, minimo: int, maximo: int, nullable: bool = False):
        super().__init__(nullable)
        self.minimo, self.maximo = minimo, maximo

    def _validar(self, valor, ruta):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ErrorEsquema(f"{ruta}: debe ser un número entero")
        if not self.minimo <= valor <= self.maximo:
            raise ErrorEsquema(f"{ruta}: fuera del rango {self.minimo} a {self.maximo}")
        return valor


class Opcion(_Tipo):
    def __init__(self, valores, nullable: bool = False):
        super().__init__(nullable)
        self.valores = tuple(valores)

    def _validar(self, valor, ruta):
        if isinstance(valor, bool) or valor not in self.valores:
            raise ErrorEsquema(f"{ruta}: valor no permitido")
        return valor


class Booleano(_Tipo):
    def _validar(self, valor, ruta):
        if not isinstance(valor, bool):
            raise ErrorEsquema(f"{ruta}: debe ser verdadero o falso")
        return valor


class Lista(_Tipo):
    def __init__(self, item: _Tipo, max_items: int = 20, nullable: bool = False):
        super().__init__(nullable)
        self.item, self.max_items = item, max_items

    def _validar(self, valor, ruta):
        if not isinstance(valor, list):
            raise ErrorEsquema(f"{ruta}: debe ser una lista")
        if len(valor) > self.max_items:
            raise ErrorEsquema(f"{ruta}: más de {self.max_items} elementos")
        return [self.item.validar(elemento, f"{ruta}[{i}]") for i, elemento in enumerate(valor)]


class Objeto(_Tipo):
    """Cada campo declarado debe validar; si falta y su tipo admite null, queda en None. Los demas se descartan."""

    def __init__(self, campos: dict, nullable: bool = False):
        super().__init__(nullable)
        self.campos = campos

    def _validar(self, valor, ruta):
        if not isinstance(valor, dict):
            raise ErrorEsquema(f"{ruta}: debe ser un objeto")
        return {
            nombre: tipo.validar(valor.get(nombre), _ruta(ruta if ruta != "valor" else "", nombre))
            for nombre, tipo in self.campos.items()
        }
