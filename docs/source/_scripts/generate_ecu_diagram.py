"""
Generate an SVG diagram of an ECU variant from its FLYNC configuration.

Supports the eight ECU variants under ``examples/ecu_variants/``:

    1. single_controller_single_iface_ext_PHY
    2. single_controller_single_iface_int_PHY
    3. single_controller_multiple_iface_ext_PHY
    4. single_controller_multiple_iface_int_PHY
    5. single_controller_single_iface_multiple_vms
    6. single_controller_multiple_iface_physical_ext_phy
    7. switch_ecu_ext_PHY
    8. switch_ecu_with_host_ext_PHY

Usage:

    python scripts/helpers/generate_ecu_diagram.py <path> [-o <output.svg>]

If ``path`` is a single ECU directory it is rendered to ``<output.svg>`` (default
``<ecu_name>.svg`` next to the config). If ``path`` is a parent directory, every
immediate child that looks like an ECU config is rendered to
``<child>.svg`` next to the child directory.
"""

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from flync.model.flync_4_ecu.ecu import ECU
from flync.sdk.helpers.validation_helpers import validate_external_node

MII_OPTIONS = ["mii", "rmii", "sgmii", "rgmii"]
SPEED_LABELS = [
    ("100baset1", "base_t1", 100),
    ("1000baset1", "base_t1", 1000),
    ("10baset1s", "base_t1s", 10),
]

ECU_FILL, ECU_STROKE = "#dceaf7", "#6c8ebf"
CTRL_FILL, CTRL_STROKE = "#cadcf2", "#6c8ebf"
IFACE_FILL, IFACE_STROKE = "#b6cded", "#6c8ebf"
PHY_FILL, PHY_STROKE = "#ffe6cc", "#d79b00"
PORT_FILL, PORT_STROKE = "#d5e8d4", "#82b366"
SWITCH_FILL, SWITCH_STROKE = "#fff2cc", "#d6b656"
SWITCH_PORT_FILL, SWITCH_PORT_STROKE = "#ffe6cc", "#d79b00"
SILICON_FILL, SILICON_STROKE = "#f5f5f5", "#666666"
BRIDGE_FILL, BRIDGE_STROKE = "#fff2cc", "#d6b656"

VLAN_PALETTE = {
    10: ("#f8cecc", "#b85450"),
    20: ("#e1d5e7", "#9673a6"),
    30: ("#d5e8d4", "#82b366"),
}
DEFAULT_VIFACE_COLOR = ("#c5a9c8", "#7e5285")


def vlan_color(vlan_id: int) -> tuple[str, str]:
    return VLAN_PALETTE.get(vlan_id, DEFAULT_VIFACE_COLOR)


class SVG:
    """Minimal SVG builder with the primitives this script needs."""

    def __init__(self, width: float, height: float):
        self.w = width
        self.h = height
        self.parts: list[str] = []

    def rect(self, x, y, w, h, *, fill="none", stroke="none", sw=1.0, rx=4):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def line(self, x1, y1, x2, y2, *, dashed=False, sw=1.0):
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000000" stroke-width="{sw}"{dash}/>'
        )

    def text(self, x, y, content, *, size=12, anchor="start", bold=False):
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}"{weight}>'
            f"{escape(content)}</text>"
        )

    def options(self, x, y, opts, *, size=11, anchor="start"):
        parts = []
        for i, (label, active) in enumerate(opts):
            if i > 0:
                parts.append(" | ")
            if active:
                parts.append(f'<tspan font-weight="bold">{escape(label)}</tspan>')
            else:
                parts.append(escape(label))
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}">{"".join(parts)}</text>'
        )

    def vlan_oval(self, cx, cy, vlan_id, *, w=58, h=22):
        fill, stroke = vlan_color(vlan_id)
        self.parts.append(
            f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" '
            f'rx="{h / 2}" ry="{h / 2}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        self.text(cx, cy + 4, f"VLAN {vlan_id}", size=10, anchor="middle", bold=True)

    def viface(self, x, y, w, name, addresses, vlan_id, *, with_oval=False):
        """
        Draw a viface tile (colored header + white body with addresses). When ``with_oval`` and
        the VLAN id is non-zero, a VLAN tag oval is rendered overlapping the right edge.

        Returns the y of the bottom edge.
        """
        fill, stroke = vlan_color(vlan_id)
        header_h, body_h = 20, 28
        self.rect(x, y, w, header_h, fill=fill, stroke=stroke, sw=1, rx=1)
        self.text(x + w / 2, y + 14, name, size=10, anchor="middle", bold=True)
        self.rect(x, y + header_h, w, body_h, fill="#ffffff", stroke=stroke, sw=1, rx=1)
        addrs = ", ".join(str(a.address) for a in addresses)
        self.text(x + 6, y + header_h + 18, f"addresses: [{addrs}]", size=10)
        bottom = y + header_h + body_h
        if with_oval and vlan_id != 0:
            ox = x + w - 25
            oy = y + header_h + body_h / 2 + 4
            self.vlan_oval(ox, oy, vlan_id)
        return bottom

    def render(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="12">'
            '<rect width="100%" height="100%" fill="#ffffff"/>'
            + "\n".join(self.parts)
            + "</svg>"
        )


def mii_opts(active_type):
    return [(o, o == active_type) for o in MII_OPTIONS]


def role_opts(role):
    return [("master", role == "master"), ("slave", role == "slave")]


def speed_opts(mode, speed):
    out = []
    has_active = False
    for label, m, s in SPEED_LABELS:
        is_active = m == mode and s == speed
        out.append((label, is_active))
        if is_active:
            has_active = True
    if not has_active:
        out.insert(0, (f"{speed}{mode.replace('_', '')}", True))
    return out


def has_ext_phy(ecu: ECU) -> bool:
    return any(p.mii_config is not None for p in ecu.ports)


def _port_for_iface(ecu: ECU, iface_name: str):
    """Return the ECUPort directly connected to ``iface_name`` (via ecu_port_to_controller_interface)."""
    for conn in ecu.topology.connections:
        c = conn.root if hasattr(conn, "root") else conn
        if getattr(c, "type", None) == "ecu_port_to_controller_interface" and c.iface_name == iface_name:
            return c.ecu_port
    return None


def _port_for_switch_port(ecu: ECU, switch_port_name: str):
    """Return the ECUPort connected to ``switch_port_name`` (via ecu_port_to_switch_port)."""
    for conn in ecu.topology.connections:
        c = conn.root if hasattr(conn, "root") else conn
        if getattr(c, "type", None) == "ecu_port_to_switch_port" and c.switch_port_name == switch_port_name:
            return c.ecu_port
    return None


def detect_pattern(ecu: ECU) -> str:
    n_ctrl = len(ecu.controllers)
    n_sw = len(ecu.switches) if ecu.switches else 0
    if n_ctrl != 1:
        raise ValueError("Only ECUs with exactly one controller are supported.")
    ctrl = ecu.controllers[0]
    n_iface = len(ctrl.ethernet_interfaces)
    if n_sw == 0:
        if n_iface == 1:
            iface = ctrl.ethernet_interfaces[0].interface_config
            if iface.compute_nodes:
                return "vms"
            return "single_viface" if len(iface.virtual_interfaces) == 1 else "multi_viface"
        return "multi_physical_iface"
    sw = ecu.switches[0]
    return "switch_with_host" if sw.host_controller is not None else "switch"


def _draw_ext_phy_chain(svg, *, line_x, top_y, port_y, mii_type, mdi_config, port_name):
    """
    Render the external-PHY chain below an ECU box: dashed line to PHY, MII labels, dashed line to
    ECU port, MDI labels, port box.
    """
    phy_w, phy_h = 60, 28
    phy_x = line_x - phy_w / 2
    phy_y = top_y + 30
    svg.line(line_x, top_y, line_x, phy_y, dashed=True)
    mid_y = (top_y + phy_y) / 2 + 4
    svg.options(line_x + 12, mid_y, mii_opts(mii_type))
    svg.rect(phy_x, phy_y, phy_w, phy_h, fill=PHY_FILL, stroke=PHY_STROKE, sw=1, rx=3)
    svg.text(phy_x + phy_w / 2, phy_y + phy_h / 2 + 4, "PHY", size=12, anchor="middle", bold=True)

    line2_top = phy_y + phy_h
    svg.line(line_x, line2_top, line_x, port_y, dashed=True)
    mid_y2 = (line2_top + port_y) / 2 + 4
    svg.options(line_x - 60, mid_y2, role_opts(mdi_config.role), anchor="end")
    svg.options(line_x + 18, mid_y2, speed_opts(mdi_config.mode, mdi_config.speed))

    port_w, port_h = 110, 28
    svg.rect(line_x - port_w / 2, port_y, port_w, port_h, fill=PORT_FILL, stroke=PORT_STROKE, sw=1, rx=3)
    svg.text(line_x, port_y + port_h / 2 + 4, port_name, size=12, anchor="middle", bold=True)


def _draw_int_phy_chain(svg, *, line_x, top_y, ecu_bottom, port_y, mdi_config, port_name):
    """
    Render the integrated-PHY chain: PHY box still inside the ECU outline, dashed line to it from
    the iface, dashed line to the port, MDI labels.
    """
    phy_w, phy_h = 110, 28
    phy_x = line_x - phy_w / 2
    phy_y = ecu_bottom - phy_h - 12
    svg.line(line_x, top_y, line_x, phy_y, dashed=True)
    svg.rect(phy_x, phy_y, phy_w, phy_h, fill=PHY_FILL, stroke=PHY_STROKE, sw=1, rx=3)
    svg.text(phy_x + phy_w / 2, phy_y + phy_h / 2 + 4, "Integrated PHY", size=12, anchor="middle", bold=True)

    line2_top = phy_y + phy_h
    svg.line(line_x, line2_top, line_x, port_y, dashed=True)
    mid_y = (line2_top + port_y) / 2 + 4
    svg.options(line_x - 60, mid_y, role_opts(mdi_config.role), anchor="end")
    svg.options(line_x + 18, mid_y, speed_opts(mdi_config.mode, mdi_config.speed))

    port_w, port_h = 110, 28
    svg.rect(line_x - port_w / 2, port_y, port_w, port_h, fill=PORT_FILL, stroke=PORT_STROKE, sw=1, rx=3)
    svg.text(line_x, port_y + port_h / 2 + 4, port_name, size=12, anchor="middle", bold=True)


# ============================================================================
# Layouts
# ============================================================================


def render_single_viface(ecu: ECU) -> str:
    """Variants 1 (ext PHY) and 2 (int PHY): one controller, one iface, one viface."""
    ext = has_ext_phy(ecu)
    ctrl = ecu.controllers[0]
    iface = ctrl.ethernet_interfaces[0].interface_config
    viface = iface.virtual_interfaces[0]
    port = ecu.ports[0]

    width = 470
    height = 470 if ext else 460
    ecu_x, ecu_y, ecu_w = 15, 30, width - 30
    ecu_h = 240 if ext else 290
    ctrl_x, ctrl_y = ecu_x + 25, ecu_y + 35
    ctrl_w, ctrl_h = ecu_w - 50, (ecu_h - 55) if ext else (ecu_h - 95)
    if_x, if_y = ctrl_x + 20, ctrl_y + 35
    if_w, if_h = ctrl_w - 40, ctrl_h - 55
    line_x = ecu_x + ecu_w / 2

    svg = SVG(width, height)
    svg.rect(ecu_x, ecu_y, ecu_w, ecu_h, fill=ECU_FILL, stroke=ECU_STROKE, sw=1.5, rx=6)
    svg.text(ecu_x + ecu_w / 2, ecu_y + 18, ecu.name, size=14, anchor="middle", bold=True)
    svg.rect(ctrl_x, ctrl_y, ctrl_w, ctrl_h, fill=CTRL_FILL, stroke=CTRL_STROKE, sw=1.2, rx=5)
    svg.text(ctrl_x + ctrl_w / 2, ctrl_y + 18, ctrl.name, size=13, anchor="middle", bold=True)
    svg.rect(if_x, if_y, if_w, if_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
    svg.text(if_x + if_w / 2, if_y + 18, iface.name, size=12, anchor="middle", bold=True)
    svg.viface(if_x + 20, if_y + 35, if_w - 40, viface.name, viface.addresses, viface.vlanid)

    port_y = height - 28 - 15
    if ext:
        _draw_ext_phy_chain(
            svg,
            line_x=line_x,
            top_y=ecu_y + ecu_h,
            port_y=port_y,
            mii_type=iface.mii_config.type if iface.mii_config else None,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )
    else:
        _draw_int_phy_chain(
            svg,
            line_x=line_x,
            top_y=if_y + if_h,
            ecu_bottom=ecu_y + ecu_h,
            port_y=port_y,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )

    return svg.render()


def render_multi_viface(ecu: ECU) -> str:
    """Variants 3 (ext PHY) and 4 (int PHY): one iface, two or more vifaces side-by-side."""
    ext = has_ext_phy(ecu)
    ctrl = ecu.controllers[0]
    iface = ctrl.ethernet_interfaces[0].interface_config
    vifaces = iface.virtual_interfaces
    port = ecu.ports[0]

    n = len(vifaces)
    viface_w = 250
    gap = 20
    inner_w = n * viface_w + (n - 1) * gap
    if_w = inner_w + 40
    ctrl_w = if_w + 40
    ecu_w = ctrl_w + 50
    width = ecu_w + 30

    height = 470 if ext else 460
    ecu_x, ecu_y = 15, 30
    ecu_h = 240 if ext else 290
    ctrl_x, ctrl_y = ecu_x + 25, ecu_y + 35
    ctrl_h = (ecu_h - 55) if ext else (ecu_h - 95)
    if_x, if_y = ctrl_x + 20, ctrl_y + 35
    if_h = ctrl_h - 55
    line_x = ecu_x + ecu_w / 2

    svg = SVG(width, height)
    svg.rect(ecu_x, ecu_y, ecu_w, ecu_h, fill=ECU_FILL, stroke=ECU_STROKE, sw=1.5, rx=6)
    svg.text(ecu_x + ecu_w / 2, ecu_y + 18, ecu.name, size=14, anchor="middle", bold=True)
    svg.rect(ctrl_x, ctrl_y, ctrl_w, ctrl_h, fill=CTRL_FILL, stroke=CTRL_STROKE, sw=1.2, rx=5)
    svg.text(ctrl_x + ctrl_w / 2, ctrl_y + 18, ctrl.name, size=13, anchor="middle", bold=True)
    svg.rect(if_x, if_y, if_w, if_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
    svg.text(if_x + if_w / 2, if_y + 18, iface.name, size=12, anchor="middle", bold=True)

    vif_y = if_y + 40
    for i, v in enumerate(vifaces):
        vx = if_x + 20 + i * (viface_w + gap)
        svg.viface(vx, vif_y, viface_w, v.name, v.addresses, v.vlanid, with_oval=True)

    port_y = height - 28 - 15
    if ext:
        _draw_ext_phy_chain(
            svg,
            line_x=line_x,
            top_y=ecu_y + ecu_h,
            port_y=port_y,
            mii_type=iface.mii_config.type if iface.mii_config else None,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )
    else:
        _draw_int_phy_chain(
            svg,
            line_x=line_x,
            top_y=if_y + if_h,
            ecu_bottom=ecu_y + ecu_h,
            port_y=port_y,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )

    return svg.render()


def render_vms(ecu: ECU) -> str:
    """Variant 5: single iface plus compute nodes wired through a Virtual Switch."""

    ext = has_ext_phy(ecu)
    ctrl = ecu.controllers[0]
    iface = ctrl.ethernet_interfaces[0].interface_config
    vms = list(iface.compute_nodes)
    port = ecu.ports[0]
    bridge = ctrl.virtual_switch

    width = 720
    height = 720
    ecu_x, ecu_y, ecu_w, ecu_h = 15, 30, width - 30, 470
    ctrl_x, ctrl_y, ctrl_w, ctrl_h = ecu_x + 30, ecu_y + 35, ecu_w - 60, ecu_h - 55
    line_x = ecu_x + ecu_w / 2

    svg = SVG(width, height)
    svg.rect(ecu_x, ecu_y, ecu_w, ecu_h, fill=ECU_FILL, stroke=ECU_STROKE, sw=1.5, rx=6)
    svg.text(ecu_x + ecu_w / 2, ecu_y + 18, ecu.name, size=14, anchor="middle", bold=True)
    svg.rect(ctrl_x, ctrl_y, ctrl_w, ctrl_h, fill=CTRL_FILL, stroke=CTRL_STROKE, sw=1.2, rx=5)
    svg.text(ctrl_x + ctrl_w / 2, ctrl_y + 18, ctrl.name, size=13, anchor="middle", bold=True)

    vm_w, vm_h = 230, 100
    vm_y = ctrl_y + 50
    vm_xs = [ctrl_x + 30 + i * (vm_w + 30) for i in range(len(vms))]
    if len(vms) == 2:
        vm_xs = [ctrl_x + 30, ctrl_x + ctrl_w - vm_w - 30]
    for vm, vx in zip(vms, vm_xs):
        svg.rect(vx, vm_y, vm_w, vm_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=3)
        svg.text(vx + vm_w / 2, vm_y + 16, vm.name, size=11, anchor="middle", bold=True)
        v0 = vm.virtual_interfaces[0]
        svg.viface(vx + 10, vm_y + 30, vm_w - 20, v0.name, v0.addresses, v0.vlanid, with_oval=True)

    bridge_w, bridge_h = 160, 50
    bridge_x = ctrl_x + (ctrl_w - bridge_w) / 2
    bridge_y = vm_y + vm_h + 30
    svg.rect(bridge_x, bridge_y, bridge_w, bridge_h, fill=BRIDGE_FILL, stroke=BRIDGE_STROKE, sw=1, rx=8)
    bridge_label = f"virtual_switch {bridge.name}" if bridge else "virtual_switch"
    svg.text(bridge_x + bridge_w / 2, bridge_y + bridge_h / 2 + 4, bridge_label, size=12, anchor="middle")

    if_w, if_h = 250, 90
    if_x = ctrl_x + (ctrl_w - if_w) / 2
    if_y = bridge_y + bridge_h + 30
    svg.rect(if_x, if_y, if_w, if_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
    svg.text(if_x + if_w / 2, if_y + 14, iface.name, size=11, anchor="middle", bold=True)
    v0 = iface.virtual_interfaces[0]
    svg.viface(if_x + 10, if_y + 25, if_w - 20, v0.name, v0.addresses, v0.vlanid, with_oval=True)

    for vx in vm_xs:
        vm_cx = vx + vm_w / 2
        svg.line(vm_cx, vm_y + vm_h, vm_cx, bridge_y)
        target_x = bridge_x if vm_cx < bridge_x + bridge_w / 2 else bridge_x + bridge_w
        svg.line(vm_cx, bridge_y, target_x, bridge_y)
    svg.line(bridge_x + bridge_w / 2, bridge_y + bridge_h, if_x + if_w / 2, if_y)

    port_y = height - 28 - 15
    if ext:
        _draw_ext_phy_chain(
            svg,
            line_x=line_x,
            top_y=ecu_y + ecu_h,
            port_y=port_y,
            mii_type=iface.mii_config.type if iface.mii_config else None,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )
    else:
        _draw_int_phy_chain(
            svg,
            line_x=line_x,
            top_y=if_y + if_h,
            ecu_bottom=ecu_y + ecu_h,
            port_y=port_y,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )

    return svg.render()


def render_multi_physical_iface(ecu: ECU) -> str:
    """Variant 6: multiple physical interfaces, each with its own external PHY/port, bridged."""
    ctrl = ecu.controllers[0]
    ifaces = sorted((ei.interface_config for ei in ctrl.ethernet_interfaces), key=lambda i: i.name)
    bridge = ctrl.virtual_switch

    n = len(ifaces)
    if_w = 260
    gap = 110
    width = max(800, n * if_w + (n + 1) * gap + 60)
    height = 660

    ecu_x, ecu_y, ecu_w, ecu_h = 15, 30, width - 30, 280
    ctrl_x, ctrl_y, ctrl_w, ctrl_h = ecu_x + 25, ecu_y + 35, ecu_w - 50, ecu_h - 55

    svg = SVG(width, height)
    svg.rect(ecu_x, ecu_y, ecu_w, ecu_h, fill=ECU_FILL, stroke=ECU_STROKE, sw=1.5, rx=6)
    svg.text(ecu_x + ecu_w / 2, ecu_y + 18, ecu.name, size=14, anchor="middle", bold=True)
    svg.rect(ctrl_x, ctrl_y, ctrl_w, ctrl_h, fill=CTRL_FILL, stroke=CTRL_STROKE, sw=1.2, rx=5)
    svg.text(ctrl_x + ctrl_w / 2, ctrl_y + 18, ctrl.name, size=13, anchor="middle", bold=True)

    if_y = ctrl_y + 50
    if_h = 90
    iface_xs = []
    for i, iface in enumerate(ifaces):
        ix = ctrl_x + (ctrl_w - n * if_w - (n - 1) * gap) / 2 + i * (if_w + gap)
        iface_xs.append(ix)
        svg.rect(ix, if_y, if_w, if_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
        svg.text(ix + if_w / 2, if_y + 14, iface.name, size=11, anchor="middle", bold=True)
        v0 = iface.virtual_interfaces[0]
        svg.viface(ix + 10, if_y + 25, if_w - 20, v0.name, v0.addresses, v0.vlanid, with_oval=True)

    bridge_w, bridge_h = 160, 40
    bridge_x = ctrl_x + (ctrl_w - bridge_w) / 2
    bridge_y = if_y + if_h + 25
    svg.rect(bridge_x, bridge_y, bridge_w, bridge_h, fill=BRIDGE_FILL, stroke=BRIDGE_STROKE, sw=1, rx=8)
    bridge_label = f"virtual_switch {bridge.name}" if bridge else "virtual_switch"
    svg.text(bridge_x + bridge_w / 2, bridge_y + bridge_h / 2 + 4, bridge_label, size=12, anchor="middle")
    for ix in iface_xs:
        iface_cx = ix + if_w / 2
        svg.line(iface_cx, if_y + if_h, iface_cx, bridge_y)
        target_x = bridge_x if iface_cx < bridge_x + bridge_w / 2 else bridge_x + bridge_w
        svg.line(iface_cx, bridge_y, target_x, bridge_y)

    port_y = height - 28 - 15
    for iface, ix in zip(ifaces, iface_xs):
        port = _port_for_iface(ecu, iface.name)
        if port is None:
            continue
        line_x = ix + if_w / 2
        _draw_ext_phy_chain(
            svg,
            line_x=line_x,
            top_y=ecu_y + ecu_h,
            port_y=port_y,
            mii_type=iface.mii_config.type if iface.mii_config else None,
            mdi_config=port.mdi_config,
            port_name=port.name,
        )

    return svg.render()


def _vlans_block(svg, switch, port, *, cx, cy_center):
    """
    Render a ``<port>.vlans`` capsule centered at (``cx``, ``cy_center``) containing every VLAN
    that ``port`` is a member of, stacked vertically as colored ovals.
    """
    member_vlans = [v.id for v in switch.vlans if port.name in v.ports]
    if not member_vlans:
        return
    label_w = 100
    label_h = 14 + len(member_vlans) * 26
    lx = cx - label_w / 2
    ly = cy_center - label_h / 2
    svg.rect(lx, ly, label_w, label_h, fill="#fff8e1", stroke="#d2912a", sw=0.7, rx=4)
    svg.text(cx, ly + 12, f"{port.name}.vlans", size=9, anchor="middle")
    for i, vid in enumerate(member_vlans):
        svg.vlan_oval(cx, ly + 28 + i * 26, vid)


def render_switch(ecu: ECU, *, with_host: bool = False) -> str:
    """Variants 7 and 8: ECU with one switch (variant 8 also has a host_controller)."""
    ctrl = ecu.controllers[0]
    iface = ctrl.ethernet_interfaces[0].interface_config
    switch = ecu.switches[0]

    sw_ports = sorted(switch.ports, key=lambda p: p.silicon_port_no)
    top_port = sw_ports[0]
    bottom_ports = sw_ports[1:]
    n_ext = len(bottom_ports)
    n_vifaces = len(iface.virtual_interfaces)

    chain_pitch = 360
    width_for_chains = max(700, n_ext * chain_pitch + 120)
    width_for_vifaces = n_vifaces * 230 + 100
    width = max(width_for_chains, width_for_vifaces, 720 if with_host else 700)

    ecu_x, ecu_y, ecu_w = 15, 30, width - 30
    ctrl_w = ecu_w - 50
    ctrl_x = ecu_x + 25
    ctrl_y = ecu_y + 35
    ctrl_h = 170
    if_w = ctrl_w - 40
    if_h = ctrl_h - 55
    if_x = ctrl_x + 20
    if_y = ctrl_y + 35

    sw_x = ecu_x + 25
    sw_y = ctrl_y + ctrl_h + 60
    sw_w = ecu_w - 50
    sw_h = 320 if with_host else 280

    ecu_h = (sw_y + sw_h) - ecu_y + 10
    height = ecu_y + ecu_h + 170

    svg = SVG(width, height)
    svg.rect(ecu_x, ecu_y, ecu_w, ecu_h, fill=ECU_FILL, stroke=ECU_STROKE, sw=1.5, rx=6)
    svg.text(ecu_x + ecu_w / 2, ecu_y + 18, ecu.name, size=14, anchor="middle", bold=True)
    svg.rect(ctrl_x, ctrl_y, ctrl_w, ctrl_h, fill=CTRL_FILL, stroke=CTRL_STROKE, sw=1.2, rx=5)
    svg.text(ctrl_x + ctrl_w / 2, ctrl_y + 18, ctrl.name, size=13, anchor="middle", bold=True)
    svg.rect(if_x, if_y, if_w, if_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
    svg.text(if_x + if_w / 2, if_y + 14, iface.name, size=11, anchor="middle", bold=True)

    inner_w = if_w - 40
    per_w = max(180, inner_w // max(1, n_vifaces) - 10)
    total_w = n_vifaces * per_w + (n_vifaces - 1) * 10
    start_x = if_x + (if_w - total_w) / 2
    for i, v in enumerate(iface.virtual_interfaces):
        vx = start_x + i * (per_w + 10)
        svg.viface(vx, if_y + 25, per_w, v.name, v.addresses, v.vlanid, with_oval=True)

    iface_cx = if_x + if_w / 2

    bottom_xs: list[float] = []
    if n_ext == 1:
        bottom_xs = [sw_x + sw_w / 2]
    elif n_ext > 1:
        chain_total = n_ext * chain_pitch
        chain_start = sw_x + (sw_w - chain_total) / 2 + chain_pitch / 2
        bottom_xs = [chain_start + i * chain_pitch for i in range(n_ext)]

    silicon_w, silicon_h = 130, 64
    if bottom_xs:
        silicon_cx = sum(bottom_xs) / len(bottom_xs)
    else:
        silicon_cx = sw_x + sw_w / 2
    if with_host:
        silicon_cx = max(silicon_cx, sw_x + 360)
    silicon_x = silicon_cx - silicon_w / 2
    silicon_y = sw_y + (sw_h - silicon_h) / 2 + 10

    svg.rect(sw_x, sw_y, sw_w, sw_h, fill=SWITCH_FILL, stroke=SWITCH_STROKE, sw=1.2, rx=4)
    svg.text(sw_x + 80, sw_y + 18, switch.name, size=13, anchor="middle", bold=True)

    sp_w, sp_h = 96, 22

    tp_cx = iface_cx
    tp_y = sw_y + 50
    svg.rect(tp_cx - sp_w / 2, tp_y, sp_w, sp_h, fill=SWITCH_PORT_FILL, stroke=SWITCH_PORT_STROKE, sw=1, rx=2)
    svg.text(tp_cx, tp_y + sp_h / 2 + 4, top_port.name, size=10, anchor="middle", bold=True)
    svg.line(tp_cx, tp_y + sp_h, tp_cx, silicon_y)
    _vlans_block(svg, switch, top_port, cx=tp_cx + 110, cy_center=tp_y + sp_h / 2)

    svg.rect(silicon_x, silicon_y, silicon_w, silicon_h, fill="#ffffff", stroke="#000000", sw=1, rx=4)
    svg.text(silicon_cx, silicon_y + silicon_h / 2 - 2, "switch", size=11, anchor="middle")
    svg.text(silicon_cx, silicon_y + silicon_h / 2 + 14, "silicon", size=11, anchor="middle")
    svg.text(silicon_cx, silicon_y - 4, "silicon_port0", size=9, anchor="middle")

    bp_y = silicon_y + silicon_h + 60
    for i, (bp, bx) in enumerate(zip(bottom_ports, bottom_xs)):
        svg.rect(bx - sp_w / 2, bp_y, sp_w, sp_h, fill=SWITCH_PORT_FILL, stroke=SWITCH_PORT_STROKE, sw=1, rx=2)
        svg.text(bx, bp_y + sp_h / 2 + 4, bp.name, size=10, anchor="middle", bold=True)
        svg.line(bx, bp_y, bx, silicon_y + silicon_h)
        silicon_edge_x = silicon_x if bx < silicon_cx else silicon_x + silicon_w
        svg.line(bx, silicon_y + silicon_h, silicon_edge_x, silicon_y + silicon_h)
        label_y = (silicon_y + silicon_h + bp_y) / 2
        anchor = "end" if bx < silicon_cx else "start"
        offset = -6 if anchor == "end" else 6
        svg.text(bx + offset, label_y + 3, f"silicon_port{i + 1}", size=9, anchor=anchor)
        oval_cx = bx + (-110 if bx < silicon_cx else 110)
        _vlans_block(svg, switch, bp, cx=oval_cx, cy_center=bp_y + sp_h / 2)

    if with_host and switch.host_controller is not None:
        hc = switch.host_controller
        hc_iface_w, hc_iface_h = 280, 110
        hc_iface_x = sw_x + 20
        hc_iface_y = sw_y + 80
        svg.rect(hc_iface_x, hc_iface_y, hc_iface_w, hc_iface_h, fill=IFACE_FILL, stroke=IFACE_STROKE, sw=1, rx=4)
        svg.text(hc_iface_x + hc_iface_w / 2, hc_iface_y + 14, hc.name, size=11, anchor="middle", bold=True)
        if hc.virtual_interfaces:
            v0 = hc.virtual_interfaces[0]
            svg.viface(hc_iface_x + 10, hc_iface_y + 25, hc_iface_w - 20, v0.name, v0.addresses, v0.vlanid, with_oval=True)

    svg.line(iface_cx, if_y + if_h, iface_cx, tp_y, dashed=True)
    svg.options(iface_cx + 12, (if_y + if_h + tp_y) / 2 + 4, mii_opts(iface.mii_config.type if iface.mii_config else None))

    port_y = height - 28 - 15
    for bp, bx in zip(bottom_ports, bottom_xs):
        ep = _port_for_switch_port(ecu, bp.name)
        if ep is None:
            continue
        _draw_ext_phy_chain(
            svg,
            line_x=bx,
            top_y=ecu_y + ecu_h,
            port_y=port_y,
            mii_type=bp.mii_config.type if bp.mii_config else None,
            mdi_config=ep.mdi_config,
            port_name=ep.name,
        )

    return svg.render()


# ============================================================================
# Dispatch
# ============================================================================


_PATTERN_RENDERERS = {
    "single_viface": render_single_viface,
    "multi_viface": render_multi_viface,
    "vms": render_vms,
    "multi_physical_iface": render_multi_physical_iface,
    "switch": lambda ecu: render_switch(ecu, with_host=False),
    "switch_with_host": lambda ecu: render_switch(ecu, with_host=True),
}


def build_svg(ecu: ECU) -> str:
    pattern = detect_pattern(ecu)
    renderer = _PATTERN_RENDERERS.get(pattern)
    if renderer is None:
        raise ValueError(f"Unsupported ECU pattern: {pattern}")
    return renderer(ecu)


def _is_ecu_dir(p: Path) -> bool:
    return p.is_dir() and (p / "ecu_metadata.flync.yaml").is_file()


def _render_one(ecu_path: Path, output: Path | None, *, output_dir: Path | None = None) -> Path:
    diagnostics = validate_external_node(ECU, ecu_path)
    if diagnostics.model is None:
        raise RuntimeError(
            f"failed to load ECU model from {ecu_path}; "
            f"run validate_workspace for details."
        )
    svg = build_svg(diagnostics.model)
    if output is not None:
        out = output
    elif output_dir is not None:
        out = output_dir / f"{diagnostics.model.name}.svg"
    else:
        out = ecu_path.parent / f"{diagnostics.model.name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="ECU directory or parent directory of ECU variants.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "In single-ECU mode: output SVG file path. "
            "In batch mode: output directory; each ECU is written to <output>/<ecu_name>.svg."
        ),
    )
    args = parser.parse_args()

    path: Path = args.path.resolve()
    if not path.is_dir():
        print(f"Error: {path} is not a directory.", file=sys.stderr)
        return 1

    if _is_ecu_dir(path):
        out = _render_one(path, args.output)
        print(f"Wrote {out}")
        return 0

    targets = sorted(p for p in path.iterdir() if _is_ecu_dir(p))
    if not targets:
        print(f"Error: {path} contains no ECU configurations.", file=sys.stderr)
        return 1
    output_dir: Path | None = args.output.resolve() if args.output is not None else None
    rc = 0
    for ecu_dir in targets:
        try:
            out = _render_one(ecu_dir, None, output_dir=output_dir)
            print(f"Wrote {out}")
        except Exception as ex:
            print(f"Error rendering {ecu_dir}: {ex}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
