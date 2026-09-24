"""Bonificaciones en cascada ("10+5+3").

Funciones puras, sin dependencias de Odoo, para poder reutilizarlas desde otros
módulos (p. ej. el importador de listas de proveedores).
"""
from __future__ import annotations

import re

_NUMBER = r'\d+(?:[.,]\d+)?'
_CASCADE_RE = re.compile(rf'^{_NUMBER}(?:\+{_NUMBER})*$')


def parse_discount_cascade(text: str | bool | None) -> list[float]:
    """Parsea una cascada de bonificaciones.

    Acepta espacios y coma o punto decimal. Vacío → []. Cada valor debe ser
    mayor que 0 y menor que 100. Formato inválido → ValueError.
    """
    if not text or not str(text).strip():
        return []
    compact = re.sub(r'\s+', '', str(text))
    if not _CASCADE_RE.match(compact):
        raise ValueError(
            f'Bonificaciones "{text}" con formato inválido. '
            'Usá números separados por "+", por ejemplo 10+5+3 o 10+2,5.'
        )
    values = [float(part.replace(',', '.')) for part in compact.split('+')]
    for value in values:
        if not 0 < value < 100:
            raise ValueError(
                f'Bonificación {value:g} fuera de rango en "{text}": '
                'cada valor debe ser mayor que 0 y menor que 100.'
            )
    return values


def cascade_equivalent_pct(values: list[float]) -> float:
    """Porcentaje único equivalente a aplicar las bonificaciones en cascada."""
    factor = 1.0
    for value in values:
        factor *= 1 - value / 100
    return (1 - factor) * 100
