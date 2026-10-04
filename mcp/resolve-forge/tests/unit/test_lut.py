import pytest
from resolve_forge.domain.lut import Cube, blend, parse, serialise


def identity():
    return Cube(2, tuple((r, g, b) for b in (0., 1.) for g in (0., 1.) for r in (0., 1.)))


def test_lut_roundtrip_and_strength_endpoints():
    neutral = identity()
    assert parse(serialise(neutral)) == neutral
    graded = Cube(2, tuple((.1, .2, .3) for _ in range(8)))
    assert blend(graded, 0) == neutral
    assert blend(graded, 1) == graded
    assert blend(graded, .5).rows[0] == pytest.approx((.05, .1, .15))


@pytest.mark.parametrize("text", ["LUT_3D_SIZE 2\n0 0 0", "LUT_1D_SIZE 8", "LUT_3D_SIZE 999", "LUT_3D_SIZE 2\nnan 0 0"])
def test_invalid_tables_are_rejected(text):
    with pytest.raises(ValueError):
        parse(text)


def test_source_lut_is_preserved_and_output_cannot_be_overwritten(tmp_path):
    from resolve_forge.services.lut_service import prepare
    source, output = tmp_path / "original.cube", tmp_path / "adjusted.cube"
    text = serialise(identity())
    source.write_text(text)
    result = prepare(str(source), .5, str(output), False)
    assert result["applied"] and source.read_text() == text
    with pytest.raises(ValueError, match="never overwritten"):
        prepare(str(source), .5, str(output), False)
