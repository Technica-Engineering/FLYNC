# Variability examples

Two complete FLYNC workspaces that show the kinds of variability FLYNC supports. Each one is a full model
that validates for every declared variant. Read them in order; the second reuses what the first introduces.

In both, a product variant is a selection of ECUs and of the links between them. An ECU is the same in every
variant it is part of - an ECU that differs between products is a separate ECU - so variants differ in two
places only:

* the `variant_condition` at the root of an ECU's `ecu_metadata.flync.yaml` decides which variants the ECU is
  part of;
* a `variant_condition` on an entry of the system topology (`topology/ethernet_topology.flync.yaml`) decides
  which variants a connection, or a node of a multidrop segment, is part of.

| Workspace | Products | Kind of variability |
|---|---|---|
| [`01_optional_component`](01_optional_component/) | with / without park assist | One boolean feature. One ECU is optional, another one is replaced by an ECU with a port more, and one link is optional. |
| [`02_architecture_alternatives`](02_architecture_alternatives/) | 2 architectures × 2 compute generations | Structural alternatives. The ECUs of each architecture and generation, and the links between them, exist in alternatives. |

Run the same commands on either of them:

```bash
flync validate examples/flync_4_variability/02_architecture_alternatives                    # every declared variant
flync validate examples/flync_4_variability/02_architecture_alternatives --variant zonal_gen2
flync variants list examples/flync_4_variability/02_architecture_alternatives -f architecture -f compute_generation  # one row per variant
flync variants show zonal_gen2 examples/flync_4_variability/02_architecture_alternatives    # completed configuration, value sources, active qualifiers
flync variants trace examples/flync_4_variability/02_architecture_alternatives              # features -> workspace elements
flync variants diff domain_gen1 zonal_gen2 examples/flync_4_variability/02_architecture_alternatives
flync variants export zonal_gen2 examples/flync_4_variability/02_architecture_alternatives --out /tmp/zonal_gen2
```

The reference documentation of the variability model is the chapter *flync_4_variability* of the FLYNC
documentation.

## 01 - One optional component

The driver assistance network of a vehicle line sold with or without a park assist option. The option adds
the rear camera ECU and its link. The ADAS controller needs a port more for that link, so the park assist
product uses another ADAS controller; everything else is identical.

Look at:

* `variability/feature_model.flync.yaml` - a single boolean feature and the default variant.
* `variability/variants/` - two variants, one of which states no decision at all.
* `ecus/rear_camera/ecu_metadata.flync.yaml` - the optional ECU. A `variant_condition` at the root of the ECU's
  metadata document decides whether the whole folder is part of a product.
* `ecus/adas_controller/` and `ecus/adas_controller_pa/` - two alternative ECUs (`not park_assist` and
  `park_assist`). Only the second has the port and the interface for the rear camera; nothing inside either
  ECU varies. Both name their front port `adas_p1`.
* `topology/ethernet_topology.flync.yaml` - the link to the front camera fits both ADAS controllers and has no
  condition; the link to the rear camera carries `variant_condition: park_assist`. Without it, FLYNC's normal
  reference checks would report the base variant.

## 02 - Architecture alternatives

A body network that exists in two E/E architectures - a domain architecture with a body and a chassis domain
controller, and a zonal architecture with a front and a rear zone controller - on two hardware generations of
the central compute ECU. The products are the combinations that are built.

Look at:

* `variability/feature_model.flync.yaml` - two enumerated features, one of them ordered with a default
  (`compute_generation >= gen2`). Qualifiers over one enumerated feature (`domain`/`zonal`, `gen1`/`gen2`) are
  mutually exclusive by construction, which is what alternative ECUs need; a constraint ties the two features
  together.
* `variability/variants/` - `domain_gen2` extends `domain_gen1` and states only the generation that differs.
* `ecus/body_domain_controller/`, `ecus/chassis_domain_controller/`, `ecus/zone_controller_front/`,
  `ecus/zone_controller_rear/` - ECUs that exist in one architecture only; each declares it at the root of its
  `ecu_metadata.flync.yaml`.
* `ecus/central_compute_gen1/` and `ecus/central_compute_gen2/` - the two hardware generations of the central
  compute ECU are two ECUs whose conditions (`gen1`, `gen2`) exclude each other, so every product has exactly
  one of them. They differ inside (a safety controller and a four-port switch in the second generation) and
  are the same outside: both have the ports `cc_p1` and `cc_p2`, so the links to them are written once.
* `ecus/door_module_left/`, `ecus/door_module_right/` - ECUs that every product has, with no condition at all.
* `topology/ethernet_topology.flync.yaml` - one file for both architectures. Every link that only one
  architecture has carries its condition. The door segment (10BASE-T1S) is the same in both architectures;
  only its coordinator node changes, so the two coordinator nodes carry the conditions.
