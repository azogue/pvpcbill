# -*- coding: utf-8 -*-
"""
Electrical billing for small consumers in Spain using PVPC. Helper methods.

* load_csv_consumo_cups := to read standard energy hourly consumption CSV files
* get_pvpc_data := async method to retrieve PVPC data for a given consumption series
* create_bill := async method to generate the electric bill from the CSV file path

Both `create_bill` and `get_pvpc_data` accept an optional `path_csv_pvpc_store`
to maintain a local CSV with the downloaded PVPC data, to use it as cache.
"""
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from aiopvpc import PVPCData, REFERENCE_TZ

from pvpcbill.handler import FacturaElec


def _load_stored_csv(path: Union[Path, str]) -> Union[pd.DataFrame, pd.Series]:
    """
    Load CSV data previously stored on disk.

    * Assume localized DateTimeIndex in col 0.
    """
    data = pd.read_csv(path, index_col=0, parse_dates=[0]).round(12)
    data.index = data.index.tz_convert(REFERENCE_TZ)
    return data


def load_csv_consumo_cups(path: Union[Path, str]) -> pd.Series:
    """
    Parser del archivo csv de consumos horarios en kWh.

    Los CSV tienen la forma:

    ```csv
    CUPS;Fecha;Hora;Consumo_kWh;Metodo_obtencion
    ES00XX000012345678SN;19/07/2019;1;0,300;R
    ES00XX000012345678SN;19/07/2019;2;0,325;R
    # ...
    ```

    Devuelve un pd.Series con un DateTimeIndex localizado y los valores en kWh,
    usando el CUPS para el nombre de la serie.

    * Comprueba que el CUPS es único
    * Comprueba que todas las medidas son reales (método obtención "R")
    """
    parse_params = {"sep": ";", "decimal": b",", "parse_dates": [1], "dayfirst": True}
    df_consumo = pd.read_csv(path, **parse_params)

    # check 1 CUPS, all real measures
    assert df_consumo.CUPS.value_counts().shape[0] == 1
    assert df_consumo.Metodo_obtencion.value_counts().shape[0] == 1
    assert df_consumo.Metodo_obtencion[0] == "R"
    cups_id = df_consumo.CUPS[0]

    # reduce to pd.Series with localized datetime index
    ts_index = df_consumo.Fecha + df_consumo.Hora.apply(
        lambda x: pd.Timedelta(hours=x - 1)
    )
    # TODO check other dst change! ts_index.is_unique?
    return pd.Series(
        df_consumo.Consumo_kWh.values,
        index=ts_index.dt.tz_localize(REFERENCE_TZ),
        name=cups_id,
    )


# TODO check optional pvpc store
async def get_pvpc_data(
    consumo: pd.Series, path_csv_pvpc_store: Optional[Union[Path, str]] = None
) -> pd.DataFrame:
    """
    Download PVPC data for the given consumption series using `aiopvpc`.

    If a path for a PVPC local csv store is given, it'll try to use pre-loaded data,
     and it'll update the local file with new data.
    """
    df_store = pd.DataFrame()
    path_pvpc_csv = None

    if path_csv_pvpc_store is not None:
        # Use PVPC local storage
        path_pvpc_csv = Path(path_csv_pvpc_store)

    # check if already have it
    if path_csv_pvpc_store is not None and path_pvpc_csv.exists():
        df_store = _load_stored_csv(path_pvpc_csv)
        df = df_store.loc[consumo.index[0] : consumo.index[-1]]
        if not df.empty and df.shape[0] == consumo.shape[0]:
            print("USING cached data ;-)")
            return df

    # proceed to download PVPC range
    pvpc_handler = PVPCData()
    data = await pvpc_handler.async_download_prices_for_range(
        consumo.index[0], consumo.index[-1]
    )
    df = pd.DataFrame(data).T.reindex(consumo.index)
    assert df.index.equals(consumo.index)

    if path_csv_pvpc_store is None:
        return df

    if df_store.empty:
        df.round(12).to_csv(path_pvpc_csv)
        return df

    # TODO check drop duplicates!
    df_store = df_store.append(df).drop_duplicates().sort_index()
    df_store.round(12).to_csv(path_pvpc_csv)
    return df


async def create_bill(
    path_csv_consumo: Union[Path, str],
    potencia_contratada: float,
    tipo_peaje="GEN",
    zona_impuestos="IVA",
    path_csv_pvpc_store: Optional[Union[Path, str]] = None,
    **kwargs,
) -> FacturaElec:
    """
    Create a electric bill from a standardized consumption CSV file plus contract data.
    """
    consumo = load_csv_consumo_cups(path_csv_consumo)
    df_pvpc = await get_pvpc_data(consumo, path_csv_pvpc_store)

    return FacturaElec(
        consumo_horario=consumo,
        pvpc_data=df_pvpc,
        tipo_peaje=tipo_peaje,
        potencia_contratada=potencia_contratada,
        zona_impuestos=zona_impuestos,
        cups=consumo.name,
        **kwargs,
    )
