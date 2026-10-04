"""Apply Forge-owned effect graphs with structural locks and unlocked input writes."""
from ..domain.fusion_graph import validate
from .context import video_items
from .native import accepted, fork, invoke, selected, verify


def graph(session, nodes, edges, track=1, index=1, copy_name=None, dry_run=True):
    validate(nodes, edges)
    ctx, items = selected(session, track, [index])
    if dry_run:
        return {"clip": items[0].GetName(), "nodes": nodes, "edges": edges, "applied": False}
    target = fork(session, "fusion", copy_name)
    item = video_items(target.context, track, [index])[0]
    count = int(invoke(item, "GetFusionCompCount"))
    comp = invoke(item, "GetFusionCompByIndex", 1) if count else accepted(item, "AddFusionComp")
    endpoints = {key: invoke(comp, "FindTool", key) for key in ("MediaIn1", "MediaOut1")}
    if any(endpoint is None for endpoint in endpoints.values()):
        raise ValueError("Composition needs MediaIn1 and MediaOut1.")
    if any(invoke(comp, "FindTool", "Forge_" + node["id"]) is not None for node in nodes):
        raise ValueError("Forge effect ids already exist in the composition; choose new ids.")
    invoke(comp, "Lock")
    try:
        for node in nodes:
            tool = accepted(comp, "AddTool", node["type"])
            invoke(tool, "SetAttrs", {"TOOLS_Name": "Forge_" + node["id"]})
            endpoints[node["id"]] = tool
        for source, destination, input_name in edges:
            accepted(endpoints[destination], "ConnectInput", input_name, endpoints[source])
    finally:
        invoke(comp, "Unlock")
    # Fusion reads values written under Lock but ignores them at render time.
    for node in nodes:
        for key, value in node.get("inputs", {}).items():
            tool = endpoints[node["id"]]
            result = invoke(tool, "SetInput", key, value)
            if result is False:
                from ..errors import ForgeError
                raise ForgeError("Fusion refused SetInput.", code="RESOLVE_REFUSED")
            # Fusion's SetInput is void on some builds; readback establishes success.
            verify(value, invoke(tool, "GetInput", key), key)
    return {"source": target.source, "timeline": target.target, "clip": item.GetName(),
            "nodes": ["Forge_" + node["id"] for node in nodes], "applied": True}


def inspect(session, track=1, index=1):
    ctx, items = selected(session, track, [index])
    item = items[0]
    count = int(invoke(item, "GetFusionCompCount"))
    return {"clip": item.GetName(), "compositions": [{"index": comp_index,
            "tools": [invoke(tool, "GetAttrs") for tool in (invoke(invoke(item, "GetFusionCompByIndex", comp_index), "GetToolList", False) or {}).values()]}
            for comp_index in range(1, count + 1)]}
