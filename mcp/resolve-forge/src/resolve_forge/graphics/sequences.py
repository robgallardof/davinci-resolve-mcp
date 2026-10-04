"""Bounded-memory PNG sequence writer; identical visual states share their disk bytes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def write_frames(folder: Path, frames: int, state_at, render_state) -> Path:
    if frames < 1:
        raise ValueError("Sequence needs at least one frame")
    folder.mkdir(parents=True, exist_ok=False)
    states = {}
    # Two files make Resolve recognize a sequence rather than a five-second still.
    # The service trims that sequence to the actual one-frame duration when needed.
    for frame in range(max(2, frames)):
        state = state_at(min(frame, frames - 1))
        destination = folder / f"{folder.name}_{frame:06d}.png"
        if state not in states:
            render_state(state).save(destination)
            states[state] = destination
        else:
            try:
                os.link(states[state], destination)
            except OSError:
                shutil.copyfile(states[state], destination)
    return folder
