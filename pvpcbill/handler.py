# -*- coding: utf-8 -*-
"""Electrical billing for small consumers in Spain using PVPC. Bill handler."""
import pandas as pd

from pvpcbill.models import FacturaBilledPeriod, FacturaConfig, FacturaData
from pvpcbill.official import (
    DEFAULT_ALQUILER_CONT_ANUAL,
    DEFAULT_BONO_SOCIAL,
    DEFAULT_CUPS,
    DEFAULT_IMPUESTO_ELECTRICO,
    DEFAULT_POTENCIA_CONTRATADA_KW,
    TaxZone,
    TipoPeaje,
)
from pvpcbill.text_bill import bill_text_repr


class FacturaElec:
    """Cálculo de la facturación eléctrica en España para particulares con PVPC."""

    consumo_horario: pd.Series
    pvpc_data: pd.DataFrame
    data: FacturaData

    def __init__(
        self,
        consumo_horario: pd.Series,
        pvpc_data: pd.DataFrame,
        tipo_peaje="GEN",
        potencia_contratada=DEFAULT_POTENCIA_CONTRATADA_KW,
        zona_impuestos="IVA",
        alquiler_anual=DEFAULT_ALQUILER_CONT_ANUAL,
        con_bono_social=DEFAULT_BONO_SOCIAL,
        cups=DEFAULT_CUPS,
        impuesto_electrico=DEFAULT_IMPUESTO_ELECTRICO,
    ):
        # Datos de Consumo y PVPC
        self.pvpc_data = pvpc_data
        self.consumo_horario = consumo_horario

        # Datos de facturación
        initial_config = FacturaConfig(
            tipo_peaje=TipoPeaje(tipo_peaje),
            potencia_contratada=potencia_contratada,
            con_bono_social=con_bono_social,
            zona_impuestos=TaxZone(zona_impuestos),
            alquiler_anual=alquiler_anual,
            cups=cups,
            impuesto_electrico=impuesto_electrico,
        )

        # PROCESADO DE FACTURA
        self._evaluate_bill(initial_config)

    def _evaluate_bill(self, config: FacturaConfig) -> FacturaData:
        """Método para re-generar el cálculo de la factura eléctrica."""
        # Datos de entrada e intervalo
        t0 = self.consumo_horario.index[0]  # .tz_localize(None) - pd.Timedelta("1D")
        tf = self.consumo_horario.index[-1]
        n_days = (tf - t0.replace(hour=0)).days + 1

        # Extrae TCU para tarifa seleccionada de PVPC data
        code = config.tipo_peaje.value
        s_tcu = self.pvpc_data.eval(f"({code} - TEU{code}) / 1000.0")

        # Cálculo de intervalos de facturación:
        periodos_fact = [
            FacturaBilledPeriod.from_hourly_data(
                consumo=self.consumo_horario[self.consumo_horario.index.year == year],
                pvpc_tcu=s_tcu[self.consumo_horario.index.year == year],
                potencia_contratada=config.potencia_contratada,
                tipo_peaje=config.tipo_peaje,
            )
            for year in self.consumo_horario.index.year.astype("category").categories
        ]

        # Init datos de cálculo
        self.data = FacturaData(
            config=config,
            num_dias_factura=n_days,
            start=t0.to_pydatetime(),
            end=tf.to_pydatetime(),
            periodos_fact=periodos_fact,
        )
        return self.data

    ##############################################
    #       Representación                       #
    ##############################################
    def __repr__(self):
        """Representación en texto de la factura eléctrica."""
        return bill_text_repr(self.data)

    def to_dict(self):
        """Representación como `dict` de los componentes de la factura eléctrica."""
        return self.data.to_dict()
