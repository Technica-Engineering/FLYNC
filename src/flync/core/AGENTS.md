# AGENTS.md — flync.core

`src/flync/core/` — foundational base classes, annotations, datatypes, and utilities used by all domain models:

| Subpackage | Contents | Description |
|---|---|---|
| `base_models/` | `FLYNCBaseModel`, `DictInstances`/`ListInstances`/`BaseRegistry` | Pydantic v2 base model and collection management classes |
| `annotations/` | `External`, `Implied`, `Reference` | Field annotations controlling YAML load/resolve behavior |
| `datatypes/` | `BitRange`, `Ethertype`, `ValueRange`, `ValueTable`, IP/MAC address types | Low-level data types used across the library |
| `utils/` | `exceptions`, `exceptions_handling`, `base_utils`, `multicast/` (`multicast_paths`, `group_membership_handlers`) | Error factories and the validation policy, shared helpers, multicast path computation and group membership |
| `validators/` | `generic` (`validate_list_items_unique`, `none_to_empty_list`, `validate_or_remove`), `address`, `bit_ranges`, `connection_compatibility`, `forwarder`, `interface`, `state_management`, `traffic_classes` | Reusable validators referenced from `Annotated[...]` and `@model_validator` bodies |
| `version_migrators/` | `legacy_controller_check` | Helpers for FLYNC schema migrations across versions |

`flync.core.utils.exceptions` is where the error factories (`err_minor`/`err_major`/`err_fatal`/`warn`) and `compose_error_id` live. See the Error Catalog section in the root `AGENTS.md` for how to raise errors.
