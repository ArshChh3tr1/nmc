import pytest
from app.services.normalization.normalizer import normalize_text, get_normalizer

def test_abbreviation_expansion():
    normalizer = get_normalizer()
    assert "Stainless Steel" in normalizer.normalize("SS BOLT")
    assert "Stainless Steel" in normalizer.normalize("S/S BOLT")
    assert "Stainless Steel" in normalizer.normalize("STL BOLT")
    assert "Carbon Steel" in normalizer.normalize("CS PIPE")
    assert "Carbon Steel" in normalizer.normalize("C/S PIPE")
    assert "Hexagonal" in normalizer.normalize("HEX BOLT")
    assert "Bearing" in normalizer.normalize("BRG 6205")
    assert "Diameter" in normalizer.normalize("DIA 50")

def test_unit_unification():
    normalizer = get_normalizer()
    res_mm = normalizer.normalize("BOLT 16MM X 50MM")
    assert ("16 mm" in res_mm or "M16" in res_mm)
    assert "50 mm" in res_mm

    res_inch = normalizer.normalize('PIPE 2"')
    assert "2 inch" in res_inch

def test_three_cpse_bolt_normalization():
    # Three distinct CPSE phrasings for the identical bolt
    iocl_raw = "HEX BOLT SS M16 X 50"
    bpcl_raw = "SS HEXAGONAL BOLT 16MM X 50MM"
    hpcl_raw = "STAINLESS STEEL HEX BOLT M16-50"

    norm_iocl = normalize_text(iocl_raw)
    norm_bpcl = normalize_text(bpcl_raw)
    norm_hpcl = normalize_text(hpcl_raw)

    for n in [norm_iocl, norm_bpcl, norm_hpcl]:
        assert "Stainless Steel" in n
        assert "Hexagonal" in n
        assert "16" in n
        assert "50" in n
