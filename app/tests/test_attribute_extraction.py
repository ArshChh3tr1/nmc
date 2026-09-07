import pytest
from app.services.normalization.attribute_extractor import extract_attributes

def test_three_cpse_attribute_extraction_consistency():
    # Phrasing 1: IOCL
    ext_1 = extract_attributes("HEX BOLT SS M16 X 50")
    # Phrasing 2: BPCL
    ext_2 = extract_attributes("SS HEXAGONAL BOLT 16MM X 50MM")
    # Phrasing 3: HPCL
    ext_3 = extract_attributes("STAINLESS STEEL HEX BOLT M16-50")

    for ext in [ext_1, ext_2, ext_3]:
        assert ext["material"] == "Stainless Steel"
        assert ext["type"] == "Hex Bolt"
        dims = ext["dimensions"]
        assert dims["diameter_mm"] == 16.0
        assert dims["length_mm"] == 50.0
        assert dims["thread"] == "M16"
        assert ext["uom"] == "NOS"

def test_bearing_attribute_extraction():
    ext = extract_attributes("DEEP GROOVE BALL BEARING 6205-2RS SKF")
    assert ext["type"] == "Ball Bearing"
    assert "6205-2RS" in ext["dimensions"]["bearing_code"]

def test_pipe_and_valve_extraction():
    ext_pipe = extract_attributes("SEAMLESS PIPE CS ASTM A106 GR B 2 INCH SCH 40")
    assert ext_pipe["material"] == "Carbon Steel"
    assert ext_pipe["dimensions"]["nominal_bore"] == 2.0
    assert ext_pipe["dimensions"]["schedule"] == "40"
    assert "ASTM A106" in ext_pipe["specification"]

    ext_valve = extract_attributes("BALL VALVE 2 INCH 150# CS FLANGED WCB")
    assert ext_valve["material"] == "Carbon Steel"
    assert ext_valve["type"] == "Ball Valve"
    assert ext_valve["dimensions"]["pressure_class"] == 150
