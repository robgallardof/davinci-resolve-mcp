"""Parse bounded 3D .cube tables and blend a LUT with the identity transform."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Cube:
    size: int
    rows: tuple
    minimum: tuple = (0., 0., 0.)
    maximum: tuple = (1., 1., 1.)


def parse(text):
    size, rows, minimum, maximum = None, [], (0., 0., 0.), (1., 1., 1.)
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("TITLE "):
            continue
        parts = line.split()
        if parts[0] == "LUT_3D_SIZE":
            if size is not None or len(parts) != 2:
                raise ValueError("Exactly one LUT_3D_SIZE is required.")
            size = int(parts[1])
            if not 2 <= size <= 65:
                raise ValueError("LUT sizes must be between 2 and 65.")
        elif parts[0] in {"DOMAIN_MIN", "DOMAIN_MAX"}:
            values = tuple(float(value) for value in parts[1:])
            if len(values) != 3 or not all(math.isfinite(value) for value in values):
                raise ValueError("LUT domains need three finite values.")
            if parts[0] == "DOMAIN_MIN":
                minimum = values
            else:
                maximum = values
        else:
            if len(parts) != 3:
                raise ValueError("Only 3D LUT tables with three-channel rows are supported.")
            row = tuple(float(value) for value in parts)
            if not all(math.isfinite(value) for value in row):
                raise ValueError("LUT samples must be finite.")
            rows.append(row)
            if len(rows) > 65 ** 3:
                raise ValueError("LUT sample capacity exceeded.")
    if size is None or len(rows) != size ** 3 or any(a >= b for a, b in zip(minimum, maximum)):
        raise ValueError("LUT sample count or domain is invalid.")
    return Cube(size, tuple(rows), minimum, maximum)


def blend(cube, strength):
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("LUT strength must lie in [0, 1].")
    rows = []
    for index, row in enumerate(cube.rows):
        coordinates = (index % cube.size, (index // cube.size) % cube.size, index // (cube.size ** 2))
        identity = [low + coordinate / (cube.size - 1) * (high - low) for coordinate, low, high in zip(coordinates, cube.minimum, cube.maximum)]
        rows.append(tuple(original * strength + neutral * (1 - strength) for original, neutral in zip(row, identity)))
    return Cube(cube.size, tuple(rows), cube.minimum, cube.maximum)


def serialise(cube):
    vector = lambda values: " ".join(format(value, ".9g") for value in values)
    return "\n".join([f"LUT_3D_SIZE {cube.size}", "DOMAIN_MIN " + vector(cube.minimum),
                      "DOMAIN_MAX " + vector(cube.maximum), *[vector(row) for row in cube.rows]]) + "\n"
