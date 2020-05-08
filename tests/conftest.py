"""Tests for pvpcbill."""
import json
import pathlib

TEST_EXAMPLES_PATH = pathlib.Path(__file__).parent / "ejemplos_consumo"

TEST_PVPC_STORE = TEST_EXAMPLES_PATH / "pvpc_test_data.csv"
TEST_SAMPLE_1 = TEST_EXAMPLES_PATH / "consumo_facturado18_02_2020-18_03_2020-R.csv"


def load_json_fixture(filename: str):
    """Load stored JSON data."""
    return json.loads((TEST_EXAMPLES_PATH / filename).read_text())
