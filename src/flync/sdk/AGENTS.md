# AGENTS.md — flync.sdk

`src/flync/sdk/` — developer-facing workspace management, helpers, and context:

| Subpackage | Contents | Description |
|---|---|---|
| `workspace/` | `FlyncWorkspace`, `document`, `ids`, `objects`, `source`, `_variants`, `variant_view` | Workspace management: load/save FLYNC configurations, document tracking, source resolution; `_variants`/`variant_view` resolve a workspace's `variability/` for the selected product variant before validation |
| `helpers/` | `debug`, `generation_helpers`, `nodes_helpers`, `validation_helpers`, `variant_helpers`, `debug_layers/` (`layer1_structure`, `layer2_yaml`, `layer3_4_5_workspace`, `runner`) | Utility functions for workspace validation, config generation, node traversal, variant tracing/comparison, and multi-layer debugging |
| `context/` | `diagnostics_result`, `node_info`, `workspace_config` | Configuration and diagnostic types for SDK and language server integration |
| `utils/` | `sdk_types`, `field_utils`, `model_dependencies`, `model_dumper`, `model_schema` | Shared type definitions, field introspection, dependency graph, model serialization, per-model JSON Schema export |
