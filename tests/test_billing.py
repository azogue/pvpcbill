"""Tests for pvpcbill."""
import pytest

from pvpcbill import create_bill, FacturaData, FacturaElec
from .conftest import load_json_fixture, TEST_PVPC_STORE, TEST_SAMPLE_1


@pytest.mark.parametrize(
    "p_consumption_csv, with_results, power, tariff, tax_zone, discount",
    (
        (TEST_SAMPLE_1, True, 4.6, "NOC", "IVA", False),
        (TEST_SAMPLE_1, True, 4.6, "GEN", "IVA", False),
        # TODO fix VHC tariff, it does not match, should be 62,82 €, not 62.63
        (TEST_SAMPLE_1, False, 4.6, "VHC", "IVA", False),
        (TEST_SAMPLE_1, False, 3.45, "GEN", "IGIC", False),
        (TEST_SAMPLE_1, False, 3.45, "GEN", "IPSI", False),
        (TEST_SAMPLE_1, False, 4.6, "NOC", "IVA", True),
        (TEST_SAMPLE_1, False, 3.45, "NOC", "IGIC", True),
    ),
)
async def test_quick_bill_with_pvpc_store(
    p_consumption_csv, with_results, power, tariff, tax_zone, discount
):
    bill = await create_bill(
        path_csv_consumo=p_consumption_csv,
        path_csv_pvpc_store=TEST_PVPC_STORE,
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
