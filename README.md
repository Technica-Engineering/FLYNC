<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/source/_static/images/flync_dark_mode.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/source/_static/images/flync_light_mode.svg">
    <img src="docs/source/_static/images/flync_light_mode.svg" alt="FLYNC Logo" width="360"/>
  </picture>
</p>

<h3 align="center">Configuration-as-Code for Automotive E/E Networks</h3>

<p align="center">
  <a href="https://github.com/Technica-Engineering/FLYNC/actions/workflows/push_and_pr.yaml"><img src="https://github.com/Technica-Engineering/FLYNC/actions/workflows/push_and_pr.yaml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Technica-Engineering/FLYNC/tree/python-coverage-comment-action-data"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Technica-Engineering/FLYNC/python-coverage-comment-action-data/endpoint.json" alt="Coverage"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Technica-Engineering/FLYNC" alt="License"></a>
  <a href="https://flync-language.com"><img src="https://img.shields.io/badge/docs-flync--language.com-blue" alt="Documentation"></a>
</p>

---

**FLYNC** (FLexible Yaml-based Network Configuration) is an open-source Python library that turns vehicle network configuration into clean, version-controlled code. It provides a single human-readable YAML schema and a comprehensive SDK to create, validate, and manipulate automotive E/E configurations programmatically.

By organizing system definitions in a central, version-controlled repository, FLYNC helps engineering teams manage complexity, enable reuse, and maintain consistency across domains.

## Key Features

- 🧩 **Layered Configuration Validation** — Models configurations across multiple abstraction layers for early inconsistency detection
- ⚙️ **Configuration-as-Code** — Git-native version control, CI/CD integration, full traceability and reproducibility
- 🚀 **Fast & Reliable** — Optimized Pydantic v2 engine handles large-scale configurations with high and predictable performance
- 👩‍💻 **Developer-Friendly** — Intuitive YAML syntax, rich CLI, Python SDK, and clear documentation
- 🌍 **Open Source & Collaborative** — Apache-2.0 licensed, community-driven development
- 🔌 **Extensible Converter Framework** — Pluggy-based plugin system for format conversions (JSON, YAML, DBC, and custom plugins)

## Domain Coverage

FLYNC models the full automotive E/E architecture across 12 domains:

| Domain | Description |
|---|---|
| **ECU** | Controllers, Ethernet/CAN/LIN interfaces, ports, PHY types (RGMII, SGMII, BASET…), switches, VLANs, multicast |
| **Signal / PDU / Frame** | Full signal-to-frame stack, data types, PDUs (standard/multiplexed/container), CAN/LIN/CAN-FD frames, forwarding |
| **SOME/IP** | AUTOSAR SOME/IP service interfaces, events, methods, fields, eventgroups, UDP/TCP deployment |
| **Topology** | Physical and logical network topology, switch/port interconnections, ECU connections |
| **TSN** | QoS shaping (CBS, ATS, HTB), traffic classes, PTP time synchronization |
| **Security** | Firewall rules, MACsec encryption (integrity + confidentiality) |
| **Network Management** | State management groups, timing profiles for wake-up/sleep coordination |
| **Metadata** | System/ECU metadata, OEM, platform, versioning, HW/SW BOM |
| **Communication** | System-wide TCP profiles, SOME/IP service-level settings |
| **Bus** | CAN bus and LIN bus definitions |
| **Application** | Applications consuming/providing SOME/IP services |
| **Safety** | E2E communication protection |

## Quick Start

### Installation

Requires **Python 3.12+** and [Poetry](https://python-poetry.org/).

```bash
git clone https://github.com/Technica-Engineering/FLYNC.git
cd FLYNC

python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install poetry
poetry install
```

> For detailed platform-specific instructions and advanced options, see the [Installation Guide](https://flync-language.com).

### Example: YAML Configuration

FLYNC workspaces organize vehicle configurations in modular `.flync.yaml` files:

```
my_project/
├── system_metadata.flync.yaml
├── topology/
│   └── system_topology.flync.yaml
└── ecus/
    ├── hpc/
    │   ├── ecu_metadata.flync.yaml
    │   ├── ports.flync.yaml
    │   └── topology.flync.yaml
    └── zonal_gateway/
        ├── ecu_metadata.flync.yaml
        ├── ports.flync.yaml
        └── topology.flync.yaml
```

**System metadata** (`system_metadata.flync.yaml`):

```yaml
release:
  version_schema: semver
  version: 1.2.1
author: System_Architect
compatible_flync_version:
  version_schema: semver
  version: 0.11.0
oem: OEM_example
platform: Arch1
```

**ECU port definition** (`ecus/hpc/ports.flync.yaml`):

```yaml
ports:
  - name: hpc1_p1
    mdi_config:
      mode: base_t1
      speed: 1000
      duplex: full
      role: master
      autonegotiation: false
    mii_config:
      type: sgmii
      speed: 1000
      mode: phy
```

**System topology** (`topology/system_topology.flync.yaml`):

```yaml
connections:
  - type: ecu_port_to_ecu_port
    id: conn1
    ecu1_port: hpc1_p1
    ecu2_port: z1_p1
  - type: ecu_port_to_ecu_port
    id: conn2
    ecu1_port: hpc1_p2
    ecu2_port: zgw_p1
```

> Explore the full example at [`examples/flync_example/`](examples/flync_example/).

### Example: Python SDK

```python
from flync.sdk.workspace import FLYNCWorkspace

# Load and validate a workspace
workspace = FLYNCWorkspace(name="my_project")
workspace.ingest_folder("path/to/my_project")
workspace.run_analysis()

# Access the validated model
model = workspace.model
for ecu in model.ecus:
    print(f"ECU: {ecu.name}, Ports: {len(ecu.ports)}")
```

### Example: CLI

```bash
# Validate a workspace
flync validate path/to/my_project

# Show ECU / controller / interface information
flync info path/to/my_project

# Generate a PlantUML system diagram
flync generate-system-uml path/to/my_project

# Show SOME/IP service deployments
flync service-info path/to/my_project

# Show VLAN and multicast group information
flync vlan-info path/to/my_project
```

## CLI Tools

FLYNC ships with five CLI entry points:

| Command | Description |
|---|---|
| `flync` | Main CLI — validate workspaces, inspect ECUs, generate UML diagrams, query services and VLANs |
| `flync-converter` | Convert between formats (FLYNC ↔ JSON ↔ YAML ↔ DBC and custom plugins) |
| `flync-converter-interactive` | Interactive terminal UI for conversions (Textual) |
| `flync-converter-gui` | Desktop GUI for conversions (PySide6) |
| `puml-to-html` | Convert PlantUML diagrams to HTML |

## Architecture

```
src/
├── flync/                  # Core library
│   ├── core/               #   Base models (Pydantic v2), annotations, datatypes, validators
│   ├── model/              #   12 domain models (ECU, SOME/IP, TSN, topology, …)
│   └── sdk/                #   Workspace management, validation helpers, model serialization
├── flync_cli/              # Typer + Rich CLI application (validate, info, UML, …)
└── flync_converter/        # Pluggy-based converter framework (CLI, TUI, GUI)
```

## Traditional Approach vs. FLYNC

| | Traditional Approach | With FLYNC |
|---|---|---|
| Configuration storage | Multiple formats & scattered files | One unified YAML-based model |
| Version control | Partial / inconsistent | Git-native |
| CI/CD integration | Rare / custom scripts | Built-in workflow friendly |
| Cross-team collaboration | Siloed | Shared source of truth |

## Development

### Setup

```bash
# Full developer environment (core + test + linting)
poetry install

# Add documentation dependencies
poetry install --with docs

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
poetry run pytest                           # Full suite (parallel, with coverage)
poetry run pytest tests/unit_test/          # Unit tests only
poetry run pytest -k "test_ecu"             # Filter by keyword
poetry run pytest --no-header -v --tb=short # Verbose, short tracebacks
```

### Code Quality

```bash
# Run all checks (black, isort, flake8, mypy)
bash scripts/helpers/local_checkers.sh

# Auto-fix formatting issues
bash scripts/helpers/local_autoformat.sh

# Run pre-commit on all files
pre-commit run --all-files
```

### Validate Bundled Examples

```bash
poetry run python scripts/ci/validate_examples.py
```

### Build Documentation

```bash
cd docs && make html
```

## Target Users

FLYNC is designed for:

- **E/E architecture teams** — model and validate vehicle network configurations
- **Network and platform engineers** — define ECU topologies, SOME/IP services, TSN policies
- **SDV DevOps and integration teams** — integrate configuration validation into CI/CD pipelines
- **Validation and test engineers** — detect inconsistencies early across abstraction layers
- **Toolchain and automation specialists** — extend FLYNC with custom converter plugins

## Contributing

We welcome contributions! See **[CONTRIBUTING.md](CONTRIBUTING.md)** for detailed guidelines on:

- Coding standards and Pydantic model conventions
- Branch naming and commit message format
- PR workflow and review process
- Testing requirements

**Quick links:**

- 🐛 [Report a bug](https://github.com/Technica-Engineering/FLYNC/issues/new?template=bug_report.md)
- 💡 [Request a feature](https://github.com/Technica-Engineering/FLYNC/issues/new?template=feature_request.md)
- 🔒 Security issues → [flync@technica-engineering.de](mailto:flync@technica-engineering.de)

## Resources

| | |
|---|---|
| 🌐 Website | [flync-language.com](https://flync-language.com) |
| 📖 Documentation | [GitHub / Docs](https://github.com/Technica-Engineering/FLYNC) |
| 🐛 Issue Tracker | [GitHub Issues](https://github.com/Technica-Engineering/FLYNC/issues) |
| 📧 Contact | [flync@technica-engineering.de](mailto:flync@technica-engineering.de) |

## License

[Apache License 2.0](LICENSE) — Copyright 2026 [Technica Engineering GmbH](https://technica-engineering.de)
