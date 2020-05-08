# -*- coding: utf-8 -*-
"""Electrical billing for small consumers in Spain using PVPC. Text representation."""
from pvpcbill.models import FacturaData
from pvpcbill.official import round_money

# Plantillas para representación en texto de la factura eléctrica
TEMPLATE_FACTURA = """FACTURA ELÉCTRICA:
--------------------------------------------------------------------------------
* CUPS             	        {cups}
* Fecha inicio             	{ts_ini:%d/%m/%Y}
* Fecha final              	{ts_fin:%d/%m/%Y}
* Peaje de acceso          	{cod_peaje} ({desc_peaje})
* Potencia contratada      	{p_contrato:.2f} kW
* Consumo periodo          	{consumo_total:.2f} kWh
* ¿Bono Social?            	{con_bono}
* Equipo de medida         	{coste_medida:.2f} €
* Impuestos                	{desc_impuesto}
* Días facturables         	{dias_fact}
--------------------------------------------------------------------------------

- CÁLCULO DEL TÉRMINO FIJO POR POTENCIA CONTRATADA:
  {detalle_term_fijo}
{total_termino_fijo}

- CÁLCULO DEL TÉRMINO VARIABLE POR ENERGÍA CONSUMIDA (TARIFA {cod_peaje}):
  {detalle_term_variable}
{total_termino_variable}{detalle_descuento}- IMPUESTO ELÉCTRICO:
{detalle_term_impuesto_elec}
{detalle_subtotal}

- EQUIPO DE MEDIDA:
{detalle_term_medida}
{importe_total}

- IVA O EQUIVALENTE:
{detalle_iva}

################################################################################
{total_factura}
################################################################################
Consumo medio diario en el periodo facturado: {coste_diario:.2f} €/día
"""

MASK_T_FIJO = (
    "   {pot:.2f} kW x {coef_t_fijo} €/kW/día x {dias} días ({dias_y}/{y})"
    " = {coste:.2f} €"
)
MASK_T_FIJO_PEAJE = "Peaje acceso potencia:\n" + MASK_T_FIJO
MASK_T_FIJO_COMER = "Comercialización:\n" + MASK_T_FIJO
MASK_T_VAR_PERIOD_TRAMO = (
    " *Tramo {tramo}, " "de {ts_ini:%d/%m/%Y} a {ts_fin:%d/%m/%Y}:"
)
MASK_T_IMP_ELEC = """    {0}% x ({1:.2f}€ + {2:.2f}€ = {3:.2f}€)"""
MASK_T_MEDIDA = """    {0} días x {1:.6f} €/día"""
MASK_T_IVA_M = """    {0:.0f}% de {1:.2f}€ + {2:.0f}% de {3:.2f}€"""
MASK_T_IVA_U = """    {0:.0f}% de {1:.2f}€"""
MASK_T_VAR_PERIOD = "  Periodo {ind_periodo}: {valor_medio_periodo:.6f} €/kWh"
MASK_T_VAR_PERIOD += (
    "                             ---> {coste_periodo:.2f}€(P{ind_periodo})\n"
)
MASK_T_VAR_PERIOD += (
    "    - Peaje de acceso:     {consumo_periodo:.0f} kWh * "
    "{valor_med_tea:.6f} €/kWh = {coste_tea:.2f}€\n"
)
MASK_T_VAR_PERIOD += (
    "    - Coste de la energía: {consumo_periodo:.0f} kWh * "
    "{valor_med_tcu:.6f} €/kWh = {coste_tcu:.2f}€"
)


def bill_text_repr(bill_data: FacturaData) -> str:
    """Representación en texto de la factura eléctrica."""

    def _linetotal(str_line, total_value):
        return f"{str_line:70} {total_value:.2f} €"

    def _line_section_total(title, total_value):
        return _linetotal(f"  ==> {title}", total_value)

    detalle_tfijo = ""
    for billed_period in bill_data.periodos_fact:
        detalle_tfijo += "\n  ".join(
            [
                MASK_T_FIJO_PEAJE.format(
                    pot=bill_data.config.potencia_contratada,
                    dias=billed_period.billed_days,
                    y=billed_period.year,
                    dias_y=billed_period.total_year_days,
                    coste=billed_period.termino_fijo_peaje_acceso,
                    coef_t_fijo=billed_period.coef_peaje_acceso_potencia,
                ),
                MASK_T_FIJO_COMER.format(
                    pot=bill_data.config.potencia_contratada,
                    dias=billed_period.billed_days,
                    y=billed_period.year,
                    dias_y=billed_period.total_year_days,
                    coste=billed_period.termino_fijo_comercializacion,
                    coef_t_fijo=billed_period.coef_comercializacion,
                ),
            ]
        )

    detalle_tvar = []
    if bill_data.consumo_total > 0.0:
        for i, ener_p in enumerate(bill_data.iter_energy_periods()):
            tcu = ener_p.coste_energia_tcu
            tea = ener_p.coste_peaje_acceso_tea
            cons = ener_p.energia_total
            detalle_tvar.append(
                MASK_T_VAR_PERIOD.format(
                    ind_periodo=i + 1,
                    consumo_periodo=int(round(cons)),
                    valor_medio_periodo=(tcu + tea) / cons,
                    coste_periodo=tcu + tea,
                    valor_med_tcu=tcu / cons,
                    coste_tcu=tcu,
                    valor_med_tea=tea / cons,
                    coste_tea=tea,
                )
            )

    detalle_impelec = _linetotal(
        MASK_T_IMP_ELEC.format(
            bill_data.config.impuesto_electrico * 100.0,
            bill_data.termino_fijo_total,
            bill_data.termino_variable_total,
            bill_data.termino_fijo_total + bill_data.termino_variable_total,
        ),
        bill_data.termino_impuesto_electrico,
    )
    detalle_medida = _linetotal(
        MASK_T_MEDIDA.format(
            bill_data.num_dias_factura,
            bill_data.termino_equipo_medida / bill_data.num_dias_factura,
        ),
        bill_data.termino_equipo_medida,
    )
    detalle_subtotal = _line_section_total(
        "Subtotal",
        bill_data.termino_fijo_total
        + bill_data.termino_variable_total
        + bill_data.termino_impuesto_electrico,
    )

    subt_fijo_var = bill_data.termino_fijo_total + bill_data.termino_variable_total
    subt_fijo_var += (
        bill_data.termino_impuesto_electrico + bill_data.descuento_bono_social
    )

    if (
        bill_data.config.zona_impuestos.tax_rate
        != bill_data.config.zona_impuestos.measurement_tax_rate
    ):
        detalle_iva = MASK_T_IVA_M.format(
            bill_data.config.zona_impuestos.tax_rate * 100,
            subt_fijo_var,
            bill_data.config.zona_impuestos.measurement_tax_rate * 100,
            bill_data.termino_equipo_medida,
        )
    else:
        detalle_iva = MASK_T_IVA_U.format(
            bill_data.config.zona_impuestos.tax_rate * 100,
            subt_fijo_var + bill_data.termino_equipo_medida,
        )

    detalle_descuento = ""
    if bill_data.config.con_bono_social:
        detalle_descuento = (
            "\n"
            + _linetotal(
                "- DESCUENTO POR BONO SOCIAL:", bill_data.descuento_bono_social,
            )
            + "\n"
        )

    # Fill string template
    params = {
        "cups": bill_data.config.cups,
        "ts_ini": bill_data.start,
        "ts_fin": bill_data.end,
        "cod_peaje": bill_data.config.tipo_peaje.code,
        "consumo_total": bill_data.consumo_total,
        "desc_peaje": bill_data.config.tipo_peaje.pretty_name,
        "p_contrato": round_money(bill_data.config.potencia_contratada),
        "con_bono": "Sí" if bill_data.config.con_bono_social else "No",
        "desc_impuesto": bill_data.config.zona_impuestos.pretty_name,
        "dias_fact": bill_data.num_dias_factura,
        "detalle_descuento": f"\n{detalle_descuento}\n",
        "coste_impuesto_elec": bill_data.termino_impuesto_electrico,
        "total_termino_fijo": _line_section_total(
            "Término fijo", bill_data.termino_fijo_total
        ),
        "total_termino_variable": _line_section_total(
            "Término de consumo", bill_data.termino_variable_total
        ),
        "coste_medida": bill_data.termino_equipo_medida,
        "total_factura": _linetotal("# TOTAL FACTURA", bill_data.total),
        "detalle_term_fijo": detalle_tfijo,
        "importe_total": _line_section_total(
            "Importe total", subt_fijo_var + bill_data.termino_equipo_medida
        ),
        "detalle_iva": _linetotal(detalle_iva, bill_data.termino_iva_total),
        "detalle_term_variable": "\n  ".join(detalle_tvar),
        "detalle_term_impuesto_elec": detalle_impelec,
        "detalle_term_medida": detalle_medida,
        "detalle_subtotal": detalle_subtotal,
        "coste_diario": bill_data.total / bill_data.num_dias_factura,
    }

    return TEMPLATE_FACTURA.format(**params)
