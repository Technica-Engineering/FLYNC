"""
Variant view of a composed YAML document.

Variant resolution removes list items and mapping keys from a document before the data is validated. Error
positions and the object map are found by walking the composed (PyYAML) node tree of the document alongside
the validated data, so that tree has to look like the resolved data too.

:func:`project_node` builds that view from the :class:`~flync.model.flync_4_variability.resolution.ResolutionTrace`
of the document: removed nodes are left out. Every node that is kept is the original node (or a shallow copy of
it), so line and column marks still point into the file the user wrote.
"""

import copy

from yaml.nodes import MappingNode, Node, SequenceNode

from flync.model.flync_4_variability.resolution import ResolutionTrace, YamlPath


def _normalized(trace: ResolutionTrace) -> tuple[set[YamlPath], frozenset[YamlPath]]:
    """Use text for mapping keys, so paths compare equal to the scalar values of the composed key nodes."""

    def norm(path: YamlPath) -> YamlPath:
        """Turn the mapping keys of a path into text."""

        return tuple(part if isinstance(part, int) and not isinstance(part, bool) else str(part) for part in path)

    removed = {norm(path) for path in trace.removed}
    prefixes = frozenset(norm(path) for path in trace.touched_prefixes())
    return removed, prefixes


def _project(node: Node, path: YamlPath, removed: set[YamlPath], prefixes: frozenset[YamlPath]) -> Node:
    """Project ``node``, found at ``path``, through what the resolution removed."""

    projected = node
    if path in prefixes and isinstance(node, MappingNode):
        mapping = copy.copy(node)
        mapping.value = [
            (key_node, _project(value_node, path + (str(key_node.value),), removed, prefixes))
            for key_node, value_node in node.value
            if path + (str(key_node.value),) not in removed
        ]
        projected = mapping
    elif path in prefixes and isinstance(node, SequenceNode):
        sequence = copy.copy(node)
        sequence.value = [
            _project(item, path + (index,), removed, prefixes) for index, item in enumerate(node.value) if path + (index,) not in removed
        ]
        projected = sequence
    return projected


def project_node(node: Node | None, trace: ResolutionTrace | None) -> Node | None:
    """
    Return the view of a composed document as resolved for the active variant.

    Args:
        node (Node | None): The composed root node of the document.
        trace (ResolutionTrace | None): What resolving the document removed.

    Returns:
        Node | None: ``node`` itself when nothing was resolved, otherwise a filtered tree that shares every untouched node with the original.
    """

    if node is None or not trace:
        return node
    removed, prefixes = _normalized(trace)
    return _project(node, (), removed, prefixes)
