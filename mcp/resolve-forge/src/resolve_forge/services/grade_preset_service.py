"""Creative preset grading delegates mutation and copying to the existing grade service."""
from ..domain.grade_presets import parameters
from . import color_service


def apply(session, preset="natural", intensity=.5, track=1, indices=None, copy_name=None, dry_run=True):
    values = parameters(preset, intensity)
    result = color_service.grade(session, **values, track=track, indices=indices,
                                 copy_name=copy_name, dry_run=dry_run)
    return {**result, "preset": preset, "intensity": intensity,
            "scope": "Creative display-referred CDL; does not detect/correct exposure or transform log/HDR. Correct input color management first; compare skin/highlights before render. Existing CDL on node 1 is replaced on the copy."}
