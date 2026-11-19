"""
Variant resolution for the FLYNC workspace.

Sits between the object registry and the loader: it decides which documents, directory entries and
document content belong to the active product variant, and collects the variability findings. The
pure resolution rules live in :mod:`flync.model.flync_4_variability.resolution`; this layer applies
them to the workspace's documents and folders.
"""

import logging
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Optional, Union, get_args, get_origin

from pydantic_core import ErrorDetails

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions_handling import get_unique_errors, locate_errors
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_variability import Variability
from flync.model.flync_4_variability.resolution import (
    ABSENT,
    FEATURE_MODEL_DOCUMENT,
    PRESENCE_DOCUMENT_ATTR,
    VARIABILITY_FOLDER,
    DocumentRole,
    copy_tree,
    document_condition,
    document_present,
    document_role,
    has_variation_points,
    invalid_variability_error,
    is_in_variability,
    lint_document,
    no_variant_selected_error,
    resolve_document,
    unknown_variant_error,
)
from flync.model.flync_model import FLYNCModel
from flync.sdk.utils.field_utils import get_metadata

from ._object_mapping import _WorkspaceObjectMapping

logger = logging.getLogger(__name__)

VARIABILITY_FIELD = "variability"
"""Name of the root model field holding the variability model."""

WORKSPACE_ROOT_MARKER = "system_metadata.flync.yaml"
"""File that marks the root of a FLYNC workspace, used to find the variability of a validated sub-node."""


class _WorkspaceVariants(_WorkspaceObjectMapping):
    """Applies the variability of the workspace to its documents and directory entries."""

    # region load lifecycle

    def _begin_variant_load(self) -> None:
        """Reset the per-load variant state at the start of a root load."""

        self._traces.clear()
        self._projected.clear()
        self._consumed_docs.clear()
        self._selection_diags.clear()
        self._lint_diags.clear()
        self._variability = None
        self._variant_ctx = None
        self._variability_root = None

    def _activate_variability(self, has_folder: bool, variability: Optional[Variability]) -> bool:
        """
        Select the variant to resolve once the variability model is loaded.

        The variant is the explicitly requested one, else the feature model's ``default_variant``. Without a ``variability/``
        folder nothing is selected and every variation point resolves as false.

        Args:
            has_folder (bool): Whether the workspace has a ``variability/`` folder.
            variability (Variability | None): The loaded variability model; ``None`` when it failed to load.

        Returns:
            bool: ``False`` when no variant can be resolved and the load must stop.
        """

        self._variability = variability if has_folder else None
        self._variant_ctx = None
        if not has_folder:
            return self._activate_without_variability()
        if variability is None:
            self._add_selection_diag(FEATURE_MODEL_DOCUMENT, "", invalid_variability_error())
            return False
        self._run_variant_lint()
        return self._select_variant(variability)

    def _activate_without_variability(self) -> bool:
        """Accept a workspace without ``variability/`` unless a variant was requested, which cannot exist."""

        if self._requested_variant is not None:
            self._add_selection_diag(FEATURE_MODEL_DOCUMENT, "", unknown_variant_error(self._requested_variant, []))
            return False
        self._run_variant_lint()
        return True

    def _select_variant(self, variability: Variability) -> bool:
        """Select the requested variant, else the default one; records a finding and returns ``False`` when there is none."""

        names = variability.variant_names()
        selected = self._requested_variant or variability.feature_model.default_variant
        if selected is None:
            self._add_selection_diag(FEATURE_MODEL_DOCUMENT, "", no_variant_selected_error(names))
            return False
        if selected not in names:
            self._add_selection_diag(FEATURE_MODEL_DOCUMENT, "", unknown_variant_error(selected, names))
            return False
        self._variant_ctx = variability.context(selected)
        return True

    def _stamp_active_variant(self, model: Any) -> None:
        """Record on a loaded root model which variant it was resolved for."""

        if isinstance(model, FLYNCModel):
            model._active_variant = self._variant_ctx

    @staticmethod
    def _find_variability_folder(root: Path) -> Optional[Path]:
        """
        Find the ``variability/`` folder that applies to a validated sub-node (e.g. a single ECU folder).

        Walks up from ``root`` to the enclosing workspace root, recognized by its system metadata file.
        """

        for candidate in (root, *root.parents):
            if (candidate / WORKSPACE_ROOT_MARKER).is_file():
                folder = candidate / VARIABILITY_FOLDER
                return folder if folder.is_dir() else None
        return None

    # endregion

    # region findings

    def _add_selection_diag(self, doc_id: str, name: str, diag: ErrorDetails) -> None:
        """Record a variant-selection finding against a document."""

        self._selection_diags.setdefault((doc_id, name), []).append(diag)

    def _run_variant_lint(self) -> None:
        """Check the variation points of every document, independently of the active variant."""

        self._lint_diags.clear()
        for uri in self.documents:
            self._lint_one_document(uri)

    def _lint_inputs(self):
        """The symbol table and the variant contexts to lint against; ``(None, [])`` without variability."""

        variability = self._variability
        if variability is None:
            return None, []
        return variability.symbol_table(), variability.contexts()

    def _lint_one_document(self, uri: str) -> None:
        """(Re)compute the variant-independent findings of one document."""

        self._lint_diags.pop(uri, None)
        document = self.documents.get(uri)
        if document is None or not has_variation_points(document.text):
            return
        symbols, contexts = self._lint_inputs()
        found = lint_document(uri, document.ast, symbols, contexts, self._document_role(uri))
        if found:
            locate_errors(found, None, document.source_nodes())
            self._lint_diags[uri] = found

    def _finalize_variability_diags(self) -> None:
        """Merge the variability findings into :attr:`documents_diags`, once the load (or partial reload) is done."""

        merged: dict[str, list[ErrorDetails]] = {}
        for doc_id, found in self._lint_diags.items():
            merged.setdefault(doc_id, []).extend(found)
        for (doc_id, _), found in self._selection_diags.items():
            merged.setdefault(doc_id, []).extend(found)
        for doc_id, found in merged.items():
            self.documents_diags[doc_id] = get_unique_errors(self.documents_diags.get(doc_id, []) + found)

    # endregion

    # region documents and directory entries

    def _document_role(self, uri: str) -> DocumentRole:
        """
        What a document may contain in the way of variation points, from its place in the workspace whose variability applies.

        The place is taken relative to the root of that workspace, so the documents of a validated sub-node (e.g. one ECU
        folder) get the role they have in the whole workspace. Without variability every document is
        :attr:`~flync.model.flync_4_variability.resolution.DocumentRole.OTHER`.
        """

        root = self._variability_root
        if root is None or self.workspace_root is None:
            return DocumentRole.OTHER
        try:
            path = (self.workspace_root / uri).relative_to(root).as_posix()
        except ValueError:
            return DocumentRole.OTHER
        return document_role(path, self._ecu_presence_file())

    def _ecu_presence_file(self) -> str:
        """File name of the presence document of an ECU, e.g. ``ecu_metadata.flync.yaml``."""

        name = self._presence_file(ECU)
        assert name is not None, "the ECU model declares its presence document"
        return name

    def _presence_file(self, model_type: type[FLYNCBaseModel]) -> str | None:
        """File name of the document named by the ``PRESENCE_DOCUMENT`` of a folder-based model, or ``None`` when it has none."""

        field_name = getattr(model_type, PRESENCE_DOCUMENT_ATTR, None)
        field_info = model_type.model_fields.get(field_name) if field_name else None
        if field_info is None:
            return None
        external = get_metadata(field_info.metadata, External)
        if external is None or OutputStrategy.SINGLE_FILE not in external.output_structure:
            return None
        stem = external.path if external.naming_strategy == NamingStrategy.FIXED_PATH and external.path else field_name
        return f"{stem}{self.configuration.flync_file_extension}"

    def _document_content(self, uri: str) -> Any:
        """
        Return the content of a document as it is validated for the active variant.

        Always a fresh copy, so validation can prune it without corrupting the parsed document that later loads (other variants,
        revalidation) reuse. Variation points are resolved; the variability model itself is taken as written. The condition at
        the root of an ECU's presence document is only stripped: the loader has already decided the presence of the ECU folder.

        Returns:
            The resolved content, ``None`` for an empty document, or :data:`~flync.model.flync_4_variability.resolution.ABSENT`
            when the whole document is not part of the variant.
        """

        document = self.documents[uri]
        data = document.ast
        if data is None:
            return None
        if is_in_variability(uri) or not has_variation_points(document.text):
            self._traces.pop(uri, None)
            self._consumed_docs.add(uri)
            return copy_tree(data)
        resolved, trace = resolve_document(data, self._variant_ctx, root_presence=self._document_role(uri) is not DocumentRole.ECU_PRESENCE)
        if trace:
            self._traces[uri] = trace
        else:
            self._traces.pop(uri, None)
        if resolved is not ABSENT:
            self._consumed_docs.add(uri)
        return resolved

    def _document_absent(self, uri: str) -> bool:
        """Whether a document carries a root ``variant_condition`` that is false in the active variant."""

        document = self.documents.get(uri)
        if document is None or is_in_variability(uri):
            return False
        return not document_present(document.ast, self._variant_ctx)

    def _root_condition(self, uri: str) -> object | None:
        """The root ``variant_condition`` of a document, or ``None`` when it has none (or is unknown)."""

        document = self.documents.get(uri)
        return document_condition(document.ast) if document is not None else None

    def _presence_documents(self, folder: Path, element_type: Any) -> list[str]:
        """
        Ids of the documents that decide whether ``folder`` is part of the variant, for an element of ``element_type``.

        A folder-based model names the field whose document carries the condition in its ``PRESENCE_DOCUMENT`` class
        attribute; only an ECU has one (``ecu_metadata``). A union element type contributes the presence document of every member.
        """

        found: list[str] = []
        for model_type in _candidate_types(element_type):
            name = self._presence_file(model_type)
            if name is not None:
                found.append(self.document_id_from_path(folder / name))
        return found

    def _entry_present(self, entry: Path, element_type: Any) -> bool:
        """
        Whether a file or folder of a list or dict field is part of the active variant.

        A folder is absent when the root condition of its presence document is false (see :meth:`_presence_documents`), which
        only an ECU folder has. The presence document itself is always present: its condition is about the folder, which is
        already decided when the document is read (or not decided at all, for an ECU validated on its own). Any other file
        with a root ``variant_condition`` that is false is absent too, although the lint reports such a condition. Everything
        else is present.
        """

        if entry.is_dir():
            return not any(self._document_absent(uri) for uri in self._presence_documents(entry, element_type))
        uri = self.document_id_from_path(entry)
        return self._document_role(uri) is DocumentRole.ECU_PRESENCE or not self._document_absent(uri)

    def _variant_entries(self, item_dir: Path, element_type: Any) -> list[Path]:
        """The sorted entries of a folder-based list or dict field that belong to the active variant."""

        entries = sorted(entry for entry in item_dir.iterdir() if not self.is_hidden_path(entry))
        return [entry for entry in entries if self._entry_present(entry, element_type)]

    def _under_absent_folder(self, uri: str) -> bool:
        """Whether a document lies in an ECU folder whose presence document removes it from the active variant."""

        parent = Path(uri).parent
        while parent.as_posix() not in (".", ""):
            prefix = parent.as_posix() + "/"
            for other in self.documents:
                if (
                    other != uri
                    and other.startswith(prefix)
                    and "/" not in other[len(prefix) :]
                    and self._document_role(other) is DocumentRole.ECU_PRESENCE
                    and self._document_absent(other)
                ):
                    return True
            parent = parent.parent
        return False

    def inactive_documents(self) -> list[str]:
        """
        Documents whose content is not part of the loaded model.

        In a variant workspace these are mostly the documents of the ECUs that are not part of the active variant, so an editor
        can show them as inactive. Documents that no model field maps to are listed too.

        Returns:
            list[str]: Workspace-relative ids of the documents, sorted.
        """

        return sorted(uri for uri in self.documents if uri not in self._consumed_docs)

    # endregion


def _candidate_types(element_type: Any) -> list[type[FLYNCBaseModel]]:
    """The model classes an element type can be: itself, or the members of a union, with ``Annotated`` unwrapped."""

    if get_origin(element_type) is Annotated:
        element_type = get_args(element_type)[0]
    origin = get_origin(element_type)
    if origin is Union or origin is UnionType:
        return [member for arg in get_args(element_type) for member in _candidate_types(arg)]
    return [element_type] if isinstance(element_type, type) and issubclass(element_type, FLYNCBaseModel) else []


__all__ = ["ABSENT", "VARIABILITY_FIELD", "_WorkspaceVariants"]
