"""Create strength-adjusted LUTs in new files, preserving the original table."""
from pathlib import Path
from ..domain import lut


def prepare(source_path, strength=1., output_path=None, dry_run=True):
    source = Path(source_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".cube" or source.stat().st_size > 40 * 1024 * 1024:
        raise ValueError("Use an existing .cube LUT smaller than 40 MiB.")
    cube = lut.parse(source.read_text(encoding="utf-8-sig"))
    adjusted = lut.blend(cube, strength)
    if dry_run:
        return {"size": cube.size, "samples": len(cube.rows), "strength": strength, "applied": False}
    output = Path(output_path or Path.home() / "Movies/resolve-forge" / (source.stem + "_forge.cube")).expanduser().resolve()
    if output.suffix.lower() != ".cube" or output.exists():
        raise ValueError("Use a new .cube destination; source LUTs are never overwritten.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        destination.write(lut.serialise(adjusted))
    return {"file": str(output), "size": adjusted.size, "strength": strength, "applied": True}
