.. _variability:

*******************
flync_4_variability
*******************

The ``flync_4_variability`` module adds **product-line variant management** to FLYNC. One workspace holds
every variant of a system instead of one branch or one copy per variant.

FLYNC supports two kinds of variability:

* **Optional components** - a boolean feature decides whether an ECU, and the links to it, are part of a
  product. Example: a vehicle sold with or without park assist.
* **Architecture alternatives** - enumerated features select one of several mutually exclusive ways to
  build the same system. Example: a body network in a domain or a zonal E/E architecture, on two hardware
  generations of its central compute ECU.

In both, a product variant is a **selection of ECUs and of the links between them**. An ECU is the same in
every variant it is part of: an ECU that differs between products - one port more, another controller,
other software - is a separate ECU. So variants differ in two places only: the ``ecu_metadata`` of an ECU
says which variants the ECU is part of, and the **system topology** (``topology/``) says how the ECUs of
each variant are connected.

Variant management in FLYNC covers the path from a product decision to the network elements that realize
it:

* a **feature model**: a flat list of boolean and enumerated features, the constraints between them and
  named qualifiers;
* **variants** that only state their own decisions, inherit the rest from another variant with ``extends``
  and take a default for anything left open;
* **variation points** in the workspace, resolved into one ordinary, fully validated model per variant;
* **analyses** that trace each feature to the workspace elements it decides, and compare two variants
  element by element.

.. note::
   "Variant" on this page always means a **product variant**: one concrete configuration of the product
   line. It is unrelated to the *variant types* of a discriminated union
   (:doc:`../../development/structure_and_polymorphism`) and to the ECU layout patterns in
   ``examples/ecu_variants``.

At a glance
###########

.. code-block:: text

   my_workspace/
   ├── variability/
   │   ├── feature_model.flync.yaml      # what can vary, and the constraints between the features
   │   └── variants/
   │       ├── base.flync.yaml           # one file per product variant: a set of feature values
   │       └── park_assist.flync.yaml
   ├── ecus/
   │   ├── adas_controller/              # ecu_metadata starts with variant_condition: not park_assist
   │   ├── adas_controller_pa/           # ecu_metadata starts with variant_condition: park_assist
   │   ├── front_camera/                 # no condition: part of every variant
   │   └── rear_camera/                  # ecu_metadata starts with variant_condition: park_assist
   └── topology/
       └── ethernet_topology.flync.yaml  # a connection may carry variant_condition

.. code-block:: yaml

   # variability/feature_model.flync.yaml
   features:
     - name: park_assist
       type: boolean
     - name: architecture
       type: enumeration
       values: [domain, zonal]

   # variability/variants/park_assist.flync.yaml
   features:
     park_assist: true
     architecture: zonal

.. code-block:: bash

   flync validate my_workspace                         # validates every declared variant
   flync validate my_workspace --variant park_assist   # validates one variant

A workspace without a ``variability/`` folder describes a single configuration and loads exactly as before.
Variant management is entirely opt-in.

New to variant management? Start with :ref:`variability_step_by_step`, which walks through the two
supported use cases. The rest of this page is the reference.

.. _variability_step_by_step:

Step by step: the two use cases
###############################

This section is a tutorial. It shows both kinds of variability FLYNC supports, and each follows the same
four steps:

1. **Declare what can vary** in ``variability/feature_model.flync.yaml`` - the features.
2. **Declare the products** in ``variability/variants/<name>.flync.yaml`` - one file per variant, holding
   only the decisions that variant makes.
3. **Mark what varies in the workspace** with a ``variant_condition``: at the root of the ``ecu_metadata``
   of every ECU that only some products have, and on every entry of the system topology that only some
   products have.
4. **Check it** with ``flync validate``, which validates every declared variant, and ``flync variants``.

Each use case is a complete workspace in ``examples/flync_4_variability/`` that you can copy, run and
change. The snippets below are taken from those workspaces. If you only need one optional component, stop
after the first one; the second never changes what the first introduced.

.. list-table::
   :header-rows: 1
   :widths: 10 30 60

   * - Use case
     - Products differ in
     - What you learn
   * - :ref:`1 <variability_level_1>`
     - one option (with / without park assist)
     - a boolean feature, an optional ECU, an ECU that the option replaces by another one, a conditional
       link
   * - :ref:`2 <variability_level_2>`
     - two architectures and two hardware generations
     - enumerated and ordered features, constraints, qualifiers, variants that extend each other, and
       alternative ECUs with mutually exclusive conditions

.. _variability_level_1:

Use case 1 - One optional component
===================================

*Workspace:* ``examples/flync_4_variability/01_optional_component``

A driver-assistance network is sold with or without a park assist option. The option adds a rear camera
ECU and its link to the ADAS controller. The ADAS controller needs a port more for that link, so the park
assist product uses another ADAS controller; everything else is the same.

**Step 1 - declare the feature.** One boolean feature is enough:

.. literalinclude:: ../../../../examples/flync_4_variability/01_optional_component/variability/feature_model.flync.yaml
   :language: yaml
   :caption: variability/feature_model.flync.yaml

**Step 2 - declare the two products.** A variant only states its own decisions. A boolean feature that is
not decided is ``false``, so the base product needs no decision at all:

.. literalinclude:: ../../../../examples/flync_4_variability/01_optional_component/variability/variants/base.flync.yaml
   :language: yaml
   :caption: variability/variants/base.flync.yaml

.. literalinclude:: ../../../../examples/flync_4_variability/01_optional_component/variability/variants/park_assist.flync.yaml
   :language: yaml
   :caption: variability/variants/park_assist.flync.yaml

**Step 3 - mark what varies.** An ECU is part of a product when the ``variant_condition`` at the root of
its ``ecu_metadata.flync.yaml`` holds, or when it has none. The rear camera exists only with park assist,
so the feature goes on the first line of its metadata:

.. code-block:: yaml

   # ecus/rear_camera/ecu_metadata.flync.yaml
   variant_condition: park_assist      # the whole ECU, only with park assist
   author: Dev
   ...

The ADAS controller of the park assist product has a second port and a second interface, for the rear
camera. An ECU never varies inside - there is no condition on a port or an interface - so that is a
second ECU, ``adas_controller_pa``. The two ADAS controllers are *alternatives*: their conditions exclude
each other, so every product has exactly one of them.

.. code-block:: yaml

   # ecus/adas_controller/ecu_metadata.flync.yaml - one port
   variant_condition: not park_assist
   ...

   # ecus/adas_controller_pa/ecu_metadata.flync.yaml - two ports
   variant_condition: park_assist
   ...

The front camera has no condition: it is part of every product. The folder tree stays an ordinary FLYNC
tree, and every ECU in it is an ordinary, complete ECU that validates on its own.

Last, the **system topology** wires the ECUs of each product. A connection that only some products have
carries the same condition as the ECU it leads to. Both ADAS controllers name their front port
``adas_p1``, so the link to the front camera fits either of them and needs no condition:

.. literalinclude:: ../../../../examples/flync_4_variability/01_optional_component/topology/ethernet_topology.flync.yaml
   :language: yaml
   :caption: topology/ethernet_topology.flync.yaml

Forget the condition on ``link_rear_camera`` and FLYNC reports it in the base product: the link refers to
ports that none of its ECUs has. No extra rule is needed; the normal reference checks keep the variants
consistent.

**Step 4 - check it.**

.. code-block:: bash

   flync validate examples/flync_4_variability/01_optional_component          # both variants
   flync variants list examples/flync_4_variability/01_optional_component -f park_assist   # one row per variant, with its park_assist value
   flync info ecus examples/flync_4_variability/01_optional_component --variant park_assist

.. _variability_level_2:

Use case 2 - Architecture alternatives
======================================

*Workspace:* ``examples/flync_4_variability/02_architecture_alternatives``

A body network exists in a domain architecture and a zonal architecture, on two hardware generations of
the central compute ECU. Here the products are not one network with or without an option: they are
**built differently**. The domain architecture has a body and a chassis domain controller, the zonal
architecture a front and a rear zone controller, and the two compute generations differ inside. Still,
every product is only a selection of ECUs and of the links between them.

**Step 1 - declare the features.** A decision with more than two outcomes is an *enumeration*. Mark it
``ordered`` when conditions need "gen2 or later". A ``default`` saves every variant a decision. A
``constraint`` states which combinations the product line does not offer. **Qualifiers** give a condition
a name; qualifiers over one enumerated feature are mutually exclusive by construction, which is exactly
what the alternatives of an element need:

.. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/feature_model.flync.yaml
   :language: yaml
   :caption: variability/feature_model.flync.yaml

**Step 2 - declare the products.** ``domain_gen1`` relies on the default of ``compute_generation``.
``domain_gen2`` uses ``extends`` to inherit the decisions of ``domain_gen1`` and states only what differs.
``zonal_gen2`` has to decide the generation, because the constraint forbids zonal on gen1:

.. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/domain_gen1.flync.yaml
   :language: yaml
   :caption: variability/variants/domain_gen1.flync.yaml

.. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/domain_gen2.flync.yaml
   :language: yaml
   :caption: variability/variants/domain_gen2.flync.yaml - extends domain_gen1

.. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/zonal_gen2.flync.yaml
   :language: yaml
   :caption: variability/variants/zonal_gen2.flync.yaml

**Step 3 - mark what varies.** Every ECU that exists in one architecture or generation only says so at the
root of its ``ecu_metadata``. The ECUs every product has carry no condition:

.. code-block:: text

   ecus/
   ├── body_domain_controller/        # ecu_metadata: variant_condition: domain
   ├── chassis_domain_controller/     # ecu_metadata: variant_condition: domain
   ├── zone_controller_front/         # ecu_metadata: variant_condition: zonal
   ├── zone_controller_rear/          # ecu_metadata: variant_condition: zonal
   ├── central_compute_gen1/          # ecu_metadata: variant_condition: gen1 - one controller, a three-port switch
   ├── central_compute_gen2/          # ecu_metadata: variant_condition: gen2 - a safety controller, a four-port switch
   ├── door_module_left/              # no condition: part of every product
   └── door_module_right/             # no condition: part of every product
   topology/
   └── ethernet_topology.flync.yaml   # every connection that only one architecture has carries its condition

The two generations of the central compute ECU are two ECUs. FLYNC does not know that
``central_compute_gen1`` and ``central_compute_gen2`` stand for "the central compute ECU"; it only knows
that no product contains both, because their conditions exclude each other. Both have the external ports
``cc_p1`` and ``cc_p2``, so the system topology does not care which one is present.

The **system topology** holds the rest. One file describes both architectures: every link carries the
architecture it belongs to. The door modules are on the same 10BASE-T1S segment in both architectures and
only the coordinator of the segment (node 0) changes, so the segment itself has no condition and its two
coordinator nodes do:

.. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/topology/ethernet_topology.flync.yaml
   :language: yaml
   :caption: topology/ethernet_topology.flync.yaml

Nothing else in the workspace varies: the PDUs the door modules send, and every other definition, are the
same in every product.

**Step 4 - check it.**

.. code-block:: bash

   flync validate examples/flync_4_variability/02_architecture_alternatives
   flync variants show domain_gen2 examples/flync_4_variability/02_architecture_alternatives   # every value and where it comes from
   flync variants diff domain_gen1 zonal_gen2 examples/flync_4_variability/02_architecture_alternatives
   flync variants check examples/flync_4_variability/02_architecture_alternatives   # every variation point, all variants at once

``flync variants show`` prints the completed configuration: for ``domain_gen2`` it shows ``architecture``
as ``inherited`` from ``domain_gen1``, ``compute_generation`` as ``assigned`` in the variant itself, and
``domain`` and ``gen2`` as the active qualifiers. ``flync variants diff`` lists the features that differ and
then every workspace element that only one of the two variants has, including the alternative that each
one uses.

Adding a variant to an existing workspace
=========================================

Once the feature model exists, a new product is one file:

1. Create ``variability/variants/<name>.flync.yaml``. The file name is the variant name.
2. Pick the closest existing variant and name it in ``extends``; state only the decisions that differ.
3. Run ``flync validate <workspace> --variant <name>``. Three kinds of finding can appear:

   * ``FLYNC-VAR-...`` on the variant itself: an undeclared feature or value, a broken constraint, or an
     enumerated feature without a value and without a default. Fix the variant, or the feature model.
   * a reference finding in exactly this variant: a connection of the system topology leads to an ECU the
     new combination of features leaves out. Add the missing ``variant_condition`` to the connection.
   * a warning that a condition is never true: a variation point no declared variant uses.

4. Run ``flync variants diff <closest> <name> <workspace>`` and check that the differences are the ones
   you intended.

Adding a feature to an existing workspace
=========================================

1. Add the feature to ``variability/feature_model.flync.yaml``. Give it a ``default`` or make it boolean,
   so that the existing variants stay complete without a change.
2. Declare a qualifier when a condition is repeated, or when the technical consequence has a better name
   than the decision (``zonal: architecture == zonal``).
3. Mark what varies: a ``variant_condition`` at the root of the ``ecu_metadata`` of every ECU the feature
   adds or removes, a separate ECU for every ECU the feature changes, and a ``variant_condition`` on every
   entry of the system topology that leads to one of them.
4. Decide the feature in the variants that need it, then run ``flync validate <workspace>`` for every
   variant.

Concepts
########

Why variant management
======================

Most products are not built once. They are built as a **product line**: a family of similar products that
share most of their design and differ in a controlled set of characteristics. A network architecture,
for example, might come with or without an optional ECU, in two E/E architectures, across two hardware
generations.

There are two common ways to handle this without variant management, and both scale badly:

* **One copy (or branch) per variant.** Every fix has to be repeated in every copy, the copies drift
  apart, and nobody can tell at a glance what actually differs between two variants.
* **One "superset" configuration with informal comments.** Tools cannot tell which parts belong to
  which product, so nothing can be validated per product.

FLYNC's variant management keeps a single source of truth and makes the differences explicit and
machine-checkable. Common parts are written once. Every difference is marked with a condition over named
features, and every product variant is validated as if it had been written on its own.

The 150 % model and the 100 % model
===================================

A workspace with variant management is a **150 % model**: it holds everything that any variant needs, plus
the information about which part belongs to which variant. Resolving it for one variant yields a
**100 % model**: an ordinary :class:`~flync.model.flync_model.FLYNCModel` that describes exactly that one
product configuration and goes through every FLYNC validator unchanged.

.. mermaid::

   flowchart LR
     subgraph PS["Problem space: what varies"]
       FM["Feature model<br/>features, constraints, qualifiers"]
       V["Product variants<br/>decisions"]
     end
     subgraph SS["Solution space: how it varies"]
       W["150 % workspace<br/>with variation points"]
     end
     V --> C["Configuration<br/>assigned, inherited, default"]
     FM --> C
     C --> R["Resolver<br/>(per variant)"]
     W --> R
     R --> M1["100 % model<br/>variant A"]
     R --> M2["100 % model<br/>variant B"]
     R --> M3["..."]

Product-line engineering separates two concerns, and FLYNC keeps them apart in the same way:

* The **problem space** says *what* can vary and which combinations are allowed. In FLYNC this is the
  ``variability/`` folder (the feature model and the product variants). It uses no network
  terminology at all.
* The **solution space** says *how* each difference shows up in the artifacts. In FLYNC this is the rest of
  the workspace, where **variation points** say which ECUs and which links belong to which variant.

Because the two are separate, the network model never needs to know what an "architecture" or a
"park assist option" is.

Glossary
========

The FLYNC names follow general product-line engineering usage (e.g. ISO/IEC 26580 and the feature-model
literature). The table gives the general term next to the FLYNC name.

.. list-table::
   :header-rows: 1
   :widths: 22 22 56

   * - FLYNC term
     - General term
     - Meaning
   * - product line
     - product line, product family
     - A set of products that share a common base and differ in a managed way.
   * - 150 % workspace
     - superset model, configurable model
     - The workspace that contains every variant and the variation points.
   * - 100 % model
     - derived product, resolved configuration
     - One variant after resolution: the 150 % workspace with every variation point decided.
   * - feature
     - feature
     - A characteristic in which products of the line differ (an optional component, an architecture, a
       hardware generation).
   * - feature model
     - feature model, feature catalog
     - The list of features, their possible values, the constraints between them, and the qualifiers.
   * - boolean feature
     - optional feature
     - A feature that a product either has or does not have.
   * - enumerated feature
     - alternative group, feature with a value set
     - A feature for which every product picks exactly one value from a declared list.
   * - ordered feature
     - feature with an ordered domain
     - An enumerated feature whose values have a meaningful order (generations, releases, years).
   * - ``category``
     - feature kind, viewpoint
     - What a feature stands for: product, context, requirement, solution, or element.
   * - constraint
     - cross-tree constraint, dependency
     - A rule every valid product must satisfy, e.g. "zonal needs gen2 or later".
   * - value source
     - decision origin
     - Where the value of a feature in a variant comes from: assigned, inherited, or default.
   * - product variant
     - product, configuration, bill-of-features
     - A named set of decisions about features; completed, it describes one concrete product.
   * - ``extends``
     - configuration inheritance
     - A variant that starts from another variant and only states what differs.
   * - variant condition
     - presence condition
     - A boolean expression over the features that decides whether something is part of a variant.
   * - qualifier
     - named presence condition
     - A reusable, named condition, used by name wherever a condition is written.
   * - alternative ECUs
     - alternative components, mutually exclusive variants of a component
     - Two or more ECUs whose conditions exclude each other, so that every product has at most one of them.
   * - variation point
     - variation point
     - A place in the artifacts where variants differ: the root of an ECU's metadata, or an entry of the
       system topology.
   * - attributes
     - feature metadata
     - Free-form, domain-specific data on a feature (an option code, a cost class, ...).
   * - resolution
     - derivation, product instantiation
     - Producing the 100 % model of one variant from the 150 % workspace.

How it works
============

1. ``variability/feature_model.flync.yaml`` declares the **features** the products are configured by,
   the constraints between them and named qualifiers.
2. ``variability/variants/<name>.flync.yaml`` declares each **product variant** by its own decisions.
3. Each variant is **completed**: decisions it inherits through ``extends`` and the defaults of the
   features give every other feature its value. A missing decision is reported.
4. The rest of the workspace marks what varies with **variation points**, written as conditions over
   the features: the ``ecu_metadata`` of an ECU says which variants the ECU is part of, and an entry of
   the system topology which variants the connection is part of. An ECU never varies inside.
5. When the workspace is loaded for a variant, the loader resolves every variation point *before*
   validation. The models never see a variation point, and the result is validated like any other
   workspace.
6. ``flync validate`` validates **every declared variant**. A finding is reported once, together with
   the list of variants it occurs in.

The set of declared variants is **closed**. FLYNC validates the products you declare, not every
combination the feature model would allow. A product line with a dozen features allows thousands of
combinations, most of which are never built; validating the declared ones keeps the result meaningful
and the run time predictable.

The ``variability/`` folder
###########################

.. code-block:: text

   📂 variability
   ├── 📄❗ feature_model.flync.yaml     # mandatory when the folder exists
   └── 📂 variants
       ├── 📄 <variant name>.flync.yaml   # at least one
       └── 📄 ...

* The folder names ``variability`` and ``variants`` and the file name ``feature_model`` are fixed.
* The name of a variant is its file name, without ``.flync.yaml``.
* Nothing inside ``variability/`` may itself use variation points. The variability model has to be the
  same for every variant.

The feature model
#################

The feature model lists the features, the ``constraints`` between them, the named qualifiers, and the
default variant.

.. admonition:: Expand for the example feature model - 📄 ``variability/feature_model.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/feature_model.flync.yaml
      :language: yaml

Features
========

Each entry of ``features`` declares one feature. The features form a flat list.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Key
     - Meaning
   * - ``name``
     - Identifier used in conditions and in variant files. Letters, digits, and underscores; it must not
       start with a digit, be a Python keyword, or be one of the reserved names ``true`` and ``false``.
       Features and qualifiers share one namespace.
   * - ``description``
     - Free text. Strongly recommended: the feature model is the reference for everyone who reads the
       variants.
   * - ``type``
     - ``boolean`` or ``enumeration``. Optional: when omitted, it is inferred (a feature with ``values`` is
       an enumeration, a feature without is boolean). When given, it must agree with ``values``.
   * - ``category``
     - What the feature stands for: ``product``, ``context``, ``requirement``, ``solution``, or ``element``.
       See :ref:`variability_categories`. Optional; it documents the feature and does not change how it is
       configured.
   * - ``values``
     - The possible values of an enumerated feature: at least one, all unique, none empty. Numbers are read
       as text (``values: [2026, 2027]`` declares ``"2026"`` and ``"2027"``).
   * - ``ordered``
     - ``true`` makes the order of ``values`` meaningful and allows ``<``, ``<=``, ``>`` and ``>=`` in
       conditions. Only for enumerated features.
   * - ``default``
     - Value a feature gets when neither the variant nor a variant it extends decides it. ``true``/``false``
       for a boolean feature, one of ``values`` for an enumerated one.
   * - ``attributes``
     - Free-form key/value data (see :ref:`variability_attributes`).

Boolean features
----------------

A boolean feature is a component or capability that a product either has or does not have. It is
``false`` in a variant unless the variant (or its ``default``) enables it. This is the feature of an
**optional component**.

.. code-block:: yaml

   - name: park_assist
     description: Park assist with a rear camera.
     type: boolean

Enumerated features
-------------------

An enumerated feature has a fixed list of values, and every variant selects exactly one of them. Use it
for mutually exclusive choices: an E/E architecture, a hardware platform. This is the feature of
**architecture alternatives**. A variant must assign it unless it has a ``default``.

.. code-block:: yaml

   - name: architecture
     type: enumeration
     values: [domain, zonal]

Ordered features
----------------

An ordered feature is an enumerated feature whose values form a sequence. The declaration order *is* the
order: the comparison uses the position in ``values``, not the text. Use it for anything that moves
forward over the product's life: hardware generations, revisions, releases.

.. code-block:: yaml

   - name: compute_generation
     type: enumeration
     values: [gen1, gen2]
     ordered: true
     default: gen1

.. code-block:: yaml

   # present from gen2 onward
   variant_condition: compute_generation >= gen2

Choosing the kind of feature
----------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - The products differ in ...
     - Model it as
   * - whether a component is fitted
     - a boolean feature
   * - which one of several mutually exclusive architectures or solutions is used
     - an enumerated feature
   * - a step in a sequence (generation, revision, release)
     - an ordered enumerated feature
   * - several independent options that can be combined freely
     - one boolean feature per option, not one enumeration of all combinations

.. tip::
   A feature should describe the **product**, not the implementation. ``park_assist`` is a good feature;
   ``adas_controller_port_2_enabled`` is not. The mapping from features to network elements belongs in the
   variation points. That keeps the feature model readable for product management, and stable when the
   implementation changes.

.. _variability_categories:

Categories
==========

``category`` documents what a feature stands for. It never changes how a variant is configured, but it
makes the feature model readable and is shown by ``flync variants trace``.

.. list-table::
   :header-rows: 1
   :widths: 16 44 40

   * - Category
     - Stands for
     - Example
   * - ``product``
     - a capability a customer or product manager chooses
     - an option such as park assist, an edition
   * - ``context``
     - a condition outside the system
     - a sales market, a customer, a legal frame
   * - ``requirement``
     - a high-level requirement that only some products have
     - "redundant brake actuation"
   * - ``solution``
     - one technical solution that fulfills a requirement
     - a domain or a zonal architecture
   * - ``element``
     - a technical element a solution is made of, realized in the workspace
     - a hardware generation of an ECU

.. _variability_constraints:

Constraints
===========

``constraints`` hold the rules every declared variant must satisfy; a variant that breaks one is
reported, and the variability model is not loaded.

.. code-block:: yaml

   constraints:
     - expression: architecture != zonal or compute_generation >= gen2
       description: The zonal architecture needs the second compute generation.  # implication between values
     - expression: not (option_a and option_b)
       description: Options A and B share a connector.                            # mutual exclusion

The ``description`` is shown in the error message when a variant breaks the rule, so write it for the
person who reads that message.

Common patterns:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Rule
     - Expression
   * - A requires B
     - ``not A or B``
   * - A excludes B
     - ``not (A and B)``
   * - exactly one of A, B, C
     - one enumerated feature with ``values: [a, b, c]`` instead of three boolean features
   * - at least one of A, B, C
     - ``A or B or C``
   * - value X of E requires A
     - ``E != X or A``

Constraints only check; they never set a value. A variant has to state every decision a constraint
needs that its default does not already give.

Qualifiers
==========

A qualifier is a named condition. It makes long conditions readable, keeps a repeated condition in one
place, and gives the alternatives of an element a short name:

.. code-block:: yaml

   qualifiers:
     domain: architecture == domain
     zonal: architecture == zonal
     gen2: compute_generation == gen2
     zonal_gen2: zonal and gen2           # qualifiers can use other qualifiers

Qualifiers over one enumerated feature are mutually exclusive by construction, so ``domain`` and ``zonal``
can never both hold. That is what two elements that are alternatives of each other need.

Qualifiers share one namespace with features. A qualifier must not refer to itself, directly or through
other qualifiers.

``default_variant``
===================

The variant that is loaded when none is selected explicitly, e.g. by an editor or by
``FLYNCWorkspace.load_workspace`` without ``variant=``. Without a ``default_variant``, loading a variant
workspace without selecting a variant is an error. ``flync validate`` without ``--variant`` validates every
variant and does not need a default.

.. _variability_attributes:

Attributes
==========

Features can carry ``attributes``: free-form key/value pairs that FLYNC stores but does not interpret.
They add the data your organization needs without a change to FLYNC's schema, e.g. option codes or cost
classes. Values may be text, numbers, or booleans.

.. code-block:: yaml

   - name: park_assist
     type: boolean
     attributes:
       option_code: PA01

Generators read them from the active variant: ``model.active_variant.feature_attributes`` holds the
attributes of every feature that declares any.

.. note::
   Attributes are data *about* features. They cannot be used in conditions; anything that decides what is
   part of a variant has to be a feature.

Product variants
################

Each file in ``variability/variants/`` declares one product variant. The variant name is the file name.

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Key
     - Meaning
   * - ``description``
     - Free text describing the product.
   * - ``extends``
     - Name of another variant whose decisions this variant inherits.
   * - ``features``
     - The decisions of the variant: ``true``/``false`` for a boolean feature, one of the declared values
       for an enumerated feature. Features it leaves undecided are completed (see below).

.. admonition:: Expand for the example variants - 📄 ``variability/variants/``
   :collapsible: closed

   .. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/domain_gen1.flync.yaml
      :language: yaml
      :caption: domain_gen1.flync.yaml

   .. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/domain_gen2.flync.yaml
      :language: yaml
      :caption: domain_gen2.flync.yaml

   .. literalinclude:: ../../../../examples/flync_4_variability/02_architecture_alternatives/variability/variants/zonal_gen2.flync.yaml
      :language: yaml
      :caption: zonal_gen2.flync.yaml

.. _variability_completion:

How a variant is completed
==========================

A variant states only its own decisions. FLYNC completes them into a value for every feature. For each
feature, the first of these that gives a value wins:

1. **Assigned** - the variant's own ``features``.
2. **Inherited** - the decisions of the variants it ``extends``, the nearer variant winning.
3. **Default** - the feature's ``default``; a boolean feature without one is ``false``.

An enumerated feature that gets no value this way - no decision and no default - is reported as an open
decision of the variant.

Every value remembers where it comes from:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Source
     - Meaning
   * - ``assigned``
     - Written in the variant itself.
   * - ``inherited``
     - Written in a variant it ``extends``.
   * - ``default``
     - The feature's default, or ``false`` for an undecided boolean feature.

``flync variants show <variant>`` prints every feature with its value, its source, and its type, and the
qualifiers that are active:

.. code-block:: text

   ┌────────────────────┬────────┬───────────┬─────────────┐
   │ Feature            │ Value  │ Source    │ Type        │
   ├────────────────────┼────────┼───────────┼─────────────┤
   │ architecture       │ domain │ inherited │ enumeration │
   │ compute_generation │ gen2   │ assigned  │ enumeration │
   └────────────────────┴────────┴───────────┴─────────────┘
   active qualifiers: domain, gen2

Inheritance with ``extends``
============================

``extends`` keeps a family of variants short and makes the differences obvious:

.. code-block:: yaml

   # variants/domain_gen1.flync.yaml
   features:
     architecture: domain

   # variants/domain_gen2.flync.yaml
   extends: domain_gen1
   features:
     compute_generation: gen2

Chains can have any length; a cycle is an error. A variant that is only there as a base for others is
still a declared variant and is validated too. If a base does not describe a real product, consider
making it one, or keep it small enough that it stays valid.

Two variants that end up with exactly the same completed configuration resolve to the same model. FLYNC
warns about it, since it is usually a copy-paste mistake.

Variant conditions
##################

A variant condition (a *presence condition*) is a boolean expression over the features:

.. code-block:: text

   park_assist and architecture in [domain, zonal] and not (compute_generation < gen2)

Syntax
======

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Construct
     - Example
   * - boolean feature or qualifier on its own
     - ``park_assist``, ``zonal``
   * - equality, inequality
     - ``architecture == zonal``, ``architecture != domain``, ``park_assist == false``
   * - membership
     - ``architecture in [domain, zonal]``, ``architecture not in [domain]``
   * - ordering (``ordered`` features only)
     - ``compute_generation >= gen2``, ``compute_generation < gen2``
   * - logic
     - ``and``, ``or``, ``not``, parentheses
   * - literals
     - ``true``, ``false``

Precedence, from strongest to weakest, is: comparisons, ``not``, ``and``, ``or``. So ``a or b and not c``
means ``a or (b and (not c))``. Use parentheses whenever it helps the reader.

Values that are not identifiers must be quoted: ``platform == "gen-2a"``. Numbers can be written as they
are (``release >= 2027``) and are compared as the text they were declared with.

Type rules
==========

Every condition is checked against the feature model, in every file, independently of the variant that
is being loaded. A misspelled name or value is reported where it is written.

* A boolean feature or a qualifier can be used on its own, or compared with ``true``/``false`` using
  ``==``/``!=``.
* An enumerated feature must be compared, and only with its declared values.
* ``<``, ``<=``, ``>`` and ``>=`` need a feature declared ``ordered: true``.

Conditions are written over features, never over variant names: a condition on a feature keeps working
when a new variant with the same features is added.

What is not allowed
===================

Arithmetic, function calls, attribute access, chained comparisons (``gen1 < compute_generation < gen3``)
and any other Python syntax are rejected. Conditions are parsed and checked against a strict whitelist and
are **never executed as Python**, so a workspace cannot run code.

Variation points
################

A variation point is a place in the workspace where variants differ. FLYNC has two, and both are a
``variant_condition``:

.. list-table::
   :header-rows: 1
   :widths: 22 38 40

   * - Kind
     - Written as
     - Decides
   * - ECU presence
     - ``variant_condition: <condition>`` at the root of ``ecus/<ecu>/ecu_metadata.flync.yaml``
     - which variants the whole ECU, with everything in its folder, is part of
   * - System topology entry
     - ``variant_condition: <condition>`` on an entry of a list in ``topology/``
     - which variants a connection, or a node of a multidrop segment, is part of

Whatever a false condition removes is removed *before validation*. Everything that refers to it is then
checked as usual: a connection that still leads to a removed ECU is reported, in exactly the variants
where the ECU is missing. So FLYNC's normal reference checks keep the variants consistent without any
extra rule.

ECU presence
============

An ECU folder is part of a variant when the ``variant_condition`` at the root of its
``ecu_metadata.flync.yaml`` holds, or when the document has none. The condition is the first line of a
document every ECU has anyway, and the folder tree stays an ordinary FLYNC tree.

.. code-block:: yaml

   # ecus/rear_camera/ecu_metadata.flync.yaml
   variant_condition: park_assist
   author: Dev
   ...

This is the only variation point an ECU has. **An ECU is the same in every variant it is part of**: no
other document of an ECU - its ports, controllers, interfaces, switches, internal topology, sockets - may
carry a variation point. An ECU that differs between variants is a separate ECU:

* **Optional ECU**: ``ecus/rear_camera/`` exists only in the variants with park assist.
* **Alternative ECUs**: ``ecus/central_compute_gen1/`` and ``ecus/central_compute_gen2/`` carry the
  conditions ``gen1`` and ``gen2``. They are two independent ECUs as far as FLYNC is concerned; what makes
  them alternatives is that their conditions exclude each other, so every product has exactly one of them.
  Qualifiers over one enumerated feature exclude each other by construction.
* **An ECU with a port more**: ``adas_controller`` (``not park_assist``) and ``adas_controller_pa``
  (``park_assist``) are alternatives too; only the second has the port for the rear camera.

Give alternatives the same names for the parts the system topology refers to (``adas_p1``, ``cc_p1``), so
that the topology does not need to care which one is present.

The ECU model names the document in its ``PRESENCE_DOCUMENT`` class attribute
(``ECU.PRESENCE_DOCUMENT = "ecu_metadata"``). An ECU folder validated on its own is loaded as written: its
presence condition is about the workspace, so it is only checked against the feature model.

System topology entries
=======================

The system topology (``topology/ethernet_topology.flync.yaml``) wires the ECUs of every variant. Any entry
of a list in it - a connection, or a node of a multidrop segment - may carry ``variant_condition``. When
the condition is false in the variant, the entry is dropped; when it is true, only the
``variant_condition`` key itself is removed. The key never reaches the model.

.. code-block:: yaml

   # topology/ethernet_topology.flync.yaml
   connections:
     - type: ecu_port_to_ecu_port
       id: link_rear_camera
       variant_condition: park_assist      # a link that only some products have
       ecu1_port: adas_p2
       ecu2_port: rcam_p1
     - type: ethernet_multidrop
       id: DoorSegment                     # a segment every product has ...
       nodes:
         - ecu_port: bdc_p2
           node_id: 0
           variant_condition: domain       # ... with a coordinator per architecture
         - ecu_port: zcf_p2
           node_id: 0
           variant_condition: zonal
         - ecu_port: dml_p1
           node_id: 1

Write the condition on the entry and nowhere else in the file: a condition at the root of the document,
or on a nested block such as the ``plca`` settings of a segment, is reported. A connection that differs
between variants is two connections with exclusive conditions.

Everything else is the same in every variant
============================================

The variability model, the communication definitions (buses, frames, PDUs, SOME/IP services), the
applications, the metadata of the system, and every document of an ECU other than the root of its
``ecu_metadata`` are the same in every variant. A variation point in any of them is reported:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Written where
     - Reported as
   * - inside an ECU, anywhere but the root of its ``ecu_metadata``
     - ``FLYNC-VAR-MAJ-STRUCT-483``: model the ECU that differs as a separate ECU
   * - in the system topology, not on an entry of a list
     - ``FLYNC-VAR-MAJ-STRUCT-484``
   * - in any other document
     - ``FLYNC-VAR-MAJ-STRUCT-485``
   * - ``variant_values``, anywhere
     - ``FLYNC-VAR-MAJ-STRUCT-486``: values do not vary; an element that differs is a separate element
   * - inside ``variability/``
     - ``FLYNC-VAR-MAJ-STRUCT-445``

Modeling a difference
======================

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Situation
     - How to model it
   * - An ECU exists only in some products
     - ``variant_condition`` at the root of its ``ecu_metadata``
   * - An ECU differs between products (a port, a controller, an interface, a switch, a part number, a
       software setting)
     - one ECU per configuration, with mutually exclusive conditions
   * - Products use different ECUs for the same job (a domain or a zone controller)
     - one ECU each, with mutually exclusive conditions
   * - A link exists only in some products
     - ``variant_condition`` on the connection in the system topology
   * - A multidrop segment has a different node in some products
     - ``variant_condition`` on the node
   * - A connection differs between products
     - one connection per configuration, with mutually exclusive conditions
   * - A bus, a PDU, or a service is used only by some products
     - define it once, for every product. A bus that no ECU of a product attaches to is reported as a
       warning in that product.

Reserved names
==============

``variant_condition`` is a reserved key, and ``variant_values`` is rejected wherever it appears. Using a
variation point in a workspace without a ``variability/`` folder is an error, since it could never be
resolved.

Loading and resolution
######################

Selecting the variant
=====================

The variant a workspace is resolved for is chosen when it is loaded:

1. the explicitly selected variant (``--variant`` on the command line, ``variant=`` in the SDK);
2. otherwise the ``default_variant`` of the feature model;
3. otherwise loading fails, listing the declared variants.

The selection is never stored in the workspace configuration. The same files are resolved for any
variant.

What the loader does
====================

1. Load and validate the variability model. If it is invalid, no variant can be resolved, and loading
   stops with a finding that points to ``variability/``.
2. Complete the decisions of the selected variant (see :ref:`variability_completion`).
3. Check every variation point of every document against the feature model and its place in the
   workspace, for all variants at once (see :ref:`variability_validation`).
4. Leave out the ECU folders whose presence condition is false.
5. Resolve the ``variant_condition`` entries of the system topology.
6. Validate the resulting, variant-free data with the normal FLYNC models.

Error positions still point to the line and column in the file you wrote, also when entries before it
were removed by the resolution. Documents that are not part of the loaded variant are available as
``FLYNCWorkspace.inactive_documents()``, for example so that an editor can gray them out.

A model built this way remembers its variant: :attr:`FLYNCModel.active_variant
<flync.model.flync_model.FLYNCModel.active_variant>` is the
:class:`~flync.model.flync_4_variability.VariantContext` of the variant, or ``None`` for a workspace without
variability.

.. _variability_validation:

Validation
##########

FLYNC checks the variability on three levels.

**The variability model.**

* Features: names are valid and unique, features and qualifiers share one namespace, ``type`` agrees with
  ``values``, ``ordered`` is only used with ``values``, and defaults are valid.
* Constraints and qualifiers: every condition uses declared names and values only, and qualifiers have no
  cycles.
* Variants: at least one is declared, ``default_variant`` names a declared variant, ``extends`` names a
  declared variant and has no cycles, every variant decides only declared features with valid values,
  every enumerated feature without a default gets a value, and every variant satisfies the constraints.
  Two variants with the same completed configuration are reported as a warning.

Keys that are not part of the feature model or of a variant are rejected, so a typo in a key name is
reported where it is written.

**The variation points**, independently of the selected variant: every condition parses and uses
declared names and values with the right operators, and every variation point is in one of its two
places - the root of an ECU's ``ecu_metadata`` or an entry of the system topology. A condition that is
false in *every* declared variant is reported as a warning, because the element it guards is never used.

**Every variant**, fully resolved. ``flync validate`` runs the complete FLYNC validation once per
declared variant. Every existing rule (unique names, valid references, address conflicts, timing
budgets, ...) therefore applies to each product on its own. The output has one row per variant, followed
by every finding once, with the variants it occurs in. The run fails when any variant fails.

All variability findings have ids of the form ``FLYNC-VAR-...``; see the :doc:`../../error_catalog`.

.. _variability_examples:

Example workspaces
##################

``examples/flync_4_variability/`` holds one complete workspace per supported use case. Each is a full FLYNC
model that validates for every declared variant. The ``README.md`` of the folder lists the files to look at,
and :ref:`variability_step_by_step` walks through them in order.

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Workspace
     - What it shows
   * - ``01_optional_component``
     - One boolean feature, two variants: an optional rear camera ECU, two alternative ADAS controllers (with
       and without the port for the rear camera), and ``variant_condition`` on the system link to the rear
       camera.
   * - ``02_architecture_alternatives``
     - Two E/E architectures and two hardware generations in one repository: enumerated and ordered features, a
       constraint, qualifiers, and a variant that extends another. Domain and zone controllers that exist in one
       architecture only, two generations of the central compute ECU with the same external ports, door modules
       that every product has, and one system topology whose links carry their architecture, with a shared
       10BASE-T1S segment whose coordinator node depends on the architecture.

Scenario cookbook
#################

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Scenario
     - How it is modeled
   * - Optional ECU (rear camera, trailer module)
     - A boolean feature; ``variant_condition: park_assist`` at the root of ``ecus/rear_camera/ecu_metadata.flync.yaml``,
       and on the connections of the system topology that lead to it.
   * - ECU hardware derivative (more ports, extra controller, other part numbers)
     - One ECU per derivative, with mutually exclusive conditions (``adas_controller`` with ``not park_assist``,
       ``adas_controller_pa`` with ``park_assist``). Give the parts the system topology refers to the same names.
   * - Optional interface, controller, or switch inside an ECU
     - Not a variation point: the ECU with it and the ECU without it are two ECUs.
   * - Same ECU, different wiring
     - One ECU, and alternative connections or multidrop nodes in the system topology, with mutually exclusive
       conditions (the coordinator nodes of the door segment).
   * - Same ECU, different interfaces (CAN in one architecture, Ethernet in the other)
     - Two ECUs, one per architecture.
   * - Different external topology (domain vs. zonal)
     - ``variant_condition`` per connection of ``ethernet_topology.flync.yaml``, including multidrop segments and
       their nodes.
   * - Same logical ECU built differently per architecture or generation
     - Two ECUs with mutually exclusive presence conditions, e.g. ``central_compute_gen1`` and
       ``central_compute_gen2``.
   * - A bus, a PDU, or a service that only some products use
     - Defined once for every product; only the ECUs that use it vary.
   * - Several architectures in one repository
     - An enumerated ``architecture`` feature with qualifiers; shared ECUs carry no condition.
   * - Hardware generation / revision
     - An ``ordered`` feature: ``compute_generation >= gen2``.
   * - Combinations the product line does not offer
     - A ``constraint``: ``architecture != zonal or compute_generation >= gen2``.
   * - Option codes for features
     - ``attributes`` on the features.

Modeling guidelines
###################

* **Start from the products.** List the products that are actually built, then derive the features that
  tell them apart. Do not add features "for later": a feature that no variant uses only makes conditions
  harder to read.
* **Model only what varies.** The feature model describes the differences, not the whole system; parts
  that are the same in every product belong in the workspace without any feature.
* **One ECU, one configuration.** An ECU never varies inside. When some products need an ECU with a port,
  a controller or a setting more, add a second ECU and select each one with a condition at the root of its
  ``ecu_metadata``. The differences between products then stay in two places: the ECU folders and the
  system topology.
* **Give enumerated features a default** when one value is the usual choice, so that only the exceptions
  have to be decided.
* **Name features after product characteristics**, not after implementation details. The variation
  points translate features into network elements.
* **Use enumerations for exclusive choices.** One ``architecture`` feature with ``values: [domain, zonal]``
  says more, and needs fewer constraints, than two boolean features plus a rule that exactly one is set.
* **Give every constraint a description.** It is the error message a colleague will read.
* **Use qualifiers for conditions that appear more than once**, and give them names that say why an
  element varies.
* **Keep alternatives mutually exclusive.** Write the presence conditions of two ECUs that stand for the
  same thing so that at most one can be true. Two qualifiers over the same enumerated feature are
  exclusive by construction.
* **Use** ``extends`` **to show differences**: a variant file that only lists what differs from its parent
  is easy to review.
* **Read** ``flync variants show`` **for new variants.** The source column shows what a variant decided
  itself and what it inherited or took by default.
* **Run** ``flync variants check`` **before** ``flync validate``. It checks the variability model and the variation
  points without validating every variant, so mistakes in the variability show up sooner.

Working with variants
#####################

Command line
============

.. code-block:: bash

   flync validate <workspace>                          # every declared variant
   flync validate <workspace> --variant zonal_gen2     # one variant
   flync info ecus <workspace> --variant zonal_gen2
   flync variants list <workspace>                     # one row per variant; first 50, see --limit
   flync variants list <workspace> --where "architecture == zonal" -f compute_generation   # filter, add feature columns
   flync variants show domain_gen2 <workspace>         # completed configuration with value sources and active qualifiers
   flync variants trace <workspace>                    # features -> workspace elements
   flync variants trace --feature architecture <workspace>
   flync variants diff domain_gen1 zonal_gen2 <workspace>   # feature and element differences
   flync variants check <workspace>                    # variability model and every variation point
   flync variants export zonal_gen2 --out <dir> <workspace>
   flync schema <dir> --variants                       # JSON Schema that accepts variation points

``flync variants list`` prints one row per variant - its name, the variant it extends, and its description -
so that it stays readable for a product line with thousands or millions of variants. It shows the first 50
variants and says how many there are; ``--limit N`` changes that (``0`` shows all of them), ``--where``
keeps only the variants in which a variant condition holds, and ``--feature`` (repeatable) adds a column
with the value of a feature. The full configuration of one variant is in ``flync variants show``.

``flync validate`` on a variant workspace prints one row per variant, then every finding once with the
variants it occurs in. It fails when any variant fails. Validating one ECU folder checks the ECU as
written - it is the same in every variant - and checks its presence condition against the feature model
of the workspace it belongs to.

``flync schema --variants`` writes JSON Schemas that also accept ``variant_condition`` where it is allowed
- in an ECU's metadata and on the entries of the system topology - so that an editor offers completion and
checks in the 150 % files too.

.. _variability_analyses:

Analyzing variants
==================

**Traceability.** ``flync variants trace`` lists, for every feature, its category and every variation point
that refers to it - directly or through a qualifier: the ECUs it decides
(``ecus/rear_camera/ecu_metadata.flync.yaml``) and the entries of the system topology, named by their id
(``topology/ethernet_topology.flync.yaml: connections[1] (link_rear_camera)``). It answers "which elements
does this feature decide?" and, read the other way, "which feature is this element there for?". A feature
with no workspace elements is either a pure product decision or a sign that something is missing.

**Comparison.** ``flync variants diff <a> <b>`` lists the features whose values differ, and every element of
the workspace that only one of the two variants has: the ECUs and the entries of the system topology. Use
it to review a new variant against an existing one, or to explain to a subsystem team what changes between
two products.

SDK
===

.. code-block:: python

   from flync.sdk.helpers.generation_helpers import export_variant
   from flync.sdk.helpers.validation_helpers import validate_variants
   from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

   path = "examples/flync_4_variability/02_architecture_alternatives"
   ws = FLYNCWorkspace.load_workspace("body", path, variant="domain_gen2")
   variant = ws.flync_model.active_variant
   variant.value("architecture")            # "domain"
   variant.is_enabled("gen2")               # True (boolean features and qualifiers)
   variant.evaluate("zonal or compute_generation >= gen2")
   variant.source("architecture")           # ValueSource.INHERITED

   ws.select_variant("zonal_gen2")          # re-resolve, without re-reading the files

   result = validate_variants(path)
   result.passed, result.failed_variants()

   export_variant(ws.flync_model, "out/zonal_gen2")      # a plain workspace for downstream tools

``Variability`` (``ws.flync_model.variability``) gives access to the variability model itself:
``variant_names()``, ``features()``, ``context(name)`` for any variant, ``contexts()`` for all of them,
``configuration(name)`` for the completed configuration with its value sources and open decisions, and
``is_dead(condition)`` to test whether a condition holds in no declared variant.

The analyses are available in the SDK too:

.. code-block:: python

   from flync.sdk.helpers.variant_helpers import compare_workspace_variants, trace_workspace_features

   variability = ws.flync_model.variability
   traced = trace_workspace_features(path, variability)
   [point.describe() for point in traced["architecture"]]

   comparison = compare_workspace_variants(path, variability, "domain_gen1", "zonal_gen2")
   comparison.features, comparison.elements

``flync.model.flync_4_variability.configure(feature_model, decisions)`` completes any set of decisions
without a declared variant, e.g. to try out a configuration interactively.

Editing and exporting
=====================

A loaded model is always one resolved variant, so it cannot be written back over the 150 % workspace:
``FLYNCWorkspace.load_model`` / ``dump_flync_workspace`` refuse it with
:class:`~flync.sdk.workspace.flync_workspace.VariantWorkspaceWriteError`. Edit the 150 % files directly. Edits
made through ``update_document`` are resolved again for the active variant, and an edit to
``variability/`` re-resolves the whole workspace.

To hand one variant to a tool that does not know about variants, export it. ``flync variants export``
or ``export_variant()`` writes an ordinary workspace without ``variability/`` and without variation
points. The ``flync`` converter resolves the variant set in its configuration (``--src-variant`` on the
converter command line).

Limitations and FAQ
###################

**Which kinds of variability are supported?** Optional components and architecture alternatives: a flat
list of boolean and enumerated features, constraints, and qualifiers. Feature trees, rules that set
feature values automatically and split feature models are not part of the model; keys for them are
rejected.

**Can FLYNC list every valid combination of the feature model?** No. FLYNC validates the declared
variants, a closed set. Declare every product you build.

**Can a feature have a free numeric value?** No; features are boolean or enumerated. Model a numeric
parameter with a few discrete settings as an (ordered) enumeration. The explicit ``type`` key is there so
that more kinds of feature can be added later without changing existing feature models.

**Can a variant extend several variants?** No, ``extends`` names one variant. Build a chain instead.

**Can a constraint select a feature for me?** No. Constraints only check. Give the feature a ``default``,
or decide it in the variant or in a variant it extends.

**Can conditions use attributes or the variant name?** No. Only features and qualifiers decide what is
part of a variant.

**Why can an ECU not vary inside?** Because an ECU that differs is, for everyone who builds, buys, flashes,
or tests it, a different ECU, with its own part number and its own validation. Two ECU folders keep each
configuration complete and reviewable on its own, and keep the differences between products in two places:
which ECUs a product has, and how the system topology connects them.

**Can a whole document be conditional?** Only an ECU, through the root of its ``ecu_metadata.flync.yaml``,
which removes the whole ECU folder. Every other document is the same in every variant.

**Can a value differ between variants?** No; ``variant_values`` is not supported. A value that differs
belongs to an element that differs, which is a separate ECU or a separate entry of the system topology.

**How does FLYNC know that two ECUs are alternatives of each other?** It does not, and it does not need
to: every product is validated on its own. Two ECUs whose conditions exclude each other never meet in one
product. Give them the same port names when the links around them should not care which one is present.

**Do my existing validators need to know about variants?** No. Every model sees a variant-free
configuration, and every rule automatically applies per variant.

Reference
#########

.. autoclass:: flync.model.flync_4_variability.Variability()
   :members: features, variant_names, configuration, context, contexts, symbol_table, is_dead

.. autoclass:: flync.model.flync_4_variability.FeatureModel()

.. autoclass:: flync.model.flync_4_variability.Feature()

.. autoclass:: flync.model.flync_4_variability.FeatureType()
   :members:

.. autoclass:: flync.model.flync_4_variability.FeatureCategory()
   :members:

.. autoclass:: flync.model.flync_4_variability.FeatureConstraint()

.. autoclass:: flync.model.flync_4_variability.VariantDefinition()

.. autoclass:: flync.model.flync_4_variability.VariantContext()
   :members: value, source, is_enabled, evaluate, holds

.. autoclass:: flync.model.flync_4_variability.ValueSource()
   :members:

.. autoclass:: flync.model.flync_4_variability.Configuration()

.. autofunction:: flync.model.flync_4_variability.configure

.. autofunction:: flync.model.flync_4_variability.compile_condition

.. autoclass:: flync.model.flync_4_variability.analysis.VariationPoint()
   :members: describe, outcome

.. autofunction:: flync.model.flync_4_variability.analysis.trace_features

.. autofunction:: flync.model.flync_4_variability.analysis.compare_variants
