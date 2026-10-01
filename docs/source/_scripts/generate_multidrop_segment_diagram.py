"""
Generate a mermaid diagram of every multidrop segment in a workspace.

The four ``_static/images/examples`` diagrams are drawn by hand. This one is derived instead, so the picture in the documentation cannot
drift away from the YAML it describes.

Usage::

    python generate_multidrop_segment_diagram.py <workspace> [-o <output dir>]
"""

import argparse
import sys
from pathlib import Path

from flync.sdk.helpers.validation_helpers import validate_workspace

EXPORT_DIR = Path(__file__).resolve().parent / ".." / "_static" / "mermaid"


def _node_label(node) -> str:
    """One box per node: the ECU, the port it sits on, and the slot that decides its role."""

    if not node.participates:
        return f'"{node.ecu_name}<br/>{node.ecu_port_name}<br/>no slot"'
    return f'"{node.ecu_name}<br/>{node.ecu_port_name}<br/>slot {node.node_id} · {node.role}"'


def render(conn) -> str:
    cycle = f", TO timer {conn.plca.to_timer} bit times" if conn.plca is not None else ", no PLCA"
    medium = f'"{conn.id}<br/>shared single pair, {len(conn.nodes)} nodes{cycle}"'

    ordered = conn.participants + [n for n in conn.nodes if not n.participates]

    lines = ["graph TD", f"    MEDIUM[{medium}]"]
    for index, node in enumerate(ordered):
        box = f"N{index}"
        lines.append(f"    {box}[{_node_label(node)}]")
        lines.append(f"    MEDIUM --- {box}")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("-o", "--output-dir", type=Path, default=EXPORT_DIR)
    args = parser.parse_args(argv)

    result = validate_workspace(args.workspace)
    if result.model is None:
        print(f"{args.workspace} did not load", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for conn in result.model.multidrop_connections:
        target = args.output_dir / f"multidrop_segment_{conn.id.lower()}.mmd"
        target.write_text(render(conn), encoding="utf-8")
        print(f"wrote {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
