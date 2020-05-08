# -*- coding: utf-8 -*-
"""
Electrical billing for small consumers in Spain using PVPC. Official data.

Facturación de datos de consumo eléctrico para particulares según PVPC.

* Documentos de origen con los valores de los peajes de acceso
  a baja tensión (≤1kV) y baja potencia (≤10kW):
  - [Tarifas 2015 (IDAE)](http://www.idae.es/uploads/documentos/documentos_Tarifas_Reguladas_ene_2015_9195098b.pdf)
  - [Tarifas 2016 (IDAE)](http://www.idae.es/uploads/documentos/documentos_Tarifas_Reguladas_ene_2016_a197c904.pdf)

* Periodo de facturación:
  A partir de 31/03/2014.
  El día de lectura inicial está excluido
  y el día de lectura final está incluido.

* Discriminación horaria:

  - '2.0DHA': Potencia máxima 10 kW, con dos periodos:
    P1 (Punta) Invierno: 12-22h / Verano: 13-23h
    P2 (Valle) Invierno: 22-12h / Verano: 23-13h.

  - '2.0DHS': Tarifa vehículo eléctrico. Potencia máxima 10 kW, con
    P1 (Punta) 13-23h | P2 (Valle) 23-01h / 07-13h | P3 (Supervalle) 01-07h.

  - El horario Valle de 14 horas abarca
    de 22 a 12 h en invierno y de 23 a 13 h en verano.
  - El horario Punta de 10 horas abarca
    de 12 a 22 h en invierno y de 13 a 23 h en verano.
"""  # noqa
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Tuple

import pandas as pd
import pytz
from aiopvpc import ESIOS_TARIFFS

# Defaults y definiciones
DEFAULT_CUPS = "ES00XXXXXXXXXXXXXXSN"
DEFAULT_POTENCIA_CONTRATADA_KW = 3.45
DEFAULT_BONO_SOCIAL = False

ROUND_PREC = 2  # 0,01 €
DEFAULT_IMPUESTO_ELECTRICO = 0.0511269632  # 4,864% por 1,05113
DEFAULT_ALQUILER_CONT_ANUAL = 0.81 * 12  # € / año para monofásico

KEY_TARIFF_GEN = ESIOS_TARIFFS[0]
KEY_TARIFF_NOC = ESIOS_TARIFFS[1]
KEY_TARIFF_VHC = ESIOS_TARIFFS[2]


class TipoPeaje(Enum):
    """Tariff enumerator"""

    GEN = KEY_TARIFF_GEN
    NOC = KEY_TARIFF_NOC
    VHC = KEY_TARIFF_VHC

    @property
    def num_periods(self) -> int:
        if self == self.GEN:
            return 1
        elif self == self.NOC:
            return 2
        return 3

    @property
    def pretty_name(self) -> str:
        if self == self.GEN:
            return "General"
        elif self == self.NOC:
            return "Nocturna"
        return "Vehículo eléctrico"

    @property
    def code(self) -> str:
        if self == self.GEN:
            return "2.0A"
        elif self == self.NOC:
            return "2.0DHA"
        return "2.0DHS"


class TaxZone(Enum):
    """Tax zones enumerator"""

    PENINSULA_BALEARES = "IVA"
    CANARIAS = "IGIC"
    CEUTA_MELILLA = "IPSI"

    @property
    def tax_rate(self) -> float:
        if self == self.PENINSULA_BALEARES:
            return 0.21
        elif self == self.CANARIAS:
            return 0.03
        return 0.01

    @property
    def measurement_tax_rate(self) -> float:
        if self == self.PENINSULA_BALEARES:
            return 0.21
        elif self == self.CANARIAS:
            return 0.07
        return 0.04

    @property
    def pretty_name(self) -> str:
        if self == self.PENINSULA_BALEARES:
            return f"Península y Baleares ({self.value})"
        elif self == self.CANARIAS:
            return f"Canarias ({self.value})"
        return f"Ceuta y Melilla ({self.value})"


# TODO cambiar distinción tarifaria de 'año' a periodo reglamentario
MARGEN_COMERC_EUR_KW_YEAR_MCF = {
    2014: 4.0,  # € /(kW·año)
    2015: 4.0,  # € /(kW·año)
    2016: 4.0,  # € /(kW·año)
    2017: 4.0,  # € /(kW·año)
    # ...
    # TODO add recent data
    2019: 3.113,  # € /(kW·año)
    2020: 3.113,  # € /(kW·año)
}
TERM_POT_PEAJE_ACC_EUR_KW_YEAR_TPA = {
    2014: 35.648148,
    2015: 38.043426,  # 3,503618833 * 12 - 4
    2016: 38.043426,  # (3,1702855 + 0,33333) * 12
    2017: 37.156426,
    # TODO add recent data
    # 2020: 37.258224, + 6c
    # 2020: 37.054905,  # - 4c
    2019: 38.043426,  # ?
    2020: 38.043426,  # +54c 15.85 vs 14.34 + 1.17 = 15.51
    # 2020: 37.156426, # ~ 1 cent (15.52),
    # TODO review period split + round kWh -> 0.103944 + 0.008505 €/kW/dia
}
TERM_ENER_PEAJE_ACC_EUR_KWH_TEA = {
    2014: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.074568, 0.017809, 0.006596],
    },
    2015: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.074568, 0.017809, 0.006596],
    },
    2016: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.062012, 0.002879, 0.000886],
    },
    2017: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.062012, 0.002879, 0.000886],
    },
    # TODO add/review recent data
    2019: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.062012, 0.002879, 0.000886],
    },
    2020: {
        KEY_TARIFF_GEN: [0.044027],
        KEY_TARIFF_NOC: [0.062012, 0.002215],
        KEY_TARIFF_VHC: [0.062012, 0.002879, 0.000886],
    },
}


##############################################
#       Cálculo                              #
##############################################
def round_money(value: float):
    """Rounding method used in official billing (as it appears)."""
    return float(Decimal(str(value)).quantize(Decimal("1.11"), rounding=ROUND_HALF_UP))


# TODO review sum_money
def round_sum_money(values):
    return sum(round(value, ROUND_PREC) for value in values)


def split_in_tariff_periods(
    series: pd.Series, tipo_peaje: TipoPeaje
) -> Tuple[pd.Series, ...]:
    if tipo_peaje == TipoPeaje.GEN:
        assert tipo_peaje.num_periods == 1
        return (series,)

    # split using constant hours in UTC :)
    idx_utc: pd.DatetimeIndex = series.index.tz_convert(pytz.UTC)
    params_cierre = {"include_start": True, "include_end": False}

    if tipo_peaje == TipoPeaje.NOC:
        idx_p1 = idx_utc.indexer_between_time("11:00", "21:00", **params_cierre)
        idx_p2 = idx_utc.indexer_between_time("21:00", "11:00", **params_cierre)
        assert tipo_peaje.num_periods == 2
        return series[idx_p1], series[idx_p2]

    idx_p1 = idx_utc.indexer_between_time("11:00", "21:00", **params_cierre)
    idx_p2 = idx_utc.indexer_between_time("05:00", "11:00", **params_cierre)
    idx_p3 = idx_utc.indexer_between_time("21:00", "05:00", **params_cierre)
    assert tipo_peaje.num_periods == 3
    return series[idx_p1], series[idx_p2], series[idx_p3]
