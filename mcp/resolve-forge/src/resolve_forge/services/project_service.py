"""Project lifecycle and backups, independent of MCP registration."""
from pathlib import Path

from .native import accepted, invoke, name, timelines
from .context import current


def manage(session, action, project_name=None, output_path=None):
    manager = session.resolve().GetProjectManager()
    if action == "list":
        return {"projects": invoke(manager, "GetProjectListInCurrentFolder") or []}
    if action in {"create", "load"}:
        project = accepted(manager, "CreateProject" if action == "create" else "LoadProject", name(project_name))
        return {"project": project.GetName()}
    ctx = current(session, need_timeline=False)
    if action == "inspect":
        return {"project": ctx.project.GetName(), "settings": invoke(ctx.project, "GetSetting"),
                "timelines": [{"index": index, "name": timeline.GetName()} for index, timeline in enumerate(timelines(ctx.project), 1)]}
    if action == "save":
        accepted(manager, "SaveProject")
        return {"project": ctx.project.GetName(), "saved": True}
    if action == "backup":
        output = Path(output_path or Path.home() / "Movies/resolve-forge" / (ctx.project.GetName() + ".drp")).expanduser().resolve()
        if output.suffix.lower() != ".drp" or output.exists():
            raise ValueError("Backup needs a new .drp path; existing backups are never overwritten.")
        output.parent.mkdir(parents=True, exist_ok=True)
        accepted(manager, "SaveProject")
        accepted(manager, "ExportProject", ctx.project.GetName(), str(output))
        if not output.is_file() or output.stat().st_size == 0:
            raise ValueError("Resolve reported export success but the backup is absent or empty.")
        return {"backup": str(output), "bytes": output.stat().st_size}
    raise ValueError("Project action must be list, inspect, create, load, save or backup.")


def configure(session, settings, dry_run=True):
    if not settings or any(not isinstance(key, str) or not isinstance(value, (str, int, float, bool)) for key, value in settings.items()):
        raise ValueError("Settings must be a non-empty dictionary of scalar values.")
    ctx = current(session, need_timeline=False)
    before = {key: invoke(ctx.project, "GetSetting", key) for key in settings}
    if not dry_run:
        from .native import verify
        for key, value in settings.items():
            accepted(ctx.project, "SetSetting", key, str(value))
            verify(str(value), invoke(ctx.project, "GetSetting", key), key)
    return {"project": ctx.project.GetName(), "before": before, "requested": settings, "applied": not dry_run}
