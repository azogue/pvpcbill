"""Tests for pvpcbill."""
import pandas as pd
import pytest

from pvpcbill import create_bill, get_pvpc_data, load_csv_consumo_cups
from .conftest import load_json_fixture, TEST_PVPC_STORE, TEST_SAMPLE_1


@pytest.mark.skip(reason="Real esios API calls here!, disable to test locally")
async def test_bill_with_local_pvpc_store():
    """Test the local PVPC CSV storage (MAKES REAL API CALLS)."""
    s_consumo: pd.Series = load_csv_consumo_cups(TEST_SAMPLE_1)

    # make another series 2 months before
    s_consumo_other = s_consumo.copy().reindex(s_consumo.index - pd.Timedelta(days=60))

    df_pvpc_1 = await get_pvpc_data(s_consumo, TEST_PVPC_STORE)
    assert df_pvpc_1.index.equals(s_consumo.index)

    # Real Download here!
    df_pvpc_2 = await get_pvpc_data(s_consumo_other, TEST_PVPC_STORE)
    assert df_pvpc_2.index.equals(s_consumo_other.index)


@pytest.mark.skip(reason="Real esios API calls here!, disable to test locally")
async def test_bill_without_local_pvpc_store():
    """Generate a bill with just the consumption data (MAKES REAL API CALLS)."""
    bill = await create_bill(
        path_csv_consumo=TEST_SAMPLE_1,
        potencia_contratada=4.6,
        tipo_peaje="NOC",
        # Real Download here!
        # path_csv_pvpc_store=None,
    )

    # Check results
    ref_results = load_json_fixture(f"{bill.data.identifier}.json")
    assert bill.to_dict() == ref_results
    #
