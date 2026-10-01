# AGENTS.md — flync.model

`FLYNCModel` (`src/flync/model/flync_model.py`) is the root model aggregating all domains:

| Package | Domain | Description |
|---|---|---|
| `flync_4_app` | **Application** (experimental) | Applications consuming/providing SOME/IP services |
| `flync_4_bus` | **Bus** | CANBus and LINBus models |
| `flync_4_communication` | **Communication** | System-wide TCP profiles |
| `flync_4_diagnostics` | **Diagnostics** | DoIP/UDS: DoIP timings, UDS configurations (sessions, security access, supported services), DID/routine/DTC catalog, TCP/UDP socket deployment |
| `flync_4_ecu` | **ECU** | Full ECU detail: controllers, Ethernet/CAN/LIN interfaces, ports, sockets, PHY types (BASET...), MII, switches, VLANs, multicast |
| `flync_4_instrumentation` | **Instrumentation** (optional overlay) | Measurement points tapping buses/links for ASAM CMP / TECMP: Ethernet ports (p2p, id per direction), Ethernet shared-medium segments, CAN buses, LIN buses |
| `flync_4_metadata` | **Metadata** | System/ECU metadata: OEM, platform, versioning, HW/SW BOM |
| `flync_4_nm` | **Network Management** | State management groups, timing profiles for wake-up/sleep coordination |
| `flync_4_safety` | **Safety** | E2E communication protection |
| `flync_4_security` | **Security** | Firewall rules, MACsec encryption (integrity + confidentiality) |
| `flync_4_signal` | **Signal / PDU / Frame** | Full signal-to-frame stack: data types, PDUs (standard/multiplexed/container), CAN/LIN/CAN-FD frames, signal deployment, forwarding |
| `flync_4_someip` | **SOME/IP** | Open SOME/IP: service interfaces, events, methods, fields, eventgroups, UDP/TCP deployment, type system. For SOME/IP, only the Open SOME/IP Spec may be used (https://github.com/some-ip-com/open-someip-spec) |
| `flync_4_topology` | **Topology** | Physical/logical network topology: switch/port interconnections, ECU connections |
| `flync_4_tsn` | **TSN** | Time-Sensitive Networking: QoS shaping (CBS, ATS, HTB), traffic classes, PTP time sync |

When you add or change a model, update the Model Change History in `docs/source/model_change_history.rst`.
