"""Tests for pvpcbill."""
import json
import pathlib

TEST_EXAMPLES_PATH = pathlib.Path(__file__).parent / "ejemplos_consumo"


def load_json_fixture(filename: str):
    """Load stored JSON data."""
    return json.loads((TEST_EXAMPLES_PATH / filename).read_text())
