"""
Workspace module for FLYNC SDK.

Provides classes and functions to manage workspace operations.
"""

import logging
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain, islice
from pathlib import Path
from typing import Annotated, Dict, Literal, Optional, Union, cast, get_args, get_origin

import yaml
from pydantic import RootModel
from pydantic.fields import FieldInfo
from pydantic_core import ErrorDetails, ValidationError
from ruamel.yaml.nodes import MappingNode, Node, SequenceNode
from typing_extensions import deprecated

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.annotations.reference import resolve_reference
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions_handling import (
    errors_to_init_errors,
    get_name_by_alias,
    is_semantic_validation_error,
    validate_with_policy,
)
from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import (
    ListObjectsMode,
    WorkspaceConfiguration,
)
from flync.sdk.utils.field_utils import (
    get_metadata,
    get_name,
)
from flync.sdk.utils.model_dependencies import (
    ModelDependencyGraph,
    get_model_dependency_graph,
    model_force_rebuild,
)
from flync.sdk.utils.model_dumper import dump_model_with_discriminators
from flync.sdk.utils.sdk_types import PathType

from .document import Document, parse_documents, read_file
from .ids import ObjectId
from .objects import ObjectMetadata, SemanticObject
from .source import SourceRef, get_range

logger = logging.getLogger(__name__)


@dataclass
class ParentLink(object):
    """
    Records where a loaded node hangs off its parent so a reloaded value can be put back in place.

    This is captured while the workspace loads. When a single document later changes we re-validate
    just that node and use this link to splice the fresh value into the parent model, instead of
    rebuilding the whole tree.

    Attributes:
        parent_path (Path): Absolute path of the parent load-node (a file or a directory).
        field_name (str): Python field name on the parent model that holds this value.
        container (Literal["scalar", "list", "dict"]): How the value sits on that field. ``"scalar"`` is a
            plain field (e.g. an ECU's ``ports`` file or its ``topology``); ``"list"``/``"dict"`` are
            folder-based collections whose items load from separate documents.
        key (int | str | None): List index or dict key of this value; ``None`` for scalar fields.
    """

    parent_path: Path
    field_name: str
    container: Literal["scalar", "list", "dict"]
    key: int | str | None = None


@dataclass
class LoadNode(object):
    """
    Everything needed to reload one document on its own, i.e. one ``__load_from_path`` call.

    Attributes:
        path (Path): Absolute path (file or directory) this node was loaded from.
        doc_id (str): Workspace-relative id; matches the keys of ``FLYNCWorkspace.documents``.
        current_type (type): The model type this node was validated against.
        current_type_name (str | None): Parent field name, used to rebuild the effective validation type.
        object_paths (list[str]): The object-path context this node was registered under.
        link (ParentLink | None): How this node attaches to its parent; ``None`` for the root node.
        model: The last successfully loaded value for this node, or ``None`` if it failed to load.
    """

    path: Path
    doc_id: str
    current_type: type[FLYNCBaseModel]
    current_type_name: Optional[str]
    object_paths: list[str]
    link: Optional[ParentLink] = None
    model: object = None


class FLYNCWorkspace(object):
    """
    Workspace class managing documents, objects, and diagnostics.

    This class provides methods to ingest documents, run analysis, and expose semantic and source APIs for use by the SDK and language server.

    Attributes:
        name (str): Name of the workspace.

        configuration (WorkspaceConfiguration): Configuration object for workspace behavior.

        documents (Dict[str, Document]): Mapping of document URIs to Document objects.

        documents_diags (Dict[str, list[ErrorDetails]]): Validation errors indexed by document URI.

        objects (Dict[ObjectId, SemanticObject]): Semantic objects indexed by ObjectId.

        sources (Dict[ObjectId, SourceRef]): Source references indexed by ObjectId.

        flync_model (FLYNCModel | FLYNCBaseModel | None): The root FLYNC model instance, if loaded.

        workspace_root (Path | None): Absolute path to the workspace root directory.
    """

    def __init__(  # noqa # nosonar
        self,
        name: str,
        workspace_path: PathType = "",
        configuration: WorkspaceConfiguration | None = None,
    ):  # noqa # nosonar
        """
        Initialize the workspace.

        Args:
            name (str): Human-readable name for this workspace instance.
            workspace_path (PathType): Absolute path to the workspace root directory. An empty string raises :class:`ValueError`.
            configuration (WorkspaceConfiguration | None): Optional configuration object.
                When ``None``, a default :class:`~flync.sdk.context.workspace_config.WorkspaceConfiguration` is used.
        """

        if not name:
            raise ValueError(
                "Passed an invalid value for workspace name {}",
                name,
            )
        self.name = name
        self.configuration = configuration or WorkspaceConfiguration()
        self.model_graph: ModelDependencyGraph = get_model_dependency_graph(self.configuration.root_model)
        # documents
        self.documents: Dict[str, Document] = {}
        self.documents_diags: Dict[str, list[ErrorDetails]] = {}
        # semantic graph
        self.objects: Dict[ObjectId, SemanticObject] = {}
        self.sources: Dict[ObjectId, SourceRef] = {}
        # root information (if any)
        self.flync_model: Optional[FLYNCModel | FLYNCBaseModel] = None
        self.workspace_root: Optional[Path] = None
        if not workspace_path:
            raise ValueError(
                "Passed an invalid value for workspace root {}",
                workspace_path,
            )
        self.workspace_root = Path(workspace_path).absolute()
        self._model_to_object_ids: dict[int, list[ObjectId]] = {}
        # Immediate-parent object-id -> ordered immediate child ids, recorded as
        # child paths are built during load (parent + separator + segment) so
        # child lookups never destructure the dot-separated id. ``_linked_child_ids``
        # dedups so a child is registered under its parent at most once.
        self._children_by_parent: dict[str, list[str]] = {}
        self._linked_child_ids: set[str] = set()
        # Mapping of canonical ObjectId → list of duplicate ObjectIds.
        # Keys represent the chosen canonical identifier, while values hold all alternative IDs
        # that refer to the same logical object.
        self._duplicated_objects_ids: dict[ObjectId, list[ObjectId]] = {}
        # document id -> LoadNode, built during load so update_document can
        # partially reload a single document instead of the whole workspace.
        self._doc_index: dict[str, LoadNode] = {}

    @property
    def load_errors(self):
        """
        Flattened list of all validation errors across all loaded documents.

        Returns:
            list[ErrorDetails]: All per-document errors concatenated into a
            single list.
        """

        return [error for doc_errors in self.documents_diags.values() for error in doc_errors]

    # region creator
    @classmethod
    def load_model(
        cls,
        flync_model: FLYNCModel,
        workspace_name: str | None = "generated_workspace",
        file_path: PathType = "",
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a FLYNC Object.

        Args:
            flync_model (str): the FLYNC object from which the workspace will be created.

            workspace_name (str): The name of the workspace.

            file_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """  # noqa

        if not workspace_name:
            workspace_name = "generated_workspace"
        output = FLYNCWorkspace(
            name=workspace_name,
            workspace_path=file_path,
            configuration=workspace_config,
        )
        # assign this to the workspace if it's the root object
        output.flync_model = flync_model
        output.load_flync_model(flync_model, file_path)
        return output

    @classmethod
    def safe_load_workspace(
        cls,
        workspace_name: str,
        workspace_path: PathType,
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a location of the Yaml Configuration.

        In case this fails, the workspace will still be created, but with an empty model.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """

        output = FLYNCWorkspace(
            name=workspace_name,
            workspace_path=workspace_path,
            configuration=workspace_config,
        )
        output._open_documents()
        model = output.__load_from_path(output.workspace_root)  # type: ignore[arg-type]

        if not isinstance(model, FLYNCBaseModel):
            logger.error("Unable to load the workspace %s", workspace_path)
        output.flync_model = model
        return output

    @classmethod
    def load_workspace(
        cls,
        workspace_name: str,
        workspace_path: PathType,
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a location of the Yaml Configuration.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """

        output = FLYNCWorkspace.safe_load_workspace(workspace_name, workspace_path, workspace_config=workspace_config)
        if not isinstance(output.flync_model, FLYNCBaseModel):
            raise ValidationError.from_exception_data(
                title=f"Model ({workspace_name}) Creation Error",
                line_errors=errors_to_init_errors(output.load_errors),
            )
        return output

    # endregion
    # region ingestion

    def _open_documents(self):
        """
        Open all documents in the workspace matching the configured file extension.
        File I/O and YAML parsing happen inside the ProcessPool workers; the raw text
        is NOT returned through IPC to reduce pickle overhead — it is re-read from the
        OS page cache in the main process for Document construction.

        Returns:
            None
        """
        if self.workspace_root is None:
            return
        files = [p for p in self.workspace_root.rglob(f"*{self.configuration.flync_file_extension}") if p.is_file()]
        if len(files) == 0:
            return

        def batched(iterable, size):
            """Yield successive batches of given size from an iterable."""
            i = iter(iterable)
            while batch := list(islice(i, size)):
                yield batch

        workers = os.cpu_count() or 1
        batch_size = max(32, len(files) // (workers * 4))
        batches = list(batched(files, batch_size))

        # A forking ProcessPoolExecutor is unsafe here: load_workspace is driven from
        # asyncio.to_thread(...), so the default POSIX "fork" start method forks from a
        # multi-threaded process and can deadlock the child. Use a non-fork context
        # (forkserver on POSIX, spawn elsewhere); everything submitted (module-level
        # parse_document, path/str/bool args) is picklable, so this is behaviour-neutral.
        mp_context = multiprocessing.get_context("forkserver" if sys.platform != "win32" else "spawn")
        with ProcessPoolExecutor(mp_context=mp_context) as pool:
            futures = [
                pool.submit(
                    parse_documents,
                    batch,
                    self.workspace_root,
                    self.configuration.map_objects,
                )
                for batch in batches
            ]

            for future in as_completed(futures):
                for uri, ast, compose_ast in future.result():
                    text = read_file(self.workspace_root / uri)
                    doc = Document(uri, text, self.configuration.map_objects)
                    doc.assign_ast(ast, compose_ast)
                    self.documents[doc.uri] = doc

    def _open_document(self, uri: PathType):  # noqa # nosonar
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

    def load_flync_model(self, flync_model: FLYNCBaseModel, file_path: PathType = ""):  # noqa # nosonar  # noqa # nosonar
        """
        Load a FLYNCModel into the workspace.

        This is a placeholder implementation that stores the model for later
        use.
        """

        if isinstance(file_path, str):
            file_path = Path(file_path)
        content = self.__get_model_content(flync_model, file_path)
        self.__save_content_to_file(file_path, content)

    def __save_content_to_file(self, file_path: Path, content):  # noqa # nosonar  # noqa # nosonar
        """
        Persist serialized model content as a Document in the workspace.

        Resolves the full URI under the workspace root, creates a :class:`~flync.sdk.workspace.document.Document` for it, and calls
        :meth:`generate_configs` to write it to disk. Does nothing when ``content`` is empty (e.g. all fields were external).

        Args:
            file_path (Path): Relative path (without extension) for the file.
            content: The serialized content to write; may be a ``dict``, a ``list``, or a plain string.
        """

        if not content:
            # everything in the object was external,
            # no need to create a document
            return
        if not self.workspace_root:
            raise ValueError("Unable to save contents in a workspace, the workspace root is not defined.")  # noqa
        uri = self.workspace_root / file_path.with_suffix(self.configuration.flync_file_extension)
        doc = Document(uri, content, self.configuration.map_objects)
        self.documents[str(uri)] = doc
        self.generate_configs(uri)

    def __get_model_content(self, flync_model: FLYNCBaseModel, file_path):  # noqa # nosonar  # noqa # nosonar
        """
        Serialize a model to a dict, routing external fields to separate documents.

        Iterates over the model's fields.
        Fields annotated with :class:`~flync.core.annotations.External` are excluded from the returned dict and handled recursively.
        Fields with :class:`~flync.core.annotations.
        Implied` ``FOLDER_NAME`` strategy are also excluded (their value is inferred from the directory name at load time).

        Args:
            flync_model (FLYNCBaseModel): The model instance to serialize.
            file_path (Path): The base file path used when routing external fields.

        Returns:
            dict: The serialized content with external and implied fields excluded.
        """

        exclude = set()
        for field_name, field_info in type(flync_model).model_fields.items():
            external: External | None = get_metadata(field_info.metadata, External)
            if external is not None:
                exclude.add(field_name)
                # field will need to be added to to a new separate document
                flync_attribute = getattr(flync_model, field_name)
                self.__handle_load_external_types(file_path, flync_attribute, external, field_name)
                continue
            implied: Implied | None = get_metadata(field_info.metadata, Implied)
            if implied is not None and implied.strategy in (
                ImpliedStrategy.FOLDER_NAME,
                ImpliedStrategy.FILE_NAME,
            ):
                exclude.add(field_name)

        content = dump_model_with_discriminators(flync_model, exclude=exclude, exclude_unset=self.configuration.exclude_unset)
        return content

    def __handle_load_external_types(  # noqa # nosonar
        self,
        file_path: Path,
        flync_attribute,
        external: External,
        field_name: str,
    ):  # noqa # nosonar
        """
        Dispatch an external field value to the correct save handler.

        Determines the output path from the :class:`~flync.core.annotations.External`
        naming strategy, then delegates to the appropriate handler based on
        whether the attribute is a list, dict, or a :class:`FLYNCBaseModel`.

        Args:
            file_path (Path): Base path of the parent document.
            flync_attribute: The field value to save externally.
            external (External): The ``External`` annotation controlling naming and output structure.
            field_name (str): The field name, used as the default path when ``FIELD_NAME`` strategy is active.

        Raises:
            ValueError: If no valid external path can be determined or the attribute type is not supported.
        """

        if flync_attribute is None or not flync_attribute:
            # none field, do nothing
            return
        if external.naming_strategy == NamingStrategy.FIXED_PATH and external.path is not None:
            external_path = external.path
        elif external.naming_strategy == NamingStrategy.FIELD_NAME:
            external_path = field_name
        else:
            raise ValueError("Unable to find an external path for {}", field_name)
        next_path = file_path / external_path
        if isinstance(flync_attribute, list):
            self.__handle_load_external_types_list(flync_attribute, external, next_path, field_name)
        elif isinstance(flync_attribute, dict):
            self.__handle_load_external_types_dict(flync_attribute, external, next_path)
        elif isinstance(flync_attribute, FLYNCBaseModel):
            if OutputStrategy.SINGLE_FILE in external.output_structure and OutputStrategy.OMMIT_ROOT not in external.output_structure:
                content = self.__get_model_content(flync_attribute, next_path)
                self.__save_content_to_file(next_path, {field_name: content})
            else:
                self.load_flync_model(flync_attribute, next_path)
        else:
            raise ValueError("Unable to load object {} from flync object", field_name)

    def __handle_load_external_types_list(  # noqa # nosonar
        self,
        flync_attribute: list,
        external: External,
        next_path: Path,
        field_name: str,
    ):  # noqa # nosonar
        """
        Save a list of external model instances to their output locations.

        When ``output_structure`` is ``SINGLE_FILE``, all items are serialized into a single file.
        Otherwise each item is written to its own file named after its ``name`` attribute (or the implied file-name field).

        Args:
            flync_attribute (list): The list of model instances to persist.
            external (External): The ``External`` annotation for this field.
            next_path (Path): The resolved output directory path.
            field_name (str): The field name, used as the key when writing a combined single-file output.
        """

        list_content = []
        for attr in flync_attribute:
            if OutputStrategy.SINGLE_FILE in external.output_structure:
                list_content.append(self.__get_model_content(attr, next_path))
            else:
                self.load_flync_model(
                    attr,
                    next_path / get_name(attr, self.__get_field_filename(attr)),
                )
        if len(list_content) != 0:
            self.__save_content_to_file(next_path, {field_name: list_content})

    def __handle_load_external_types_dict(self, flync_attribute: dict, external: External, next_path: Path):  # noqa # nosonar  # noqa # nosonar
        """
        Save a dict of external model instances to their output locations.

        When ``output_structure`` is ``SINGLE_FILE``, all values are aggregated into a single file keyed by their original dict keys.
        Otherwise each value is written to its own file named after its key.

        Args:
            flync_attribute (dict): The dict of model instances to persist.
            external (External): The ``External`` annotation for this field.
            next_path (Path): The resolved output directory path.
        """

        dict_content = {}
        for attr_name, attr_value in flync_attribute.items():
            if external.output_structure == OutputStrategy.SINGLE_FILE:
                dict_content[attr_name] = self.__get_model_content(attr_value, next_path)
            else:
                self.load_flync_model(attr_value, next_path / attr_name)

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

        Returns:
            The loaded model instance, or ``None`` if loading failed.
        """

        link = ParentLink(parent_path, field_name, "list", position)
        if base_type is Union:
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
            item = self.__load_from_path(
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

    def __handle_generic_types_list(  # noqa
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

        Returns:
            bool: ``True`` if the field was handled, ``False`` otherwise.
        """

        list_item_value: list = []
        list_element_type = base_type_args[0]
        if OutputStrategy.FOLDER in external.output_structure:
            item_dir = path / external_path
            effective_element_type = list_element_type
            if get_origin(list_element_type) is Annotated:
                effective_element_type = get_args(list_element_type)[0]
            base_type = get_origin(effective_element_type)
            base_type_args = get_args(effective_element_type)
            # Sort so list indices (and therefore object ids and list order) are
            # deterministic across loads and filesystems; iterdir() order is not.
            for idx, sub_item_path in enumerate(sorted(item_dir.iterdir())):
                if not self.is_path_supported(sub_item_path):
                    logger.warning(
                        "Unrecognized file found in FLYNC workspace: %s",
                        str(sub_item_path),
                    )
                    continue
                list_name = self.name_form_file(sub_item_path)
                list_paths = self.add_list_item_object_path(list_name, current_object_paths, idx)
                item = self.__load_list_item(
                    sub_item_path,
                    base_type,
                    base_type_args,
                    list_element_type,
                    field_name,
                    item_dir,
                    external,
                    list_paths,
                    path,
                    len(list_item_value),
                )
                if item is None:
                    continue
                list_item_value.append(item)
            module_load_info[field_name] = list_item_value
            return True
        if OutputStrategy.SINGLE_FILE in external.output_structure:
            new_base_type = base_type_args[0]
            single_info: dict = {}
            self.__handle_generic_types(
                attribute_type=new_base_type,
                base_type=get_origin(new_base_type),
                base_type_args=get_args(new_base_type),
                external=external,
                path=path,
                external_path=external_path,
                module_load_info=single_info,
                field_name=field_name,
                storage_key=field_name,
                current_object_paths=current_object_paths,
            )
            module_load_info.update(single_info)
            return True
        return False

    def __handle_generic_types_dict(  # noqa # nosonar
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
    ) -> bool:  # noqa # nosonar
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
            for sub_item_path in sorted(item_dir.iterdir()):
                if not self.is_path_supported(sub_item_path):
                    logger.warning(
                        "Unrecognized file found in FLYNC workspace: %s",
                        str(sub_item_path),
                    )
                    continue
                dict_item_value[sub_item_path.name] = self.__load_from_path(
                    sub_item_path,
                    dict_element_type,
                    field_name,
                    self.update_objects_path(current_object_paths, sub_item_path.name),
                    ParentLink(path, field_name, "dict", sub_item_path.name),
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
    ):
        """
        Attempt to load one union member type, restoring diagnostics on failure.

        Args:
            path (Path): Absolute path of the current directory.
            external_path (str): Relative path segment for this field.
            possible_type: The union member type to attempt.
            field_name (str): Field name on the parent model.
            current_object_paths (list[str]): Dot-path contexts for object tracking.

        Returns:
            The loaded model instance, or ``None`` if the type did not match.
        """

        attempt_path = (path / external_path).absolute()
        doc_id = self.document_id_from_path(attempt_path)
        diags_existed = doc_id in self.documents_diags
        saved_diags = list(self.documents_diags.get(doc_id, []))
        saved_count = len(saved_diags)
        result = self.__load_from_path(
            path / external_path,
            possible_type,
            field_name,
            current_object_paths,
            link,
        )
        if result is None:
            new_diags = self.documents_diags.get(doc_id, [])[saved_count:]
            # If the failed attempt produced a user-raised semantic error
            # (err_major / err_minor / err_fatal on the matched type), keep
            # the diags so the user sees them. Discard only purely structural
            # mismatches, which signal "wrong union member".
            has_semantic_error = any(is_semantic_validation_error(d) for d in new_diags)
            if not has_semantic_error:
                if diags_existed:
                    self.documents_diags[doc_id] = saved_diags
                elif doc_id in self.documents_diags:
                    del self.documents_diags[doc_id]
        return result

    def __handle_generic_types_union(  # noqa
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

        Returns:
            bool: ``True`` if at least one union member loaded successfully.
        """

        success_union = False
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
                    )
                success_union = True
                break
            # What exception are you trying to catch?
            except:  # noqa: E722, B001
                pass
        return success_union

    def __handle_generic_types(
        self,
        attribute_type: type,
        base_type: type | None,
        base_type_args: tuple,
        external: External,
        path: Path,
        external_path: str,
        module_load_info: dict,
        field_name: str,
        storage_key: str,
        current_object_paths: list[str],
    ):
        """
        Dispatch an external field to the correct type-specific loader.

        Routes ``list``, ``dict``, and ``Union`` types to their dedicated handlers.
        Falls through to a direct model load for concrete ``FLYNCBaseModel`` subclasses, or does nothing for optional fields whose value is absent.

        Args:
            attribute_type (type): The full (possibly generic) annotation type.
            base_type (type | None): The ``get_origin`` of ``attribute_type``, or ``None`` for non-generic types.
            base_type_args (tuple): The ``get_args`` of ``attribute_type``.
            external (External): Annotation controlling load strategy.
            path (Path): Absolute path of the current directory.
            external_path (str): Relative path segment for this field.
            module_load_info (dict): Accumulator for loaded field values; updated in place.
            field_name (str): Field name on the parent model.
            current_object_paths (str): Dot-path context(s) for object tracking.

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

        elif base_type is Union:
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

        module_load_info[field_name] = self.__load_from_path(
            path / external_path,
            attribute_type,
            field_name,
            current_object_paths,
            scalar_link,
        )

    def __load_from_path(  # nosonar # noqa
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
        self._doc_index[doc_id] = LoadNode(
            path=path,
            doc_id=doc_id,
            current_type=current_type,
            current_type_name=current_type_name,
            object_paths=list(current_object_paths),
            link=link,
        )
        module_load_info: dict = {}
        # start by loading each field
        for field_name, field_info in current_type.model_fields.items():
            external: External | None = get_metadata(field_info.metadata, External)
            self.__handle_external_field_load(
                path,
                current_object_paths,
                module_load_info,
                field_name,
                field_info,
                external,
            )
            implied: Implied | None = get_metadata(field_info.metadata, Implied)
            self.__handle_implied_field_load(path, module_load_info, field_name, implied)

        # then group all the fields into the same object and return it
        self.__append_to_info_dict(path, module_load_info)

        if doc_id in self.documents_diags:
            logger.error("File %s was already loaded.", doc_id)
        return self._validate_node(self._doc_index[doc_id], module_load_info, map_paths=current_object_paths)

    def __handle_implied_field_load(
        self,
        path: Path,
        module_load_info: dict,
        field_name: str,
        implied: Implied | None,
    ):
        if implied is not None:
            if implied.strategy == ImpliedStrategy.FOLDER_NAME:
                module_load_info[field_name] = path.name
            elif implied.strategy == ImpliedStrategy.FILE_NAME:
                module_load_info[field_name] = self.name_form_file(path)

    def __handle_external_field_load(
        self,
        path,
        current_object_paths,
        module_load_info,
        field_name,
        field_info,
        external,
    ):
        if external is not None:
            # field will need to be added to to a new separate document
            attribute_type = field_info.annotation
            if attribute_type is None:
                raise ValueError("Attribute {} has an invalid type.", field_name)
            base_type: type | None = get_origin(attribute_type)
            base_type_args = get_args(attribute_type)
            storage_key = field_name
            external_path = self.__get_external_path(path, external, field_name)
            if not external_path.exists() and field_info.alias is not None:
                external_path = self.__get_external_path(path, external, field_info.alias)
                storage_key = field_info.alias
            if OutputStrategy.SINGLE_FILE in external.output_structure:
                if OutputStrategy.OMMIT_ROOT not in external.output_structure:
                    # the output file is a dictionary
                    # we need to load it accordingly
                    attribute_type = dict[str, attribute_type]  # type: ignore[valid-type]
                    base_type = get_origin(attribute_type)
                    base_type_args = get_args(attribute_type)
            new_paths = self.update_objects_path(current_object_paths, field_name)
            self.__handle_generic_types(
                attribute_type,
                base_type,
                base_type_args,
                external,
                path,
                external_path,
                module_load_info,
                field_name,
                storage_key,
                new_paths,
            )

    def __append_to_info_dict(  # noqa # nosonar
        self,
        path: Path,
        model_load_info: dict,
        output_strategy: Optional[OutputStrategy] = None,
        field_name: Optional[str] = None,
        fixed_name: Optional[str] = None,
    ):  # noqa # nosonar
        """
        Merge the contents of a FLYNC file into a model load-info dict.

        Opens the file at ``path``, registers it as a document, and merges its parsed YAML content into ``model_load_info``.
        The merge behaviour depends on ``output_strategy``:

        - ``OMMIT_ROOT``: assigns the raw content to ``model_load_info[field_name]``.
        - ``FIXED_ROOT``: assigns only the ``fixed_name`` key of the content.
        - Default: updates ``model_load_info`` with all top-level keys.

        Does nothing when ``path`` is not a file or is not a recognised FLYNC file extension.

        Args:
            path (Path): Path to the FLYNC YAML file.
            model_load_info (dict): Accumulator dict; updated in place.
            output_strategy (OutputStrategy | None): Optional output strategy that controls how the file content is merged.
            field_name (str | None): Target key in ``model_load_info`` for ``OMMIT_ROOT`` / ``FIXED_ROOT`` strategies.
            fixed_name (str | None): Key inside the file content to extract for ``FIXED_ROOT`` strategy.
        """

        if path.is_file():
            if not self.is_flync_file(path):
                logger.error("trying to load an unsupported file: %s", str(path))
                return
            uri: str = self.document_id_from_path(path)
            if uri not in self.documents:
                self._open_document(path)
            content = self.documents[uri].ast
            if content is None:
                return
            if output_strategy:
                if OutputStrategy.OMMIT_ROOT in output_strategy:
                    model_load_info[field_name] = content
                    return
                elif OutputStrategy.FIXED_ROOT in output_strategy:
                    model_load_info[field_name] = content[fixed_name]
                    return
            model_load_info.update(content)

    @staticmethod
    def __get_field_filename(model: FLYNCBaseModel):  # noqa # nosonar
        """
        Return the field name whose value supplies the output filename.

        Searches the model's fields for one annotated with :class:`~flync.core.annotations.Implied` using the ``FILE_NAME`` strategy.

        Args:
            model (FLYNCBaseModel): The model instance to inspect.

        Returns:
            str | None: The field name to use as the file name, or ``None`` if no such field exists.
        """

        for field, info in type(model).model_fields.items():
            implied: Implied | None = get_metadata(info.metadata, Implied)
            if implied and implied.strategy == ImpliedStrategy.FILE_NAME:
                return field

        return None

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

    def generate_configs(self, uri: PathType | None = None):
        """
        Save the workspace to the given path.

        Creates the output directory (if it does not exist) and writes a simple representation of the workspace.
        If a FLYNCModel has been loaded via ``load_flync_model``, it attempts to serialize the model to JSON.

        Args:
            uri (str | Path | None): Optional argument to save specific file instead of the entire workspace.

        Returns: None
        """

        if uri is not None:
            uri = str(uri)
            if uri not in self.documents:
                raise ValueError(f"Document with URI {uri} not found in workspace.")
        docs = [self.documents[uri]] if uri else self.documents.values()
        for doc in docs:
            # create file
            path_from_uri: Path = Path(doc.uri)
            path_from_uri.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(doc.text, str):
                path_from_uri.write_text(doc.text, encoding="utf-8")
            elif isinstance(doc.text, dict) or isinstance(doc.text, list):
                with open(path_from_uri, "w", encoding="utf-8") as f:
                    yaml.dump(
                        doc.text,
                        f,
                        sort_keys=False,
                        default_flow_style=False,
                        allow_unicode=True,
                    )

    # endregion
    # region incremental update

    def update_document(self, uri: PathType) -> list[str]:
        """
        Re-load a single changed document and re-validate only what depends on it.

        The document is read from disk and re-validated in isolation, then its fresh value is spliced
        into the parent model and every ancestor up to the root is re-validated while reusing the
        already-loaded sibling models. This keeps cross-document references (which are resolved by
        ancestor validators) correct without paying the cost of a full :meth:`load_workspace`.

        Falls back to a full reload when the document is not a known load-node (e.g. a brand new file),
        no longer exists, or the partial update hits an unsupported shape.

        Args:
            uri (PathType): Path of the changed document, absolute or workspace-relative.

        Returns:
            list[str]: The ids of every document whose model or diagnostics were recomputed.
        """

        uri = Document.normalize_uri(uri, self.workspace_root)
        target = self.workspace_root / uri if self.workspace_root else Path(uri)
        node = self._doc_index.get(uri)
        if node is None or not target.exists():
            logger.info("update_document: %s cannot be updated in place, reloading workspace", uri)
            return self._reset_and_reload()
        try:
            return self._reload_document(node, uri)
        except Exception as ex:  # noqa: BLE001
            logger.error("update_document: partial reload of %s failed (%s), reloading workspace", uri, ex)
            return self._reset_and_reload()

    def _reload_document(self, node: LoadNode, uri: str) -> list[str]:
        """
        Perform the in-place reload of ``node`` and re-validate its ancestor spine.

        Args:
            node (LoadNode): The indexed node for the changed document.
            uri (str): Workspace-relative id of the changed document.

        Returns:
            list[str]: Ids of all documents that were recomputed (leaf subtree + ancestors).
        """

        text = read_file(self.workspace_root / uri)  # type: ignore[operator]
        if uri in self.documents:
            self.documents[uri].update_text(text)
        else:
            doc = Document(uri, text, self.configuration.map_objects)
            doc.parse()
            self.documents[uri] = doc

        affected: list[str] = []
        cur_child, ids = self._reload_subtree(node)
        affected += ids

        cur_link = self._doc_index[node.doc_id].link
        while cur_link is not None:
            parent_id = self.document_id_from_path(str(cur_link.parent_path))
            parent_node = self._doc_index.get(parent_id)
            if parent_node is None:
                raise ValueError(f"missing parent node for {cur_link.parent_path}")
            rebuilt = self._rebuild_ancestor(parent_node, cur_link, cur_child)
            if rebuilt is None:
                # Reusing sibling instances is cheap but leaves error-recovery unable to prune a bad
                # value out of a reused child. When that happens, re-validate this ancestor's whole
                # subtree (from the cached ASTs, no disk read) so the policy pruning behaves as it does
                # on a full load. The root's subtree is the whole workspace, so reload everything.
                if parent_node.link is None:
                    return self._reset_and_reload()
                rebuilt, ids = self._reload_subtree(parent_node)
                affected += ids
            affected.append(parent_id)
            cur_child = rebuilt
            cur_link = self._doc_index[parent_id].link
        self.flync_model = cur_child  # type: ignore[assignment]

        return list(dict.fromkeys(affected))

    def _reload_subtree(self, node: LoadNode) -> tuple[object, list[str]]:
        """
        Drop and re-load ``node`` together with everything indexed underneath it.

        Args:
            node (LoadNode): Root of the subtree to reload.

        Returns:
            tuple[object, list[str]]: The reloaded model value and the ids of the documents touched.
        """

        affected = [sub.doc_id for sub in self._subtree_nodes(node)]
        for doc_id in affected:
            self.documents_diags.pop(doc_id, None)
            if doc_id != node.doc_id:
                self._doc_index.pop(doc_id, None)
        if self.configuration.map_objects:
            self._purge_object_subtree(node.object_paths)
        model = self.__load_from_path(
            node.path,
            node.current_type,
            node.current_type_name,
            list(node.object_paths),
            node.link,
        )
        return model, affected

    def _rebuild_ancestor(self, parent_node: LoadNode, link: ParentLink, new_child):
        """
        Re-validate ``parent_node`` with its changed child replaced, reusing every other child instance.

        The parent's own inline file is re-read but the unchanged external children are taken straight
        from the previously loaded parent instance, so validation only re-runs the parent's own
        validators (including reference binding) instead of re-parsing sibling documents.

        Args:
            parent_node (LoadNode): The ancestor being rebuilt.
            link (ParentLink): How ``new_child`` attaches to this ancestor.
            new_child: The freshly loaded value for ``link.field_name``.

        Returns:
            The rebuilt (and parent-normalized) ancestor model.
        """

        old_parent = parent_node.model
        parent_type = parent_node.current_type
        new_branch = self._splice_branch(old_parent, link, new_child)
        module_load_info = self._ancestor_load_info(parent_node, old_parent, link, new_branch)

        new_parent = self._validate_node(parent_node, module_load_info)
        if self.configuration.map_objects and old_parent is not None:
            if new_parent is not None:
                self._remap_ancestor_objects(parent_type, old_parent, new_parent)
            else:
                self._detach_object(parent_node)
        return new_parent

    def _ancestor_load_info(self, parent_node: LoadNode, old_parent, link: ParentLink, new_branch) -> dict:
        """
        Gather the field data to re-validate ``parent_node`` with ``link.field_name`` replaced.

        Unchanged external children are reused straight from ``old_parent`` (so they are not re-read or
        re-validated), implied fields are recomputed from the path, and the parent's own inline file is
        merged back in.
        """

        module_load_info: dict = {}
        for field_name, field_info in parent_node.current_type.model_fields.items():
            if field_name == link.field_name:
                module_load_info[field_name] = new_branch
                continue
            if get_metadata(field_info.metadata, External) is not None:
                value = getattr(old_parent, field_name, None)
                if value is not None:
                    module_load_info[field_name] = value
                continue
            implied = get_metadata(field_info.metadata, Implied)
            if implied is not None:
                self.__handle_implied_field_load(parent_node.path, module_load_info, field_name, implied)
        self.__append_to_info_dict(parent_node.path, module_load_info)
        return module_load_info

    def _detach_object(self, node: LoadNode) -> None:
        """Clear the object-map entry of a node whose model failed to rebuild, so it holds no stale model."""
        if not node.object_paths:
            return
        oid = ObjectId(node.object_paths[0].strip("."))
        semantic = self.objects.get(oid)
        if semantic is None or semantic.model is None:
            return
        self._unmap_object_id(semantic.model, oid)
        cast(SemanticObject, semantic).model = None  # type: ignore[assignment]

    @staticmethod
    def _splice_branch(old_parent, link: ParentLink, new_child):
        """Build the new value for ``link.field_name`` with ``new_child`` put in the right slot."""
        if link.container == "list":
            new_list = list(getattr(old_parent, link.field_name, None) or [])
            if isinstance(link.key, int) and 0 <= link.key < len(new_list):
                new_list[link.key] = new_child
            else:
                new_list.append(new_child)
            return new_list
        if link.container == "dict":
            new_dict = dict(getattr(old_parent, link.field_name, None) or {})
            new_dict[link.key] = new_child
            return new_dict
        return new_child

    def _validate_node(self, node: LoadNode, module_load_info: dict, map_paths: Optional[list[str]] = None):
        """
        Validate ``module_load_info`` for ``node`` the same way the initial load does.

        Resets the node's diagnostics, applies the parent-aware type rebuild/normalisation, records any
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
            self.documents_diags[node.doc_id].extend(errors)
            if map_paths is not None and self.configuration.map_objects:
                self._update_objects(node.doc_id, model, map_paths, parent_name=node.current_type_name)
            if node.current_type_name:
                model = self.model_graph.normalize_child_to_parent(original_type, node.current_type_name, model)
            node.model = model
            return model
        except ValidationError as e:
            self.documents_diags[node.doc_id].extend(e.errors())
            node.model = None
            return None

    def _subtree_nodes(self, node: LoadNode) -> list[LoadNode]:
        """Return ``node`` and every indexed node whose object path sits underneath it."""
        own = {p.strip(".") for p in node.object_paths}
        own.discard("")
        prefixes = tuple(f"{p}." for p in own)
        result = []
        for candidate in self._doc_index.values():
            ids = {p.strip(".") for p in candidate.object_paths}
            if ids & own or (prefixes and any(cid.startswith(prefixes) for cid in ids)):
                result.append(candidate)
        return result

    def _purge_object_subtree(self, object_paths: list[str]) -> None:
        """
        Remove all object-map entries under ``object_paths`` so a reload can register them fresh.

        The node's own ids are dropped from :attr:`objects`/:attr:`sources` (the reload re-creates them
        with the new model) but kept in the parent's child index, since the parent is not reloaded and
        would otherwise lose the edge to this node.
        """

        own = {p.strip(".") for p in object_paths}
        own.discard("")
        prefixes = tuple(f"{p}." for p in own)

        def in_subtree(oid: str) -> bool:
            """Utility function to check if object id is in the subtree."""
            return oid in own or (bool(prefixes) and oid.startswith(prefixes))

        def is_descendant(oid: str) -> bool:
            """Utility function to check if object id is descendant in the path."""
            return bool(prefixes) and oid.startswith(prefixes)

        # Use self.objects keys directly — list_objects() includes virtual
        # aliases from _duplicated_objects_ids.values() that are not actual keys
        # in self.objects and would cause a KeyError on pop.
        real_objs = [o for o in self.objects if in_subtree(str(o))]
        for oid in real_objs:
            semantic = self.objects.pop(oid)
            self.sources.pop(oid, None)
            self._unmap_object_id(semantic.model, oid)
        if self._duplicated_objects_ids:
            for oid in [o for o in self.list_objects() if in_subtree(str(o))]:
                self._duplicated_objects_ids.pop(oid, None)

        for pid in [p for p in self._children_by_parent if in_subtree(p)]:
            self._children_by_parent.pop(pid, None)
        for parent_id, children in self._children_by_parent.items():
            self._children_by_parent[parent_id] = [c for c in children if not is_descendant(c)]
        self._linked_child_ids = {c for c in self._linked_child_ids if not is_descendant(c)}

    def _remap_ancestor_objects(self, parent_type, old_parent, new_parent) -> None:
        """Point the ancestor's (and its external container fields') object entries at the rebuilt instances."""
        self._remap_model_ids(old_parent, new_parent)
        for field_name, field_info in parent_type.model_fields.items():
            if get_metadata(field_info.metadata, External) is None:
                continue
            old_value = getattr(old_parent, field_name, None)
            new_value = getattr(new_parent, field_name, None)
            if isinstance(old_value, (list, dict)) and old_value is not new_value:
                self._remap_model_ids(old_value, new_value)

    def _unmap_object_id(self, model, oid: ObjectId) -> None:
        """Remove a single object id from the ``model -> ids`` reverse index."""
        if model is None:
            return
        ids = self._model_to_object_ids.get(id(model))
        if ids is None:
            return
        remaining = [i for i in ids if i != oid]
        if remaining:
            self._model_to_object_ids[id(model)] = remaining
        else:
            self._model_to_object_ids.pop(id(model), None)

    def _remap_model_ids(self, old_model, new_model) -> None:
        """Move the object ids registered for ``old_model`` onto ``new_model``."""
        ids = self._model_to_object_ids.pop(id(old_model), None)
        if not ids:
            return
        for oid in ids:
            semantic = self.objects.get(oid)
            if semantic is not None:
                semantic.model = new_model
        self._model_to_object_ids[id(new_model)] = ids

    def _reset_and_reload(self) -> list[str]:
        """Clear all derived state and reload the workspace from disk (the safe fallback path)."""
        self.documents.clear()
        self.documents_diags.clear()
        self.objects.clear()
        self.sources.clear()
        self._model_to_object_ids.clear()
        self._children_by_parent.clear()
        self._linked_child_ids.clear()
        self._doc_index.clear()
        self._duplicated_objects_ids.clear()
        self._open_documents()
        self.flync_model = self.__load_from_path(self.workspace_root)  # type: ignore[arg-type]
        return list(self.documents_diags.keys())

    # endregion
    # region helpers
    def is_path_supported(self, path: PathType):
        """
        Return whether a path is a directory or a recognised FLYNC file.

        Args:
            path (PathType): The path to check.

        Returns:
            bool: ``True`` if the path is a directory or a FLYNC file.
        """

        if not isinstance(path, Path):
            path = Path(path)
        return path.is_dir() or self.is_flync_file(path)

    def is_flync_file(self, path: PathType):
        """
        Return whether a path has a recognised FLYNC file extension.

        Args:
            path (PathType): The path to check.

        Returns:
            bool: ``True`` if the path's combined suffixes are in :attr:`~WorkspaceConfiguration.allowed_extensions`.
        """

        if not isinstance(path, Path):
            path = Path(path)
        return "".join(path.suffixes) in self.configuration.allowed_extensions

    def name_form_file(self, file_name: str | Path) -> str:
        """
        Strip all recognised FLYNC file extensions from a filename.

        Iterates over every extension in :attr:`~flync.sdk.context.workspace_config.WorkspaceConfiguration.allowed_extensions`
        and removes it as a suffix, leaving the bare stem.
        If a :class:`pathlib.Path` is passed, only its ``name`` component is used.

        Args:
            file_name (str | Path): The filename or path to strip.

        Returns:
            str: The filename with all FLYNC extensions removed (e.g. ``"my_ecu.flync.yaml"`` → ``"my_ecu"``).
        """

        if isinstance(file_name, Path):
            file_name = file_name.name
        for extension in self.configuration.allowed_extensions:
            file_name = file_name.replace(extension, "")
        return file_name

    def fill_path_from_object(self, model_object: FLYNCBaseModel, object_path: str) -> str:  # noqa # nosonar  # noqa # nosonar
        """
        Replace placeholder segments in an object path with concrete keys.

        Traverses the workspace's root model following ``object_path``, substituting ``[]`` with the actual list index and ``{}`` with the
        actual dict key when ``model_object`` is found.

        Args:
            model_object (FLYNCBaseModel): The model instance to locate.
            object_path (str): Dot-separated path containing ``[]`` or ``{}`` placeholders.

        Returns:
            str: The resolved dot-separated path with concrete index/key values.
        """

        parts = object_path.split(".")
        current_parent = self.flync_model
        for parts_idx, part in enumerate(parts):
            if part == "[]":
                for idx, obj in enumerate(current_parent):  # type: ignore[arg-type]
                    if obj == model_object:
                        parts[parts_idx] = idx  # type: ignore[call-overload]
                        current_parent = obj  # type: ignore[assignment]
            elif part == "{}":
                for key, value in current_parent.item():  # type: ignore
                    if value == obj:
                        parts[parts_idx] = key
                        current_parent = value
            else:
                current_parent = getattr(current_parent, part)
        return ".".join(parts)

    @lru_cache(maxsize=None)
    def document_id_from_path(self, doc_path: str) -> str:
        """
        Return the workspace-relative string identifier for a document path.

        Args:
            doc_path (str): An absolute path to a document file.

        Returns:
            str: The path relative to the workspace root, as a string.
        """

        return Path(doc_path).absolute().relative_to(self.workspace_root).as_posix()  # type: ignore[arg-type]

    @staticmethod
    def new_object_path(current_path: str, new_object_name: int | str) -> str:
        """
        Extend a dot-separated object path with a new segment.

        Args:
            current_path (str): The existing dot-separated path.
            new_object_name (int | str): The segment to append.

        Returns:
            str: The extended path string.
        """

        return ".".join([current_path, str(new_object_name)]) if current_path else str(new_object_name)

    def update_objects_path(self, current_paths: list[str], new_object_name: str) -> list[str]:
        """
        Extend every path in a list with a new segment.

        Args:
            current_paths (list[str]): Existing dot-separated paths.
            new_object_name (str): The segment to append to each path.

        Returns:
            list[str]: New list of extended path strings.
        """

        child_paths = [self.new_object_path(current_path, new_object_name) for current_path in current_paths]
        if self.configuration.map_objects:
            # Each child path is its parent path with one appended segment, so the
            # parent/child pair is known here without ever splitting the id. Index
            # alignment holds because both lists are built from ``current_paths``.
            for parent_path, child_path in zip(current_paths, child_paths):
                self._link_child_path(parent_path, child_path)
            if (
                len(child_paths) > 1
                and ListObjectsMode.INDEX in self.configuration.list_objects_mode
                and ListObjectsMode.NAME in self.configuration.list_objects_mode
            ):
                self._duplicated_objects_ids.setdefault(child_paths[0], []).extend(child_paths[1:])  # type: ignore[arg-type]
        return child_paths

    def _link_child_path(self, parent_id: str, child_id: str) -> None:
        """
        Record a parent -> child edge in the child index.

        ``parent_path``/``child_path`` are raw (possibly leading-dot) traversal
        paths; they are normalized with the same ``strip(".")`` used when objects
        are registered, so the recorded ids match :attr:`objects` keys. Root-level
        ids (which normalize to an empty parent) are skipped, preserving the
        "root has no children" behaviour.
        """

        if not parent_id or child_id in self._linked_child_ids:
            return

        self._linked_child_ids.add(child_id)
        self._children_by_parent.setdefault(parent_id, []).append(child_id)

    # endregion

    # region semantic APIs (SDK)

    def _update_objects(  # nosonar # noqa
        self,
        path_id: str,
        model: FLYNCBaseModel | None,
        current_object_paths: list[str],
        node: Node | None = None,
        parent_name: str | None = None,
    ):
        """
        Recursively register model values and their source positions.

        Walks the YAML AST node alongside the validated model, calling :meth:`_add_object_to_path` for every value encountered so that
        each semantic object is associated with its source location.

        Args:
            path_id (str): document id of the document containing this node.
            model (FLYNCBaseModel): The validated model value at this node.
            current_object_paths (str | list[str]): Dot-path context(s) for the current model value.
            node (Node | None): The ruamel.yaml AST node corresponding to ``model``. Defaults to the document's root compose AST.
            parent_name (str | None): The field name on the parent that points to this node, used for sequence items.
        """

        start_line = 0
        end_line = 0
        start_column = 0
        end_column = 0
        if isinstance(model, RootModel):
            model = model.root
        if model is not None and path_id in self.documents:
            # object is all external fields
            # should already be updated
            document = self.documents[path_id]
            if node is None:
                node = document.compose_ast
            if isinstance(node, MappingNode):
                self._update_mapping_node_objects(path_id, model, current_object_paths, node)
            elif isinstance(node, SequenceNode):
                self._update_sequence_node_objects(path_id, model, current_object_paths, node, parent_name)
            if node is not None:
                start_line, start_column = (
                    node.start_mark.line + 1,
                    node.start_mark.column + 1,
                )
                end_line, end_column = (
                    node.end_mark.line + 1,
                    node.end_mark.column + 1,
                )
        self._add_object_to_path(
            path_id,
            model,
            current_object_paths,
            start_line,
            end_line,
            start_column,
            end_column,
        )

    def _update_sequence_node_objects(self, doc_id, model, current_object_paths, node, parent_name):
        for idx, item in enumerate(node.value):
            list_paths = self.add_list_item_object_path(
                getattr(model[idx], "name", None),  # type: ignore
                current_object_paths,
                idx,
            )
            self._update_objects(
                doc_id,
                model[idx],  # type: ignore[index]
                list_paths,
                item,
                parent_name=parent_name,
            )

    def _update_mapping_node_objects(self, doc_id, model, current_object_paths, node):
        for key_node, val_node in node.value:
            if isinstance(model, dict):
                model_value = model[key_node.value]
            else:
                model_fields = getattr(type(model), "model_fields", {})
                if key_node.value in model_fields:
                    field_name = key_node.value
                else:
                    try:
                        field_name = get_name_by_alias(type(model), key_node.value)
                    except KeyError:
                        field_name = key_node.value
                model_value = getattr(model, field_name, None)
            self._update_objects(
                doc_id,
                model_value,
                self.update_objects_path(current_object_paths, key_node.value),
                val_node,
                key_node.value,
            )

    def add_list_item_object_path(self, item_name, current_object_paths, idx):
        """
        Build the object path(s) for a single list item.

        Depending on :attr:`~flync.sdk.context.workspace_config.WorkspaceConfiguration.list_objects_mode`,
        the item may be registered under its numeric index, its name, or both:

        - :attr:`~flync.sdk.context.workspace_config.ListObjectsMode.INDEX`: appends the zero-based integer index as a path segment.
        - :attr:`~flync.sdk.context.workspace_config.ListObjectsMode.NAME`: appends ``item_name`` as an additional path segment when the name is
          non-empty. For external (folder-based) lists the name comes from the file/directory stem; for inline lists it comes from the model's
          ``name`` attribute.

        Both flags are active by default, so a list item is accessible under two IDs simultaneously (e.g. ``controllers.0`` and
        ``controllers.my_ctrl``).

        Args:
            item_name (str | None): Name of the list item, or ``None`` empty string when the item has no name.
            current_object_paths (list[str]): Parent path(s) to extend.
            idx (int): Zero-based position of the item in the list.

        Returns:
            list[str]: New list of object paths for this item.
        """
        idx_paths = []
        name_paths = []
        index_mode = ListObjectsMode.INDEX in self.configuration.list_objects_mode
        name_mode = ListObjectsMode.NAME in self.configuration.list_objects_mode
        if index_mode or not item_name:
            idx_paths += self.update_objects_path(current_object_paths, idx)
        if name_mode and item_name:
            name_paths += self.update_objects_path(current_object_paths, item_name)

        if name_mode and index_mode:
            if len(idx_paths) > 1:
                self._duplicated_objects_ids.setdefault(idx_paths[0], []).extend(idx_paths[1:] + name_paths)

            elif len(idx_paths) == 1 and name_paths:
                self._duplicated_objects_ids.setdefault(idx_paths[0], []).extend(name_paths)

        return idx_paths + name_paths

    def _add_object_to_path(  # noqa # nosonar
        self,
        doc_id: str,
        model,
        current_object_paths: list[str],
        start_line,
        end_line,
        start_column,
        end_column,
    ):  # noqa # nosonar
        """
        Register a model value and its source location for each given document id.

        Creates entries in :attr:`objects` and :attr:`sources` for every path in ``current_object_paths``. Skips paths that are already registered.

        Args:
            doc_id (str): document id of the document containing the object.
            model: The semantic object value to store.
            current_object_paths (list[str]): Dot-separated object ids to register.
            start_line (int): 1-based start line of the object in the document.
            end_line (int): 1-based end line of the object.
            start_column (int): 1-based start column.
            end_column (int): 1-based end column.
        """
        if not self.configuration.map_objects:
            return

        model_key = None if model is None else id(model)
        src_ref = SourceRef(doc_id, get_range(start_line, start_column, end_line, end_column))
        if self._duplicated_objects_ids and current_object_paths:
            common = [p for p in current_object_paths if p in self._duplicated_objects_ids]
            if common:
                current_object_paths = common

        for object_path in current_object_paths:
            object_id = ObjectId(object_path)
            if object_id in self.objects:
                return
            self.objects[object_id] = SemanticObject(object_id, model)
            self.sources[object_id] = src_ref
            if model_key is not None:
                self._model_to_object_ids.setdefault(model_key, []).append(object_id)
                if oids := self._duplicated_objects_ids.get(object_id):
                    self._model_to_object_ids[model_key].extend(oids)

    def _resolve_duplicate_object_id(self, oid: ObjectId):
        """
        Resolve a duplicate object ID into a fully registered object.

        This method checks whether the given `oid` exists in the duplicates mapping
        (`self._duplicated_objects_ids`). If found, it promotes the duplicate ID into
        `self.objects` and `self.sources` by copying the canonical object's model and source.

        Args
        ----------
        oid : ObjectId
            The object identifier to resolve from duplicates.
        """
        if oid in self.objects or not self._duplicated_objects_ids:
            return
        parent = oid.split(".")[0]
        for name_id, idx_ids in self._duplicated_objects_ids.items():
            if parent != name_id.split(".")[0] or oid not in idx_ids:
                continue

            model = self.objects[name_id].model
            source = self.sources[name_id]
            self.objects.update({dup: SemanticObject(oid, model) for dup in idx_ids})
            self.sources.update(dict.fromkeys(idx_ids, source))
            del self._duplicated_objects_ids[name_id]
            return

    def get_object(self, id: ObjectId) -> SemanticObject:
        """
        Retrieve a semantic object by its ObjectId.

        Args:
            id (ObjectId):
                Identifier of the semantic object.

        Returns:
            SemanticObject:
                The requested semantic object.
        """
        self._resolve_duplicate_object_id(id)
        return self.objects[id]

    def has_object(self, id: ObjectId) -> bool:
        """
        Checks if a specific key exists within a dictionary of objects.

        Args:
            id (ObjectId):
                Identifier of the semantic object.

        Returns:
            bool:
                True if the key is found, False otherwise.
        """
        self._resolve_duplicate_object_id(id)
        return id in self.objects

    def get_metadata(self, id: ObjectId) -> ObjectMetadata:
        """
        Retrieve metadata about a semantic object without exposing the full model.

        Provides type information, field details, relationships, and source location.
        The model itself is stored privately and not exposed in serialization.

        Args:
            id (ObjectId):
                Identifier of the semantic object.

        Returns:
            ObjectMetadata:
                Metadata object with type, fields, annotations, parents, children, and source.

        Raises:
            KeyError:
                If the object does not exist in the workspace.
        """

        semantic_obj = self.get_object(id)
        return ObjectMetadata(semantic_obj, self)

    def list_objects(self) -> list[ObjectId]:
        """
        Return a list of all ObjectIds present in the workspace.

        Returns:
            list[ObjectId]:
                List of object identifiers.
        """
        if not self._duplicated_objects_ids:
            return list(self.objects.keys())

        duplicated_ids = chain.from_iterable(self._duplicated_objects_ids.values())
        return list(chain(self.objects.keys(), duplicated_ids))

    def get_child_ids(self, id: ObjectId) -> list[str]:
        """
        Return the immediate child ObjectId strings of a given object.

        Backed by the ``_children_by_parent`` index built during object
        mapping, so this is an O(1) lookup rather than a full scan of the
        workspace.

        Args:
            id (ObjectId): Identifier of the parent object.

        Returns:
            list[str]: Immediate child id strings (empty if none / not mapped).
        """

        return [child for child in self._children_by_parent.get(str(id), []) if self.has_object(ObjectId(child))]

    def get_definition(self, object_id: ObjectId, field_name: str) -> Optional[ObjectId]:
        """
        Resolve and return definition identifiers for a given field reference.

        Args:
            object_id (ObjectId):
                Identifier of the semantic object.
            field_name (str)
                The field name of referencing object

        Returns:
            ObjectId
                A list of object identifiers that match the resolved reference criteria.
                The list may be empty if no definitions are found or if the field has no valid reference metadata.
        """

        sematic_obj: SemanticObject = self.get_object(object_id)
        def_obj = resolve_reference(sematic_obj.model, field_name)
        if not isinstance(def_obj, FLYNCBaseModel):
            return None
        so = self.get_semantic_object_from_model(def_obj)
        return so.id if so else None

    def get_references_of(self, object_id: ObjectId) -> list[ObjectId]:
        """
        Return all ObjectIds that reference the given object.

        Iterates over every semantic object in the workspace and checks whether any of its fields are defined by the same model as the target object.
        For each matching field, the concrete path to that field is collected via `find_path_from_field`.

        Args:
            object_id (ObjectId):
                The id of the object whose references should be found.

        Returns:
            list[ObjectId]:
                A list of ObjectIds representing all fields across the workspace that reference the given object.
        """

        refs: list[ObjectId] = []
        current_obj = self.get_object(object_id)

        for semantic_obj in self.objects.values():
            fields: dict | None = getattr(type(semantic_obj.model), "model_fields", None)
            if fields is None:
                continue

            for field, info in fields.items():
                if obj_id_def := self.get_definition(semantic_obj.id, field):
                    model_def = self.get_object(obj_id_def)
                    if model_def.model is current_obj.model:
                        self.find_path_from_field(object_id, refs, semantic_obj, field, info)
        return refs

    def find_path_from_field(
        self,
        object_id: ObjectId,
        refs: list[ObjectId],
        semantic_obj: SemanticObject,
        field: str,
        info: FieldInfo,
    ):
        """
        Resolve the concrete ObjectId path for a field and append it to refs.

        Tries to build the path as `<semantic_obj.id>.<field>`, falling back to `<semantic_obj.id>.<info.alias>` when the first candidate is not
        present in the workspace. Raises if neither candidate exists.

        Args:
            object_id (ObjectId):
                The id of the target object being referenced (used in the error message when the path cannot be resolved).
            refs (list[ObjectId]):
                Accumulator list to which the resolved path is appended.
            semantic_obj (SemanticObject):
                The semantic object that owns the field being inspected.
            field (str):
                The field name on `semantic_obj`'s model.
            info:
                The Pydantic `FieldInfo` for the field, used to access the field alias as a fallback path segment.

        Raises:
            ValueError:
                If neither the field name nor its alias resolves to a known object in the workspace.
        """

        path_candidate = ObjectId(f"{semantic_obj.id}.{field}")
        if not self.has_object(path_candidate):
            path_candidate = ObjectId(f"{semantic_obj.id}.{info.alias}")
        if not self.has_object(path_candidate):
            raise ValueError(
                "object with path {} not found in map",
                object_id,
            )
        refs.append(path_candidate)

    def get_semantic_objects_ids_from_model(self, model: FLYNCBaseModel) -> list[ObjectId]:
        """
        Find and return ObjectIds for all semantic objects that correspond to a model.

        A single model instance may be registered under multiple ObjectIds (e.g., a list item
        indexed by both numeric position and name).

        Args:
            model (FLYNCBaseModel):
                Validated Flync model.

        Returns:
            list[ObjectId]:
                List of ObjectIds that correspond to the Flync object. Empty if none found.
        """

        return self._model_to_object_ids.get(id(model), []).copy()

    def get_semantic_objects_from_model(self, model: FLYNCBaseModel) -> list[SemanticObject]:
        """
        Find and return all semantic objects that correspond to a validated Flync object.

        A single model instance may be registered under multiple ObjectIds (e.g., a list item
        indexed by both numeric position and name).

        Args:
            model (FLYNCBaseModel):
                Validated Flync model.

        Returns:
            list[SemanticObject]:
                List of semantic objects that correspond to the Flync object. Empty if none found.
        """

        return [self.get_object(oid) for oid in self._model_to_object_ids.get(id(model), [])]

    @deprecated("Use get_semantic_objects_from_model() instead, which returns all matches")
    def get_semantic_object_from_model(self, model: FLYNCBaseModel) -> SemanticObject | None:
        """
        Find and return the first semantic object that corresponds to a validated Flync object.

        This method maintains backward compatibility by returning only the first result.

        Args:
            model (FLYNCBaseModel):
                Validated Flync model.

        Returns:
            SemanticObject | None:
                First semantic object that corresponds to Flync object, or None if not found.
        """

        results = self.get_semantic_objects_from_model(model)
        return results[0] if results else None

    # endregion

    # region source APIs (LSP)

    def get_source(self, id: ObjectId) -> SourceRef:
        """
        Retrieve the source reference for a given ObjectId.

        Args:
            id (ObjectId):
                Identifier of the object.

        Returns:
            SourceRef:
                The source reference associated with the object.
        """
        self._resolve_duplicate_object_id(id)
        return self.sources[id]

    def objects_at(self, uri: str, line: int, character: int) -> list[ObjectId]:
        """
        Return the list of ObjectIds located at the specified position in a document.

        Args:
            uri (str):
                Document URI.
            line (int):
                1-based line number, consistent with the :class:`~flync.sdk.workspace.source.Position` values stored during YAML parsing.
            character (int):
                1-based character offset within the line.

        Returns:
            list[ObjectId]:
                List of object identifiers at the given position.
        """

        result = []
        for oid, src in self.sources.items():
            if src.uri != uri:
                continue
            r = src.range
            if (line > r.start.line or (line == r.start.line and character >= r.start.character)) and (
                line < r.end.line or (line == r.end.line and character <= r.end.character)
            ):
                result.append(oid)
        return result

    # endregion
