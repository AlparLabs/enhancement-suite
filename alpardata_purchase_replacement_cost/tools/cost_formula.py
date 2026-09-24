"""Fórmula del costo de reposición.

    neto       = lista × (1 − equivalente_bonificación)
    reposición = neto × (1 − pronto_pago + flete + percepción + internos)

Todos los adicionales se calculan sobre el neto bonificado y no se componen entre
sí (ver spec 2026-09-24-replacement-cost-design.md).
"""
from __future__ import annotations


def compute_replacement_cost(
    list_price: float,
    discount_equivalent_pct: float,
    early_payment_pct: float,
    freight_pct: float,
    perception_pct: float,
    internal_tax_pct: float,
) -> tuple[float, float]:
    """Devuelve (neto bonificado, costo de reposición)."""
    if not list_price:
        return 0.0, 0.0
    net = list_price * (1 - discount_equivalent_pct / 100)
    factor = 1 + (
        -early_payment_pct + freight_pct + perception_pct + internal_tax_pct
    ) / 100
    return net, net * factor
