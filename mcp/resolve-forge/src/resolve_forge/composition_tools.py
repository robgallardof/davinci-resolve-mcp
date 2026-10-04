"""Thin surface for producer-selected multi-source compositions."""
from .services import composition_service


def register(mcp, session, safe):
    @mcp.tool()
    @safe
    def plan_composition(segments: list[dict], audio_master: dict, format: str = "tiktok") -> dict:
        """Preview multi-source mosaics (1..5) or hero_support; independent videos, photos and source starts.

        segments: {duration_s,layout:mosaic|hero_support,sources:[{source,start_s:0,crop:[x0,y0,x1,y1],
        subject:[x0,y0,x1,y1],fit:contain|cover}]}. crop OR subject, normalized 0..1; subject is manual.
        audio_master:{source,start_s:0} required: ONE continuous soundtrack, no visual-source audio mixing.
        Creates a low resolution preview video with soundtrack and start/middle/end contact sheet in Movies.
        Producer decides when to use layouts; not an automatic multi-person rule. No Resolve mutation.
        """
        return composition_service.plan(session, segments, audio_master, format)

    @mcp.tool()
    @safe
    def build_composition(segments: list[dict], audio_master: dict, name: str, format: str = "tiktok",
                          into_resolve: bool = False, dry_run: bool = True, reviewed: bool = False) -> dict:
        """Render a NEW composition asset in Movies; optionally assemble a NEW Resolve timeline.

        Schema matches plan_composition. Preview default; real build requires reviewed=true after looking
        at the plan's sheet and preview video. Source files untouched; master audio is continuous, never
        selected implicitly from a panel. Stills held for segment duration. Maximum asset 120 seconds.
        """
        return composition_service.build(session, segments, audio_master, name, format, into_resolve, dry_run, reviewed)
