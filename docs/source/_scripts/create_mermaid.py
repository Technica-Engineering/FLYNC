from pathlib import Path
from pydantic_mermaid import MermaidGenerator
import flync.model as base_model
from pydantic_mermaid.models import Relations
from flync.model.flync_4_ecu import *
from flync.model.flync_4_someip import *
from flync.model.flync_4_security import *
from flync.model.flync_4_topology import *
from flync.model.flync_4_tsn import *


EXPORT_DIR = Path(__file__).resolve().parent / ".." / "_static" / "mermaid"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def extract_mermaid_source(chart: str) -> str:
    """
    Removes ```mermaid fenced code block markers safely.
    Works even if formatting changes slightly.
    """
    lines = chart.strip().splitlines()

    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines)


def generate_mermaid_file(model, output_path: Path) -> None:
    generator = MermaidGenerator(model)
    generator.generate_allow_list("", Relations.Both)

    raw_chart = generator.generate_chart()
    cleaned_chart = extract_mermaid_source(raw_chart)

    output_path.write_text(cleaned_chart, encoding="utf-8")


targets = {
    "model.mmd": base_model.flync_model,
    "ecu.mmd": base_model.flync_4_ecu.ecu,
    "ecu_port.mmd": base_model.flync_4_ecu.port,
    "controller.mmd": base_model.flync_4_ecu.controller,
    "socket.mmd": base_model.flync_4_ecu.sockets,
    "switch.mmd": base_model.flync_4_ecu.switch,
    "ecu_topology.mmd": base_model.flync_4_ecu.internal_topology,
    "general_configs.mmd": base_model.flync_4_general_configuration.flync_general,
    "metadata.mmd": base_model.flync_4_metadata.metadata,
    "macsec.mmd": base_model.flync_4_security.macsec,
    "firewall.mmd": base_model.flync_4_security.firewall,
    "someip_service_iface.mmd": base_model.flync_4_someip.service_interface,
    "someip_deployment.mmd": base_model.flync_4_someip.deployment,
    "system_topology.mmd": base_model.flync_4_topology.system_topology,
    "qos.mmd": base_model.flync_4_tsn.qos,
    "timesync.mmd": base_model.flync_4_tsn.timesync,
}

for filename, model in targets.items():
    generate_mermaid_file(model, EXPORT_DIR / filename)
