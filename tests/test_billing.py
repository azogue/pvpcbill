"""Tests for pvpcbill."""
import pytest

from pvpcbill import create_bill, FacturaData, FacturaElec
from .conftest import load_json_fixture, TEST_EXAMPLES_PATH

_SAMPLE_STORE = "pvpc_test_data.csv"
_SAMPLE_CONS_1 = "consumo_facturado18_02_2020-18_03_2020-R.csv"


@pytest.mark.parametrize(
    "p_consumption_csv, p_pvpc_csv, with_results, power, tariff, tax_zone, discount",
    (
        (_SAMPLE_CONS_1, _SAMPLE_STORE, True, 4.6, "NOC", "IVA", False),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, True, 4.6, "GEN", "IVA", False),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, False, 4.6, "VHC", "IVA", False),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, False, 3.45, "GEN", "IGIC", False),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, False, 3.45, "GEN", "IPSI", False),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, False, 4.6, "NOC", "IVA", True),
        (_SAMPLE_CONS_1, _SAMPLE_STORE, False, 3.45, "NOC", "IGIC", True),
    ),
)
async def test_quick_bill_with_pvpc_store(
    p_consumption_csv, p_pvpc_csv, with_results, power, tariff, tax_zone, discount
):
    p_csv = TEST_EXAMPLES_PATH / p_consumption_csv
    bill = await create_bill(
        path_csv_consumo=p_csv,
        path_csv_pvpc_store=p_pvpc_csv,
        potencia_contratada=power,
        tipo_peaje=tariff,
        zona_impuestos=tax_zone,
        con_bono_social=discount,
    )
    assert isinstance(bill, FacturaElec)

    # Check string representation
    str_bill = str(bill)
    assert (
        next(filter(lambda l: l.startswith("# TOTAL FACTURA"), str_bill.splitlines()))
        .rstrip(" €")
        .endswith(str(bill.data.total))
    )
    # print(bill)

    # Check data (de)serialization
    data = bill.to_dict()
    bill_data_2 = FacturaData.from_json(bill.data.to_json())
    assert bill_data_2.to_dict() == data

    # Check results
    res_json_file = f"{bill.data.identifier}.json"
    if with_results:
        ref_results = load_json_fixture(res_json_file)
        assert data == ref_results
    # else:
    #     json_data = bill.data.to_json()
    #     (TEST_EXAMPLES_PATH / res_json_file).write_text(json_data)
    #     print(json_data)
