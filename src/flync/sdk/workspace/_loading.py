"""
Disk-to-model loading for the FLYNC workspace.

Walks a workspace directory, routes externally annotated fields to their files or folders, and
validates each load node. Depends on :mod:`._object_mapping` to register what it loads.
"""

import logging
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Optional, Union, cast, get_args, get_origin

from pydantic.fields import FieldInfo
from pydantic_core import ErrorDetails, ValidationError

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    Namespaced,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.base_models.namespace import qualify_name
from flync.core.utils.exceptions_handling import is_semantic_validation_error, locate_errors, validate_with_policy
from flync.model.flync_4_variability import Variability
from flync.model.flync_4_variability.resolution import ABSENT, VARIABILITY_FOLDER
from flync.sdk.utils.field_utils import get_metadata
from flync.sdk.utils.model_dependencies import model_force_rebuild
from flync.sdk.utils.sdk_types import PathType

from ._base import LoadNode, ParentLink
from ._variants import VARIABILITY_FIELD, _WorkspaceVariants
from .document import Document, read_file

logger = logging.getLogger(__name__)

_UNRECOGNIZED_FILE_MSG = "Unrecognized file found in FLYNC workspace: %s"


class _WorkspaceLoading(_WorkspaceVariants):
    """Reads FLYNC documents from disk and validates them into model instances."""

    def _open_documents(self):
        """
        Open and parse every document in the workspace matching the configured file extension.

        Documents are read and parsed in this process, in sorted path order.

        Returns:
            None
        """
        if self.workspace_root is None:
            return
        for path in sorted(self.workspace_root.rglob(f"*{self.configuration.flync_file_extension}")):
            if path.is_file():
                self._open_document(path)

    def _open_document(self, uri: PathType):
        """
        Open a document, parse it, and add it to the workspace.

        Args:
            uri (str): The document's URI.

            text (str): The raw text content of the document.

        Returns: None
        """
        text = read_file(uri)
        uri = Document.normalize_uri(uri, self.workspace_root)
        doc = Document(uri, text, self.configuration.map_objects)
        doc.parse()
        self.documents[uri] = doc

    def __load_list_item(
        self,
        sub_item_path: Path,
        base_type,
        base_type_args: tuple,
        list_element_type,
        field_name: str,
        item_dir: Path,
        external,
        list_paths: list[str],
        parent_path: Path,
        position: int,
        namespace: tuple[str, ...] = (),
        namespaced: Optional[Namespaced] = None,
    ):
        """
        Load one item from a list-folder entry, handling Union and concrete types.

        Args:
            sub_item_path (Path): Path to the file or folder for this item.
            base_type: Origin type of the list element (e.g. ``Union`` or ``None``).
            base_type_args (tuple): Generic args of ``base_type``.
            list_element_type: Declared element type of the list field.
            field_name (str): Field name on the parent model.
            item_dir (Path): Parent directory containing the list items.
            external: The ``External`` annotation for this field.
            list_paths (list[str]): Dot-path context for this item.
            parent_path (Path): Path of the parent load-node that owns the list field.
            position (int): Index this item occupies in the built list (skipped entries excluded),
                used to splice a reloaded value back into the parent.
            namespace (tuple[str, ...]): Folder names between the list root and this item, outermost first.
            namespaced (Namespaced | None): The ``Namespaced`` annotation of the list, if it has one.

        Returns:
            The loaded model instance, or ``None`` if loading failed.
        """

        link = ParentLink(parent_path, field_name, "list", position, namespace, namespaced)
        if base_type is Union or base_type is UnionType:
            item_info: dict = {}
            self.__handle_generic_types_union(
                base_type_args,
                external,
                sub_item_path.name,
                field_name,
                field_name,
                item_info,
                item_dir,
                list_paths,
                link,
            )
            if field_name not in item_info:
                logger.warning(
                    "Skipping file %s: could not be loaded as any of the expected types.",
                    str(sub_item_path),
                )
                return None
            return item_info[field_name]
        else:
            item = self._load_from_path(
                sub_item_path,
                list_element_type,
                field_name,
                list_paths,
                link,
            )
            if item is None:
                logger.warning(
                    "Skipping file %s: failed to load.",
                    str(sub_item_path),
                )
            return item

    def __handle_generic_types_list(
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
        namespaced: Optional[Namespaced] = None,
    ) -> bool:
        """
        Load an external ``list`` field from disk into ``module_load_info``.

        Iterates files/folders under the external directory for ``FOLDER`` strategy, or delegates to a single-file loader for
        ``SINGLE_FILE`` strategy.

        Args:
            base_type_args (tuple): Generic args of the list annotation.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (str): Dot-path context for object tracking.
            namespaced (Namespaced | None): When given, sub-folders of the list folder are namespaces and the
                items below them are loaded with a qualified name.

        Returns:
            bool: ``True`` if the field was handled, ``False`` otherwise.
        """

        if OutputStrategy.FOLDER in external.output_structure:
            module_load_info[field_name] = self.__load_list_folder(
                base_type_args[0],
                external,
                external_path,
                field_name,
                path,
                current_object_paths,
                namespaced,
            )
            return True
        if OutputStrategy.SINGLE_FILE in external.output_structure:
            self.__handle_generic_types_list_single_file(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
            )
            return True
        return False

    def __load_list_folder(
        self,
        list_element_type,
        external: External,
        external_path: str,
        field_name: str,
        path: Path,
        current_object_paths: list[str],
        namespaced: Optional[Namespaced],
    ) -> list:
        """
        Load every item of a ``FOLDER``-strategy list field.

        Args:
            list_element_type: Declared element type of the list field.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            path (Path): Absolute path of the current directory.
            current_object_paths (list[str]): Dot-path context for object tracking.
            namespaced (Namespaced | None): The ``Namespaced`` annotation of the list, if it has one.

        Returns:
            list: The successfully loaded items, in deterministic order.
        """

        item_dir = path / external_path
        effective_element_type = list_element_type
        if get_origin(list_element_type) is Annotated:
            effective_element_type = get_args(list_element_type)[0]
        base_type = get_origin(effective_element_type)
        element_args = get_args(effective_element_type)
        # Sorted so list indices (and therefore object ids and list order) are
        # deterministic across loads and filesystems; iterdir() order is not.
        if namespaced is not None:
            entries = list(self.__iter_namespaced_items(item_dir, (), namespaced, effective_element_type))
        else:
            entries = [(sub_item_path, ()) for sub_item_path in self.__iter_supported_paths(item_dir, effective_element_type)]

        list_item_value: list = []
        for idx, (sub_item_path, namespace) in enumerate(entries):
            list_name = self.name_form_file(sub_item_path)
            if namespaced is not None:
                list_name = namespaced.separator.join([*namespace, list_name])
            list_paths = self.add_list_item_object_path(list_name, current_object_paths, idx)
            item = self.__load_list_item(
                sub_item_path,
                base_type,
                element_args,
                list_element_type,
                field_name,
                sub_item_path.parent,
                external,
                list_paths,
                path,
                len(list_item_value),
                namespace,
                namespaced,
            )
            if item is not None:
                list_item_value.append(item)
        return list_item_value

    def __iter_supported_paths(self, directory: Path, element_type: Any):
        """
        Yield the entries of ``directory`` that belong to the active variant, in sorted order, skipping hidden ones silently.

        Entries the workspace does not support are skipped with a warning.

        Args:
            directory (Path): The folder to list.
            element_type (Any): Element type of the field the folder holds; decides which document of a sub-folder
                carries its presence condition.

        Yields:
            Path: Each hidden-filtered, supported entry.
        """

        for sub_item_path in self._variant_entries(directory, element_type):
            if not self.is_path_supported(sub_item_path):
                logger.warning(_UNRECOGNIZED_FILE_MSG, str(sub_item_path))
                continue
            yield sub_item_path

    def __iter_namespaced_items(self, directory: Path, namespace: tuple[str, ...], namespaced: Namespaced, element_type: Any):
        """
        Walk a ``Namespaced`` list folder, yielding every item file with the namespace it sits in.

        Every sub-folder adds one namespace segment. Entries are visited in sorted order so list positions and
        object ids are deterministic. Hidden entries are skipped silently, unsupported files and folders whose
        name contains the namespace separator are skipped with a warning.

        Args:
            directory (Path): The folder to walk.
            namespace (tuple[str, ...]): Namespace segments of ``directory``, outermost first.
            namespaced (Namespaced): The annotation of the list being loaded.
            element_type (Any): Element type of the list, passed on to :meth:`__iter_supported_paths`.

        Yields:
            tuple[Path, tuple[str, ...]]: An item file and the namespace segments it is stored under.
        """

        for sub_item_path in self.__iter_supported_paths(directory, element_type):
            if not sub_item_path.is_dir():
                yield sub_item_path, namespace
            elif namespaced.separator in sub_item_path.name:
                logger.warning(
                    "Skipping folder %s: a namespace folder name must not contain '%s'.",
                    str(sub_item_path),
                    namespaced.separator,
                )
            else:
                yield from self.__iter_namespaced_items(sub_item_path, (*namespace, sub_item_path.name), namespaced, element_type)

    def __handle_generic_types_list_single_file(
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
    ) -> None:
        """
        Load an external ``list`` field stored as a single file into ``module_load_info``.

        Args:
            base_type_args (tuple): Generic args of the list annotation.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (str): Dot-path context for object tracking.
        """

        effective_element_type = base_type_args[0]
        if get_origin(effective_element_type) is Annotated:
            effective_element_type = get_args(effective_element_type)[0]
        element_origin = get_origin(effective_element_type)
        if element_origin is Union or element_origin is UnionType:
            # A single-file list whose element is a union of models (a discriminated union) is
            # stored in the file itself as a bare list. Load the whole file content into the
            # field and let the parent's rebuild/validation turn it into the full list. Without
            # this branch the loader would try to match the file against each union member as a
            # single model, fail, and silently drop the field.
            self._append_to_info_dict(
                path / external_path,
                module_load_info,
                output_strategy=external.output_structure,
                field_name=field_name,
            )
        else:
            single_info: dict = {}
            self.__handle_generic_types(
                attribute_type=effective_element_type,
                base_type=get_origin(effective_element_type),
                base_type_args=get_args(effective_element_type),
                external=external,
                path=path,
                external_path=external_path,
                module_load_info=single_info,
                field_name=field_name,
                storage_key=field_name,
                current_object_paths=current_object_paths,
            )
            module_load_info.update(single_info)

    def __handle_generic_types_dict(
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
    ) -> bool:
        """
        Load an external ``dict`` field from disk into ``module_load_info``.

        Iterates items under the external directory for ``FOLDER`` strategy, or delegates to a single-file loader for ``SINGLE_FILE`` strategy.

        Args:
            base_type_args (tuple): Generic args of the dict annotation ``(key_type, value_type)``.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (list[str]): Dot-path contexts for object tracking.

        Returns:
            bool: ``True`` if the field was handled, ``False`` otherwise.
        """

        dict_item_value = {}
        dict_element_type = base_type_args[1]
        if OutputStrategy.FOLDER in external.output_structure:
            item_dir = path / external_path
            for sub_item_path in self.__iter_supported_paths(item_dir, dict_element_type):
                key = sub_item_path.name
                dict_item_value[key] = self._load_from_path(
                    sub_item_path,
                    dict_element_type,
                    field_name,
                    self.update_objects_path(current_object_paths, key),
                    ParentLink(path, field_name, "dict", key),
                )
            module_load_info[field_name] = dict_item_value
            return True
        if OutputStrategy.SINGLE_FILE in external.output_structure:
            new_base_type = base_type_args[1]
            dict_info: dict = {}
            self.__handle_generic_types(
                attribute_type=new_base_type,
                base_type=get_origin(new_base_type),
                base_type_args=get_args(new_base_type),
                external=external,
                path=path,
                external_path=external_path,
                module_load_info=dict_info,
                field_name=field_name,
                storage_key=field_name,
                current_object_paths=current_object_paths,
            )
            module_load_info.update(dict_info)
            return True
        return False

    def __try_load_union_type(
        self,
        path: Path,
        external_path: str,
        possible_type,
        field_name: str,
        current_object_paths: list[str],
        link: Optional[ParentLink] = None,
        keep_diags: bool = False,
        sole_member: bool = False,
    ):
        """
        Attempt to load one union member type, restoring diagnostics on failure.

        A failed attempt usually means "wrong union member", so its purely structural diagnostics are discarded and the
        caller tries the next member; the same goes for an optional file or folder that does not exist. When the member is
        the only type the field can hold (an ``Optional[Model]`` field) and its file or folder exists, no other member can
        match: the document was meant to be that model, so every diagnostic of the failed attempt is kept instead of the
        field silently becoming ``None``.

        Args:
            path (Path): Absolute path of the current directory.
            external_path (str): Relative path segment for this field.
            possible_type: The union member type to attempt.
            field_name (str): Field name on the parent model.
            current_object_paths (list[str]): Dot-path contexts for object tracking.
            link (ParentLink | None): How the loaded value attaches to its parent.
            keep_diags (bool): Keep the diagnostics of a failed attempt. Set for a plain
                ``Optional[SingleType]`` where there is no other member to fall back to,
                so a failure is a real error and not a "wrong union member" signal.
                A path that does not exist is still discarded: an absent optional file is not an error.
            link (ParentLink | None): How the loaded value attaches to its parent.
            sole_member (bool): Whether ``possible_type`` is the only type of the union besides ``None``.

        Returns:
            The loaded model instance, or ``None`` if the type did not match.
        """

        attempt_path = (path / external_path).absolute()
        doc_id = self.document_id_from_path(attempt_path)
        diags_existed = doc_id in self.documents_diags
        saved_diags = list(self.documents_diags.get(doc_id, []))
        saved_count = len(saved_diags)
        result = self._load_from_path(
            path / external_path,
            possible_type,
            field_name,
            current_object_paths,
            link,
        )
        if result is None and not (sole_member and attempt_path.exists()):
            new_diags = self.documents_diags.get(doc_id, [])[saved_count:]
            # If the failed attempt produced a user-raised semantic error
            # (err_major / err_minor / err_fatal on the matched type), keep
            # the diags so the user sees them. Discard only purely structural
            # mismatches, which signal "wrong union member".
            has_semantic_error = any(is_semantic_validation_error(d) for d in new_diags)
            if keep_diags and attempt_path.exists() and new_diags and not has_semantic_error:
                # Same wording/shape as ``validate_or_remove`` (minor): one summary error, raw details in ``sub_errors``.
                self.documents_diags[doc_id] = saved_diags + [self.__summarize_failed_load(field_name, new_diags)]
            elif not has_semantic_error:
                if diags_existed:
                    self.documents_diags[doc_id] = saved_diags
                elif doc_id in self.documents_diags:
                    del self.documents_diags[doc_id]
        return result

    @staticmethod
    def __summarize_failed_load(field_name: str, diags: list[ErrorDetails]) -> ErrorDetails:
        """
        Collapse the raw diagnostics of a failed single-type load into one ``minor`` error.

        The message matches :func:`~flync.core.validators.generic.validate_or_remove` and the individual
        errors (e.g. ``Extra inputs are not permitted``) are listed in ``ctx["sub_errors"]``.
        """

        first_ctx = (diags[0].get("ctx") or {}) if diags else {}
        yaml_path = first_ctx.get("yaml_path")
        location = f"in {yaml_path}" if yaml_path else "in system"
        ctx: dict[str, Any] = {k: first_ctx[k] for k in ("yaml_path", "line", "col") if k in first_ctx}
        ctx["sub_errors"] = "\n".join(f"{'.'.join(str(x) for x in d.get('loc', ()))}: {d.get('msg', '')}" for d in diags)
        return ErrorDetails(
            type="minor",
            msg=f"1 or more errors found while validating {field_name}. Removing {field_name} {location}.",
            loc=(field_name,),
            input=None,
            ctx=ctx,
            url="",
        )

    def __handle_generic_types_union(
        self,
        base_type_args: tuple,
        external,
        external_path: str,
        field_name: str,
        storage_key: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
        link: Optional[ParentLink] = None,
        namespaced: Optional[Namespaced] = None,
    ) -> bool:
        """
        Attempt to load an external ``Union`` field by trying each member type.

        Iterates through the union's member types and loads the first one that succeeds. ``NoneType`` members are skipped.

        Args:
            base_type_args (tuple): The union member types.
            external: The ``External`` annotation for this field.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            storage_key (str): The key under which the successfully loaded field value.
            Typically corresponds to the field name or its alias.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (list[str]): Dot-path contexts for object tracking.
            link (ParentLink | None): How the loaded value attaches to its parent.
            namespaced (Namespaced | None): Forwarded to the member loaders, e.g. for ``Optional[List[...]]``.

        Returns:
            bool: ``True`` if at least one union member loaded successfully.
        """

        success_union = False
        # Optional[X] has a single real member: nothing else to try, so its errors must surface.
        sole_member = sum(1 for t in base_type_args if t is not type(None)) == 1
        for possible_type in base_type_args:
            try:
                if possible_type is type(None):
                    # optional external field, don't do anything
                    continue
                possible_base_type = get_origin(possible_type)
                if issubclass(possible_base_type or possible_type, FLYNCBaseModel):
                    result = self.__try_load_union_type(
                        path,
                        external_path,
                        possible_type,
                        field_name,
                        current_object_paths,
                        link,
                        keep_diags=sole_member,
                        sole_member=sole_member,
                    )
                    if result is None:
                        continue
                    module_load_info[storage_key] = result
                else:
                    self.__handle_generic_types(
                        possible_type,
                        possible_base_type,
                        get_args(possible_type),
                        external,
                        path,
                        external_path,
                        module_load_info,
                        field_name,
                        storage_key,
                        current_object_paths,
                        namespaced,
                    )
                success_union = True
                break
            # A failed member load means "wrong union member" -- try the next one.
            except (TypeError, ValueError, KeyError, AttributeError, OSError):
                continue
        return success_union

    def __handle_generic_types(
        self,
        attribute_type: type,
        base_type: object,
        base_type_args: tuple,
        external: External,
        path: Path,
        external_path: str,
        module_load_info: dict,
        field_name: str,
        storage_key: str,
        current_object_paths: list[str],
        namespaced: Optional[Namespaced] = None,
    ):
        """
        Dispatch an external field to the correct type-specific loader.

        Routes ``list``, ``dict``, and ``Union`` types to their dedicated handlers.
        Falls through to a direct model load for concrete ``FLYNCBaseModel`` subclasses, or does nothing for optional fields whose value is absent.

        Args:
            attribute_type (type): The full (possibly generic) annotation type.
            base_type (object): The ``get_origin`` of ``attribute_type``, or ``None`` for non-generic types.
                Not narrowed to ``type``: ``get_origin`` also yields typing special forms such as ``Union``.
            base_type_args (tuple): The ``get_args`` of ``attribute_type``.
            external (External): Annotation controlling load strategy.
            path (Path): Absolute path of the current directory.
            external_path (str): Relative path segment for this field.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            field_name (str): Field name on the parent model.
            current_object_paths (str): Dot-path context(s) for object tracking.
            namespaced (Namespaced | None): The ``Namespaced`` annotation of the field, if any; only list fields use it.

        Raises:
            ValueError: If the field type is not supported for external loading.
        """

        done = False
        scalar_link = ParentLink(path, field_name, "scalar")

        if base_type is list:
            done = self.__handle_generic_types_list(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
                namespaced,
            )

        elif base_type is dict:
            done = self.__handle_generic_types_dict(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
            )

        elif base_type is Union or base_type is UnionType:
            done = self.__handle_generic_types_union(
                base_type_args,
                external,
                external_path,
                field_name,
                storage_key,
                module_load_info,
                path,
                current_object_paths,
                scalar_link,
                namespaced,
            )

        if not done and type(None) in base_type_args:
            # optional type
            done = True

        if done:
            # this field might not have been added to the objects since it's
            # not a flync model and has no document. Add it manually.
            doc_id = self.document_id_from_path(path / external_path if external_path else path)
            self._add_object_to_path(
                doc_id=doc_id,
                model=(module_load_info[field_name] if field_name in module_load_info else None),
                current_object_paths=current_object_paths,
                start_line=0,
                end_line=0,
                end_column=0,
                start_column=0,
            )
            return

        if not issubclass(get_origin(attribute_type) or attribute_type, FLYNCBaseModel):
            raise ValueError(f"externally annotated field {field_name} cannot be loaded")

        module_load_info[field_name] = self._load_from_path(
            path / external_path,
            attribute_type,
            field_name,
            current_object_paths,
            scalar_link,
        )

    def _load_from_path(
        self,
        path: PathType,
        current_type: Optional[type[FLYNCBaseModel]] = None,
        current_type_name: Optional[str] = None,
        current_object_paths: Optional[list[str]] = None,
        link: Optional[ParentLink] = None,
    ) -> FLYNCBaseModel | None:
        """
        Load and validate a model from a filesystem path.

        Recursively processes all fields of ``current_type``, routing external fields to their files/directories and collecting implied values.
        After gathering all field data it validates the dict against the type and updates the workspace's object and diagnostic stores.

        Args:
            path (PathType): Directory (or file) path to load from.
            current_type (type[FLYNCBaseModel] | None): The expected model type. Defaults to the workspace's configured root model.
            current_type_name (str | None): The parent field name for this type, used to reconstruct the correct validation type.
            current_object_paths (list[str] | None): Dot-path context(s) for object tracking.

        Returns:
            FLYNCBaseModel | None: The validated model instance, or ``None`` if validation failed.
        """

        # if no type is passed, then this is the starting point
        if current_type is None:
            current_type = self.configuration.root_model
        model_force_rebuild(current_type)
        if isinstance(path, str):
            path = Path(path)
        if not current_object_paths:
            current_object_paths = [""]
        path = path.absolute()
        doc_id = self.document_id_from_path(path)
        if link is not None and not self._entry_present(path, current_type):
            # a file whose root variant_condition is false, or a folder whose presence document removes it
            return None
        self._doc_index[doc_id] = LoadNode(
            path=path,
            doc_id=doc_id,
            current_type=current_type,
            current_type_name=current_type_name,
            object_paths=list(current_object_paths),
            link=link,
        )
        module_load_info: dict = {}
        # a root load first loads the variability model and selects the variant everything else is resolved for
        is_root = link is None
        if is_root and not self._load_variability(path, current_type, current_object_paths, module_load_info):
            self._finalize_variability_diags()
            return None
        # start by loading each field; a root load has already loaded the variability model
        skipped = VARIABILITY_FIELD if is_root else None
        for field_name, field_info in current_type.model_fields.items():
            if field_name != skipped:
                self.__load_field(path, current_object_paths, module_load_info, field_name, field_info)

        # then group all the fields into the same object and return it
        self._append_to_info_dict(path, module_load_info)
        if link is not None and link.namespaced is not None and link.namespace:
            module_load_info = qualify_name(module_load_info, link.namespace, link.namespaced)

        if doc_id in self.documents_diags:
            logger.error("File %s was already loaded.", doc_id)
        model = self._validate_node(self._doc_index[doc_id], module_load_info, map_paths=current_object_paths)
        if is_root:
            self._stamp_active_variant(model)
            self._finalize_variability_diags()
        return model

    def __load_field(self, path: Path, current_object_paths: list[str], module_load_info: dict, field_name: str, field_info: FieldInfo) -> None:
        """Load one field of the model at ``path`` into ``module_load_info``: from its own document(s), or implied by the path."""

        external: External | None = get_metadata(field_info.metadata, External)
        self.__handle_external_field_load(
            path,
            current_object_paths,
            module_load_info,
            field_name,
            field_info,
            external,
        )
        if implied := get_metadata(field_info.metadata, Implied):
            self._handle_implied_field_load(path, module_load_info, field_name, implied)
            # Implied fields carry no YAML node and no model value of their
            # own, so the AST walk never registers them. Register a marker
            # object (model=None) under the linked path; without it
            # get_child_ids would drop the field, since it filters children
            # by has_object().
            paths = self.update_objects_path(current_object_paths, field_name)
            self._add_object_to_path("", None, paths, 0, 0, 0, 0)

    def _load_variability(
        self,
        path: Path,
        current_type: type[FLYNCBaseModel],
        current_object_paths: list[str],
        module_load_info: dict,
    ) -> bool:
        """
        Load the variability model of a root load and select the variant to resolve.

        For the FLYNC root model the ``variability/`` folder is loaded into ``module_load_info`` before any other field. A
        validated sub-node (e.g. one ECU folder) is resolved with the variability of its enclosing workspace.

        Returns:
            bool: ``False`` when the workspace declares variants but none can be resolved; the load stops.
        """

        self._begin_variant_load()
        if issubclass(current_type, Variability):
            # the variability model itself is never resolved
            return True
        present, variability = self._locate_variability(path, current_type, current_object_paths, module_load_info)
        return self._activate_variability(present, variability)

    def _locate_variability(
        self,
        path: Path,
        current_type: type[FLYNCBaseModel],
        current_object_paths: list[str],
        module_load_info: dict,
    ) -> tuple[bool, Optional[Variability]]:
        """
        Find and load the variability model that applies to ``path``; returns whether there is one, and the model.

        Also records the root of the workspace it belongs to, which decides the role of every document (see
        :meth:`_document_role`).
        """

        field_info = current_type.model_fields.get(VARIABILITY_FIELD)
        external = get_metadata(field_info.metadata, External) if field_info is not None else None
        if field_info is not None and external is not None:
            present = (path / VARIABILITY_FOLDER).is_dir()
            if present:
                self._variability_root = path
                self.__handle_external_field_load(path, current_object_paths, module_load_info, VARIABILITY_FIELD, field_info, external)
            return present, module_load_info.get(VARIABILITY_FIELD) if present else None
        folder = self._find_variability_folder(path)
        if folder is None:
            return False, None
        self._variability_root = folder.parent
        return True, self._load_enclosing_variability(folder)

    def _load_enclosing_variability(self, folder: Path) -> Optional[Variability]:
        """Load the ``variability/`` folder of the workspace enclosing a validated sub-node."""

        from flync.sdk.context.workspace_config import WorkspaceConfiguration

        config = WorkspaceConfiguration.create_from_config(self.configuration, root_model=Variability, map_objects=False)
        workspace = cast(Any, type(self)).safe_load_workspace("variability", folder, workspace_config=config)
        return workspace.flync_model if isinstance(workspace.flync_model, Variability) else None

    def _handle_implied_field_load(
        self,
        path: Path,
        module_load_info: dict,
        field_name: str,
        implied: Implied,
    ):
        """Fill ``field_name`` from the name of the folder or file being loaded, as the ``Implied`` strategy says."""

        if implied.strategy == ImpliedStrategy.FOLDER_NAME:
            module_load_info[field_name] = path.name
        elif implied.strategy == ImpliedStrategy.FILE_NAME:
            module_load_info[field_name] = self.name_form_file(path)

    def __handle_external_field_load(
        self,
        path: Path,
        current_object_paths: list[str],
        module_load_info: dict,
        field_name: str,
        field_info_obj: FieldInfo,
        external: External | None,
    ) -> None:
        """Load the field stored in a separate document (an ``External`` field) into ``module_load_info``."""

        if external is not None:
            # field will need to be added to to a new separate document
            attribute_type = field_info_obj.annotation
            if attribute_type is None:
                raise ValueError("Attribute {} has an invalid type.", field_name)
            base_type: type | None = get_origin(attribute_type)
            base_type_args = get_args(attribute_type)
            storage_key = field_name
            external_path = self.__get_external_path(path, external, field_name)
            if not external_path.exists() and field_info_obj.alias is not None:
                external_path = self.__get_external_path(path, external, field_info_obj.alias)
                storage_key = field_info_obj.alias
            if OutputStrategy.SINGLE_FILE in external.output_structure:
                if OutputStrategy.OMMIT_ROOT not in external.output_structure:
                    # the output file is a dictionary
                    # we need to load it accordingly
                    attribute_type = dict[str, attribute_type]  # type: ignore[valid-type]
                    base_type = get_origin(attribute_type)
                    base_type_args = get_args(attribute_type)
            new_paths = self.update_objects_path(current_object_paths, field_name)
            namespaced = get_metadata(field_info_obj.metadata, Namespaced)
            self.__handle_generic_types(
                cast(type, attribute_type),
                base_type,
                base_type_args,
                external,
                path,
                str(external_path),
                module_load_info,
                field_name,
                storage_key,
                new_paths,
                namespaced,
            )

    def _append_to_info_dict(
        self,
        path: Path,
        model_load_info: dict,
        output_strategy: Optional[OutputStrategy] = None,
        field_name: Optional[str] = None,
        fixed_name: Optional[str] = None,
    ):
        """
        Merge the contents of a FLYNC file into a model load-info dict.

        Opens the file at ``path``, registers it as a document, and merges its parsed YAML content into ``model_load_info``.
        The merge behavior depends on ``output_strategy``:

        - ``OMMIT_ROOT``: assigns the raw content to ``model_load_info[field_name]``.
        - ``FIXED_ROOT``: assigns only the ``fixed_name`` key of the content.
        - Default: updates ``model_load_info`` with all top-level keys.

        Does nothing when ``path`` is not a file or is not a recognized FLYNC file extension.

        Args:
            path (Path): Path to the FLYNC YAML file.
            model_load_info (dict): Accumulator dict; updated in place.
            output_strategy (OutputStrategy | None): Optional output strategy that controls how the file content is merged.
            field_name (str | None): Target key in ``model_load_info`` for ``OMMIT_ROOT`` / ``FIXED_ROOT`` strategies.
            fixed_name (str | None): Key inside the file content to extract for ``FIXED_ROOT`` strategy.
        """

        if not path.is_file():
            return

        if not self.is_flync_file(path):
            logger.error("trying to load an unsupported file: %s", str(path))
            return

        uri: str = self.document_id_from_path(path)
        if uri not in self.documents:
            self._open_document(path)
        # a copy resolved for the active variant: validation prunes it, the parsed document stays intact
        content = self._document_content(uri)
        if content is None or content is ABSENT:
            return

        if output_strategy and OutputStrategy.OMMIT_ROOT in output_strategy:
            model_load_info[field_name] = content
        elif output_strategy and OutputStrategy.FIXED_ROOT in output_strategy:
            model_load_info[field_name] = content[fixed_name]
        else:
            model_load_info.update(content)

    def __get_external_path(self, base_path: Path, external: External, field_name: str) -> Path:
        """
        Resolve the filesystem path for an external field.

        Constructs the path to an external file or directory based on the provided `External` configuration and naming strategy.
        If the `External` specifies a fixed path, that path is used; otherwise, the field name is used as the base.
        A file extension is appended if the output structure requires a single file.

        Args:
            base_path (Path): The root directory path where external files are located.
            external (External): The external configuration annotation for the field.
            field_name (str): The name of the field on the parent model.

        Returns:
            Path: The resolved absolute path to the external resource.
        """
        ext = self.configuration.flync_file_extension if OutputStrategy.SINGLE_FILE in external.output_structure else ""
        path = external.path if ((external.naming_strategy == NamingStrategy.FIXED_PATH) and (external.path is not None)) else field_name
        return base_path / (path + ext)

    def _validate_node(self, node: LoadNode, module_load_info: dict, map_paths: Optional[list[str]] = None):
        """
        Validate ``module_load_info`` for ``node`` the same way the initial load does.

        Resets the node's diagnostics, applies the parent-aware type rebuild/normalization, records any
        validation errors against the node's document id and stores the result on ``node.model``.

        Args:
            node (LoadNode): The node being (re)validated.
            module_load_info (dict): The gathered field data to validate.
            map_paths (list[str] | None): When object mapping is enabled and these paths are given, the
                freshly validated model is registered in the object map under them. Left ``None`` for
                ancestor rebuilds, where the object map is maintained separately.

        Returns:
            The validated (and parent-normalized) model, or ``None`` on failure.
        """

        self.documents_diags[node.doc_id] = []
        if not module_load_info:
            node.model = None
            return None
        original_type = node.current_type
        current_type = node.current_type
        try:
            if node.current_type_name:
                current_type = self.model_graph.rebuild_type_from_parent(current_type, node.current_type_name)
            relative_path = node.path.relative_to(self.workspace_root.absolute())  # type: ignore[union-attr]
            model, errors = validate_with_policy(current_type, module_load_info, relative_path.as_posix())
            self._locate_node_errors(node, current_type, errors)
            self.documents_diags[node.doc_id].extend(errors)
            if map_paths is not None and self.configuration.map_objects:
                self._update_objects(node.doc_id, model, map_paths, parent_name=node.current_type_name)
            if node.current_type_name:
                model = self.model_graph.normalize_child_to_parent(original_type, node.current_type_name, model)
            node.model = model
            return model
        except ValidationError as e:
            errors = e.errors()
            self._locate_node_errors(node, current_type, errors)
            self.documents_diags[node.doc_id].extend(errors)
            node.model = None
            return None

    def _locate_node_errors(self, node: LoadNode, model_type, errors: list) -> None:
        """
        Resolve the YAML line/column of ``errors`` against the source of ``node``'s document.

        Validation runs on safe-loaded data without source marks, so positions are looked up in the document's composed node tree. The tree is only
        composed here, for documents that have errors.
        """

        if not errors:
            return
        document = self.documents.get(node.doc_id)
        if document is None:
            return
        locate_errors(errors, model_type, self._source_nodes(node.doc_id))
