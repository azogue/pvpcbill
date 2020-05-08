# -*- coding: utf-8 -*-
"""Electrical billing for small consumers in Spain using PVPC. Bill dataclasses."""
from datetime import datetime
from typing import Iterator, List

import attr
import pandas as pd

from pvpcbill.base import Base
from pvpcbill.official import (
    MARGEN_COMERC_EUR_KW_YEAR_MCF,
    round_money,
    round_sum_money,
    split_in_tariff_periods,
    TaxZone,
    TERM_ENER_PEAJE_ACC_EUR_KWH_TEA,
    TERM_POT_PEAJE_ACC_EUR_KW_YEAR_TPA,
    TipoPeaje,
)

DEFAULT_CUPS = "ES00XXXXXXXXXXXXXXDB"
DEFAULT_POTENCIA_CONTRATADA_KW = 3.45
DEFAULT_BONO_SOCIAL = False
DEFAULT_IMPUESTO_ELECTRICO = 0.0511269632  # 4,864% por 1,05113
DEFAULT_ALQUILER_CONT_ANUAL = 0.81 * 12  # € / año para monofásico


@attr.s(auto_attribs=True)
class FacturaConfig(Base):
    """Dataclass to store information related to the electric contract."""

    tipo_peaje: TipoPeaje = attr.ib(default=TipoPeaje.GEN)
    potencia_contratada: float = attr.ib(default=DEFAULT_POTENCIA_CONTRATADA_KW)
    con_bono_social: bool = attr.ib(default=DEFAULT_BONO_SOCIAL)
    zona_impuestos: TaxZone = attr.ib(default=TaxZone.PENINSULA_BALEARES)
    alquiler_anual: float = attr.ib(default=DEFAULT_ALQUILER_CONT_ANUAL)
    impuesto_electrico: float = attr.ib(default=DEFAULT_IMPUESTO_ELECTRICO)
    cups: str = attr.ib(default=DEFAULT_CUPS)


@attr.s(auto_attribs=True)
class EnergykWhTariffPeriod(Base):
    """Dataclass to store info related to the energy in 1 tariff period."""

    name: str = attr.ib()
    coste_peaje_acceso_tea: float = attr.ib(default=0.0)
    coste_energia_tcu: float = attr.ib(default=0.0)
    energia_total: float = attr.ib(default=0.0)


@attr.s(auto_attribs=True)
class FacturaBilledPeriod(Base):
    """Dataclass to store info related to 1 billed period inside a bill."""

    billed_days: int = attr.ib()  # nº de días del periodo facturado
    # TODO cambiar distinción tarifaria de 'año' a periodo reglamentario
    year: int = attr.ib()

    # filled when process hourly consumption
    termino_fijo_peaje_acceso: float = attr.ib(default=0.0)
    termino_fijo_comercializacion: float = attr.ib(default=0.0)
    termino_fijo_total: float = attr.ib(default=0.0)
    energy_periods: List[EnergykWhTariffPeriod] = attr.ib(factory=list)

    @classmethod
    def from_hourly_data(
        cls,
        consumo: pd.Series,
        pvpc_tcu: pd.Series,
        tipo_peaje: TipoPeaje,
        potencia_contratada: float,
    ):
        """
        TODO redo doc
        """
        year = consumo.index[0].year
        billed_days = (consumo.index[-1] - consumo.index[0]).days + 1
        energy_periods = [
            EnergykWhTariffPeriod(
                name=f"P{i+1}",
                coste_peaje_acceso_tea=round_money(cons_period.sum() * coef_tea),
                coste_energia_tcu=round_money(
                    (cons_period * pvpc_tcu.loc[cons_period.index]).sum()
                ),
                energia_total=round_money(cons_period.sum()),
            )
            for i, (coef_tea, cons_period) in enumerate(
                zip(
                    TERM_ENER_PEAJE_ACC_EUR_KWH_TEA[year][tipo_peaje.value],
                    split_in_tariff_periods(consumo, tipo_peaje),
                )
            )
        ]

        billed_period = cls(
            billed_days=billed_days, year=year, energy_periods=energy_periods,
        )

        # Término fijo por peaje de acceso
        billed_period.termino_fijo_peaje_acceso = round_money(
            potencia_contratada * billed_days * billed_period.coef_peaje_acceso_potencia
        )
        # Término fijo por comercialización
        billed_period.termino_fijo_comercializacion = round_money(
            potencia_contratada * billed_days * billed_period.coef_comercializacion
        )
        billed_period.termino_fijo_total = round_money(
            billed_period.termino_fijo_peaje_acceso
            + billed_period.termino_fijo_comercializacion
        )

        return billed_period

    @property
    def total_year_days(self):
        """Total number of days in the billed period's year."""
        return (datetime(self.year + 1, 1, 1) - datetime(self.year, 1, 1)).days

    @property
    def coef_peaje_acceso_potencia(self) -> float:
        coef_y = TERM_POT_PEAJE_ACC_EUR_KW_YEAR_TPA[self.year]
        return round(coef_y / self.total_year_days, 6)

    @property
    def coef_comercializacion(self) -> float:
        coef_y = MARGEN_COMERC_EUR_KW_YEAR_MCF[self.year]
        return round(coef_y / self.total_year_days, 6)


@attr.s(auto_attribs=True)
class FacturaData(Base):
    """Dataclass to store information related to the billed period."""

    config: FacturaConfig = attr.ib()
    num_dias_factura: int = attr.ib()
    start: datetime = attr.ib()
    end: datetime = attr.ib()
    periodos_fact: List[FacturaBilledPeriod] = attr.ib(factory=list)

    descuento_bono_social: float = attr.ib(default=0.0)
    termino_impuesto_electrico: float = attr.ib(default=0.0)
    termino_equipo_medida: float = attr.ib(default=0.0)
    termino_iva_gen: float = attr.ib(default=0.0)
    termino_iva_medida: float = attr.ib(default=0.0)
    termino_iva_total: float = attr.ib(default=0.0)
    total: float = attr.ib(default=0.0)

    def __attrs_post_init__(self):
        """Fill calculated terms of the bill when instantiating."""
        self._calc_taxes_and_total()

    def _calc_taxes_and_total(self):
        """
        Añade los términos finales a la factura eléctrica.

        - Aplica el bono social
        - Calcula el impuesto eléctrico
        - Calcula el coste del alquiler del equipo de medida
        - Añade el IVA y obtiene el total
        """
        subt_fijo_var = self.termino_fijo_total + self.termino_variable_total

        # Cálculo de la bonificación (bono social):
        if self.config.con_bono_social:
            self.descuento_bono_social = round_money(-0.25 * round_money(subt_fijo_var))
            subt_fijo_var += self.descuento_bono_social

        # Cálculo del impuesto eléctrico:
        self.termino_impuesto_electrico = round_money(
            self.config.impuesto_electrico * subt_fijo_var
        )
        subt_fijo_var += self.termino_impuesto_electrico

        # Cálculo del alquiler del equipo de medida:
        frac_year = sum(p.billed_days / p.total_year_days for p in self.periodos_fact)
        self.termino_equipo_medida = round_money(frac_year * self.config.alquiler_anual)

        # Cálculo del IVA y TOTAL:
        self.termino_iva_gen = round_money(
            subt_fijo_var * self.config.zona_impuestos.tax_rate
        )
        self.termino_iva_medida = round_money(
            self.termino_equipo_medida * self.config.zona_impuestos.measurement_tax_rate
        )
        self.termino_iva_total = round_money(
            self.termino_iva_gen + self.termino_iva_medida
        )

        # TOTAL FACTURA:
        subt_fijo_var += self.termino_equipo_medida + self.termino_iva_total
        self.total = round_money(subt_fijo_var)

    def iter_energy_periods(self) -> Iterator[EnergykWhTariffPeriod]:
        """Itera sobre cada periodo tarifario de cada periodo de facturación."""
        for billed_period in self.periodos_fact:
            for ener_period in billed_period.energy_periods:
                yield ener_period

    @property
    def coste_total_peaje_acceso_tea(self) -> float:
        return round_sum_money(
            ener_p.coste_peaje_acceso_tea for ener_p in self.iter_energy_periods()
        )

    @property
    def coste_total_energia_tcu(self) -> float:
        return round_sum_money(
            ener_p.coste_energia_tcu for ener_p in self.iter_energy_periods()
        )

    @property
    def consumo_total(self) -> float:
        """Calcula la energía total facturada, sumando cada periodo de facturación."""
        return sum(ener_p.energia_total for ener_p in self.iter_energy_periods())

    @property
    def termino_variable_total(self) -> float:
        """Calcula el coste por energía total, sumando cada periodo de facturación."""
        return round_money(
            self.coste_total_peaje_acceso_tea + self.coste_total_energia_tcu
        )

    @property
    def termino_fijo_total(self) -> float:
        """Calcula el coste por potencia total, sumando cada periodo de facturación."""
        return round_sum_money(
            billed_period.termino_fijo_total for billed_period in self.periodos_fact
        )

    @property
    def identifier(self) -> str:
        """Text identifier to be used as filename for exported data."""
        str_ident = f"elecbill_data_{self.start:%Y_%m_%d}_to_{self.end:%Y_%m_%d}_"
        str_ident += f"{self.config.tipo_peaje.value}_"
        str_ident += f"{self.config.potencia_contratada:g}_".replace(".", "_")
        str_ident += f"{self.config.zona_impuestos.value}"
        if self.config.con_bono_social:
            str_ident += f"_discount"
        return str_ident
