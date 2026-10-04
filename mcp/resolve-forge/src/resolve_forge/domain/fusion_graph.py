"""Validate a finite, acyclic effect graph before changing a composition."""
import re

EFFECTS = {"Transform", "Blur", "BrightnessContrast", "TextPlus", "Background", "Merge", "ColorCorrector", "Dissolve", "Crop", "Resize"}


def validate(nodes, edges):
    if not nodes or len(nodes) > 64 or len(edges) > 128:
        raise ValueError("Graphs need 1–64 effect nodes and at most 128 edges.")
    identities = set()
    for node in nodes:
        identity = node.get("id", "")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", identity) or identity in identities:
            raise ValueError("Effect ids must be distinct alphanumeric names.")
        if node.get("type") not in EFFECTS:
            raise ValueError("Effect type is outside the supported graph palette.")
        if not isinstance(node.get("inputs", {}), dict):
            raise ValueError("Node inputs must be a dictionary.")
        if any(key in {"Clip", "Filename", "FileName", "Expression"} or not isinstance(key, str) for key in node.get("inputs", {})):
            raise ValueError("Graphs cannot load files or execute expressions.")
        identities.add(identity)
    available = identities | {"MediaIn1", "MediaOut1"}
    dependencies, occupied = {identity: [] for identity in available}, set()
    for edge in edges:
        if len(edge) != 3:
            raise ValueError("Each edge needs source, destination and destination input.")
        source, destination, input_name = edge
        if source not in available or destination not in available or source == "MediaOut1" or destination == "MediaIn1":
            raise ValueError("Unknown or invalid connection endpoint.")
        if not isinstance(input_name, str) or not input_name or (destination, input_name) in occupied:
            raise ValueError("Every destination input accepts exactly one connection.")
        occupied.add((destination, input_name))
        dependencies[destination].append(source)
    visiting, visited = set(), set()
    def visit(identity):
        if identity in visiting:
            raise ValueError("Fusion graphs cannot contain cycles.")
        if identity in visited:
            return
        visiting.add(identity)
        for parent in dependencies[identity]:
            visit(parent)
        visiting.remove(identity)
        visited.add(identity)
    for identity in available:
        visit(identity)
    return nodes, edges
