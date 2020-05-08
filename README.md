[![PyPi](https://pypip.in/v/pvpcbill/badge.svg)](https://pypi.org/project/pvpcbill/)
[![Wheel](https://pypip.in/wheel/pvpcbill/badge.svg)](https://pypi.org/project/pvpcbill/)
[![Travis Status](https://travis-ci.org/azogue/pvpcbill.svg?branch=master)](https://travis-ci.org/azogue/pvpcbill)
[![codecov](https://codecov.io/gh/azogue/pvpcbill/branch/master/graph/badge.svg)](https://codecov.io/gh/azogue/pvpcbill)

# pvpcbill

**Electrical billing simulation for small consumers in Spain using PVPC** (electricity hourly prices).

It uses **[`aiopvpc`](https://github.com/azogue/aiopvpc)** to download PVPC data, and _the usual suspects_ ([`pandas`](https://pandas.pydata.org) & [`matplotlib`](https://matplotlib.org)) to deal with time-series data and plotting.

<span class="badge-buymeacoffee"><a href="https://www.buymeacoffee.com/azogue" title="Donate to this project using Buy Me A Coffee"><img src="https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg" alt="Buy Me A Coffee donate button" /></a></span>

## Install

Install from pypi with **`pip install pvpcbill`**, or clone it to run tests or anything else ;-)

## Usage

From a _jupyter notebook_, just call the `create_bill` async helper to instantiate a new 'bill' object:

```python
from pvpcbill import create_bill

# Creación directa de factura
factura = await create_bill(
    path_csv_consumo="/path/to/elec_data/consumo_facturado18_02_2020-18_03_2020-R.csv",
    potencia_contratada=4.6,  # kW
    tipo_peaje="NOC",         # GEN / NOC / VHC
    zona_impuestos="IVA",     # IVA / IGIC / IPSI
)

print(factura)
```

** If using it from a non-async script,
use `asyncio.run(create_bill(**params))` to run the async method.

_Output:_

```text
FACTURA ELÉCTRICA:
--------------------------------------------------------------------------------
* CUPS             	        ES0012345678901234SN
* Fecha inicio             	17/02/2020
* Fecha final              	18/03/2020
* Peaje de acceso          	2.0DHA (Nocturna)
* Potencia contratada      	4.60 kW
* Consumo periodo          	472.93 kWh
* ¿Bono Social?            	No
* Equipo de medida         	0.80 €
* Impuestos                	Península y Baleares (IVA)
* Días facturables         	30
--------------------------------------------------------------------------------

- CÁLCULO DEL TÉRMINO FIJO POR POTENCIA CONTRATADA:
  Peaje acceso potencia:
   4.60 kW x 0.103944 €/kW/día x 30 días (366/2020) = 14.34 €
  Comercialización:
   4.60 kW x 0.008505 €/kW/día x 30 días (366/2020) = 1.17 €
  ==> Término fijo                                                     15.51 €

- CÁLCULO DEL TÉRMINO VARIABLE POR ENERGÍA CONSUMIDA (TARIFA 2.0DHA):
    Periodo 1: 0.111867 €/kWh                             ---> 19.02€(P1)
    - Peaje de acceso:     170 kWh * 0.062012 €/kWh = 10.54€
    - Coste de la energía: 170 kWh * 0.049855 €/kWh = 8.48€
    Periodo 2: 0.045617 €/kWh                             ---> 13.82€(P2)
    - Peaje de acceso:     303 kWh * 0.002215 €/kWh = 0.67€
    - Coste de la energía: 303 kWh * 0.043402 €/kWh = 13.15€
  ==> Término de consumo                                               32.84 €

- IMPUESTO ELÉCTRICO:
    5.11269632% x (15.51€ + 32.84€ = 48.35€)                           2.47 €
  ==> Subtotal                                                         50.82 €

- EQUIPO DE MEDIDA:
    30 días x 0.026667 €/día                                           0.80 €
  ==> Importe total                                                    51.62 €

- IVA O EQUIVALENTE:
    21% de 51.62€                                                      10.84 €

################################################################################
# TOTAL FACTURA                                                        62.46 €
################################################################################
Consumo medio diario en el periodo facturado: 2.08 €/día
```

But there is much more:

```python
# Reparto de costes en la factura
p_imp = (
    + factura.data.termino_impuesto_electrico
    + factura.data.termino_equipo_medida
    + factura.data.termino_iva_total
) / factura.data.total
p_ener = factura.data.termino_variable_total / factura.data.total
p_pot = factura.data.termino_fijo_total / factura.data.total

print(
    f"El coste de la factura se reparte en:\n  "
    f"* un {100*p_ener:.1f} % por energía consumida,\n  "
    f"* un {100*p_pot:.1f} % por potencia contratada,\n  "
    f"* un {100*p_imp:.1f} % por impuestos aplicados\n\n"
)

print(factura.data.to_json())
```

_Output:_

```text
El coste de la factura se reparte en:
  * un 52.6 % por energía consumida,
  * un 24.8 % por potencia contratada,
  * un 22.6 % por impuestos aplicados
```

```json
{
  "config": {
    "tipo_peaje": "NOC",
    "potencia_contratada": 4.6,
    "con_bono_social": false,
    "zona_impuestos": "IVA",
    "alquiler_anual": 9.72,
    "impuesto_electrico": 0.0511269632,
    "cups": "ES0012345678901234SN"
  },
  "num_dias_factura": 30,
  "start": "2020-02-17 00:00:00",
  "end": "2020-03-18 00:00:00",
  "periodos_fact": [
    {
      "billed_days": 30,
      "year": 2020,
      "termino_fijo_peaje_acceso": 14.34,
      "termino_fijo_comercializacion": 1.17,
      "termino_fijo_total": 15.51,
      "energy_periods": [
        {
          "name": "P1",
          "coste_peaje_acceso_tea": 10.544458468,
          "coste_energia_tcu": 8.477372039999999,
          "energia_total": 170.03900000000002
        },
        {
          "name": "P2",
          "coste_peaje_acceso_tea": 0.67090578,
          "coste_energia_tcu": 13.146024950000003,
          "energia_total": 302.892
        }
      ]
    }
  ],
  "descuento_bono_social": 0.0,
  "termino_impuesto_electrico": 2.47,
  "termino_equipo_medida": 0.8,
  "termino_iva_gen": 10.6722,
  "termino_iva_medida": 0.168,
  "termino_iva_total": 10.84,
  "total": 62.46
}
```

### Examples

- [Quick example to simulate a bill (jupyter notebook)](Notebooks/Ejemplo%20rápido.ipynb)
- [Detailed example to simulate a bill (jupyter notebook)](Notebooks/Ejemplo%20simulación%20de%20facturación%20eléctrica%20con%20PVPC.ipynb)
