"""
Workspace module for FLYNC SDK.

Provides classes and functions to manage workspace operations.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Union, get_args, get_origin

import yaml
from pydantic import RootModel
from pydantic.fields import FieldInfo
from pydantic_core import ErrorDetails, ValidationError
from ruamel.yaml.nodes import MappingNode, Node, SequenceNode

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.annotations.reference import Reference, ReferenceStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions_handling import (
    errors_to_init_errors,
    get_name_by_alias,
    validate_with_policy,
)
from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import (
    ListObjectsMode,
    WorkspaceConfiguration,
)
from flync.sdk.utils.field_utils import (
    get_field_name_from_alias,
    get_metadata,
    get_name,
)
from flync.sdk.utils.model_dependencies import (
    ModelDependencyGraph,
    get_model_dependency_graph,
)
from flync.sdk.utils.sdk_types import PathType

from .document import Document
from .ids import ObjectId
from .objects import SemanticObject
from .source import Position, Range, SourceRef

logger = logging.getLogger(__name__)


class FLYNCWorkspace(object):
    """Workspace class managing documents, objects, and diagnostics.

    This class provides methods to ingest documents, run analysis, and expose
    semantic and source APIs for use by the SDK and language server.

    Attributes:
        name (str): Name of the workspace.

        documents (Dict[str, Document]): Mapping of document URIs to Document \
        objects.

        objects (Dict[ObjectId, SemanticObject]): Semantic objects indexed by \
        ObjectId.

        sources (Dict[ObjectId, SourceRef]): Source references indexed by \
        ObjectId.

        dependencies (Dict[ObjectId, Set[ObjectId]]): Dependency graph.

        reverse_deps (Dict[ObjectId, Set[ObjectId]]): Reverse dependency graph.

        _diagnostics (list[Diagnostic]): Collected diagnostics.
    """

    def __init__(  # noqa # nosonar
        self,
        name: str,
        workspace_path: PathType = "",
        configuration: WorkspaceConfiguration | None = None,
    ):  # noqa # nosonar
        """Initialize the workspace.

        Args:
            name (str): Human-readable name for this workspace instance.
            workspace_path (PathType): Absolute path to the workspace root
                directory. An empty string raises :class:`ValueError`.
            configuration (WorkspaceConfiguration | None): Optional
                configuration object. When ``None``, a default
                :class:`~flync.sdk.context.workspace_config.WorkspaceConfiguration`
                is used.
        """
        if not name:
            raise ValueError(
                "Passed an invalid value for workspace name {}",
                name,
            )
        self.name = name
        self.configuration = configuration or WorkspaceConfiguration()
        self.model_graph: ModelDependencyGraph = get_model_dependency_graph(
            self.configuration.root_model
        )
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
        if isinstance(workspace_path, str):
            workspace_path = Path(workspace_path).absolute()
        self.workspace_root = workspace_path

    @property
    def load_errors(self):
        """Flattened list of all validation errors across all loaded documents.

        Returns:
            list[ErrorDetails]: All per-document errors concatenated into a
            single list.
        """
        return [
            error
            for doc_errors in self.documents_diags.values()
            for error in doc_errors
        ]

    # region creator
    @classmethod
    def load_model(
        cls,
        flync_model: FLYNCModel,
        workspace_name: str | None = "generated_workspace",
        file_path: PathType = "",
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """loads a workspace object from a FLYNC Object.

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
        """loads a workspace object from a location of the Yaml Configuration.

        In case this fails, the workspace will still be created, but with an
        empty model.

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
        model = output.__load_from_path(workspace_path)

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
        """loads a workspace object from a location of the Yaml Configuration.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """
        output = FLYNCWorkspace.safe_load_workspace(
            workspace_name, workspace_path, workspace_config=workspace_config
        )
        if not isinstance(output.flync_model, FLYNCBaseModel):
            raise ValidationError.from_exception_data(
                title=f"Model ({workspace_name}) Creation Error",
                line_errors=errors_to_init_errors(output.load_errors),
            )
        return output

    # endregion
    # region ingestion
    def _open_document(self, uri: PathType, text: str):  # noqa # nosonar
        """Open a document, parse it, and add it to the workspace.

        Args:
            uri (str): The document's URI.

            text (str): The raw text content of the document.

        Returns: None
        """
        if isinstance(uri, str):
            uri = Path(uri)
        if uri.is_absolute():
            uri = uri.relative_to(
                self.workspace_root  # type: ignore[arg-type]
            )
        uri = uri.as_posix()
        doc = Document(uri, text, self.configuration.map_objects)
        doc.parse()
        self.documents[uri] = doc

    def load_flync_model(  # noqa # nosonar
        self, flync_model: FLYNCBaseModel, file_path: PathType = ""
    ):  # noqa # nosonar
        """Load a FLYNCModel into the workspace.

        This is a placeholder implementation that stores the model for later
        use.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)
        content = self.__get_model_content(flync_model, file_path)
        self.__save_content_to_file(file_path, content)

    def __save_content_to_file(  # noqa # nosonar
        self, file_path: Path, content
    ):  # noqa # nosonar
        """Persist serialized model content as a Document in the workspace.

        Resolves the full URI under the workspace root, creates a
        :class:`~flync.sdk.workspace.document.Document` for it, and calls
        :meth:`generate_configs` to write it to disk. Does nothing when
        ``content`` is empty (e.g. all fields were external).

        Args:
            file_path (Path): Relative path (without extension) for the file.
            content: The serialized content to write; may be a ``dict``, a
                ``list``, or a plain string.
        """
        if not content:
            # everything in the object was external,
            # no need to create a document
            return
        if not self.workspace_root:
            raise ValueError(
                "Unable to save contents in a workspace, the workspace root is not defined."  # noqa
            )
        uri = self.workspace_root / file_path.with_suffix(
            self.configuration.flync_file_extension
        )
        doc = Document(uri, content, self.configuration.map_objects)
        self.documents[str(uri)] = doc
        self.generate_configs(uri)

    def __get_model_content(  # noqa # nosonar
        self, flync_model: FLYNCBaseModel, file_path
    ):  # noqa # nosonar
        """Serialize a model to a dict, routing external fields to separate
        documents.

        Iterates over the model's fields. Fields annotated with
        :class:`~flync.core.annotations.External` are excluded from the
        returned dict and handled recursively. Fields with
        :class:`~flync.core.annotations.Implied` ``FOLDER_NAME`` strategy are
        also excluded (their value is inferred from the directory name at load
        time).

        Args:
            flync_model (FLYNCBaseModel): The model instance to serialize.
            file_path (Path): The base file path used when routing external
                fields.

        Returns:
            dict: The serialized content with external and implied fields
            excluded.
        """
        exclude = set()
        for field_name, field_info in type(flync_model).model_fields.items():
            external: External | None = get_metadata(
                field_info.metadata, External
            )
            if external is not None:
                exclude.add(field_name)
                # field will need to be added to to a new separate document
                flync_attribute = getattr(flync_model, field_name)
                self.__handle_load_external_types(
                    file_path, flync_attribute, external, field_name
                )
                continue
            implied: Implied | None = get_metadata(
                field_info.metadata, Implied
            )
            if implied is not None and implied.strategy in (
                ImpliedStrategy.FOLDER_NAME,
                ImpliedStrategy.FILE_NAME,
            ):
                exclude.add(field_name)

        content = flync_model.model_dump(
            exclude=exclude, exclude_unset=self.configuration.exclude_unset
        )
        return content

    def __handle_load_external_types(  # noqa # nosonar
        self,
        file_path: Path,
        flync_attribute,
        external: External,
        field_name: str,
    ):  # noqa # nosonar
        """Dispatch an external field value to the correct save handler.

        Determines the output path from the
        :class:`~flync.core.annotations.External`
        naming strategy, then delegates to the appropriate handler based on
        whether the attribute is a list, dict, or a :class:`FLYNCBaseModel`.

        Args:
            file_path (Path): Base path of the parent document.
            flync_attribute: The field value to save externally.
            external (External): The ``External`` annotation controlling
                naming and output structure.
            field_name (str): The field name, used as the default path when
                ``FIELD_NAME`` strategy is active.

        Raises:
            ValueError: If no valid external path can be determined or the
                attribute type is not supported.
        """
        if flync_attribute is None or not flync_attribute:
            # none field, do nothing
            return
        if (
            external.naming_strategy == NamingStrategy.FIXED_PATH
            and external.path is not None
        ):
            external_path = external.path
        elif external.naming_strategy == NamingStrategy.FIELD_NAME:
            external_path = field_name
        else:
            raise ValueError(
                "Unable to find an external path for {}", field_name
            )
        next_path = file_path / external_path
        if isinstance(flync_attribute, list):
            self.__handle_load_external_types_list(
                flync_attribute, external, next_path, field_name
            )
        elif isinstance(flync_attribute, dict):
            self.__handle_load_external_types_dict(
                flync_attribute, external, next_path
            )
        elif isinstance(flync_attribute, FLYNCBaseModel):
            self.load_flync_model(flync_attribute, next_path)
        else:
            raise ValueError(
                "Unable to load object {} from flync object", field_name
            )

    def __handle_load_external_types_list(  # noqa # nosonar
        self,
        flync_attribute: list,
        external: External,
        next_path: Path,
        field_name: str,
    ):  # noqa # nosonar
        """Save a list of external model instances to their output locations.

        When ``output_structure`` is ``SINGLE_FILE``, all items are
        serialized into a single file. Otherwise each item is written to
        its own file named after its ``name`` attribute (or the implied
        file-name field).

        Args:
            flync_attribute (list): The list of model instances to persist.
            external (External): The ``External`` annotation for this field.
            next_path (Path): The resolved output directory path.
            field_name (str): The field name, used as the key when writing a
                combined single-file output.
        """
        list_content = []
        for attr in flync_attribute:
            if external.output_structure == OutputStrategy.SINGLE_FILE:
                list_content.append(self.__get_model_content(attr, next_path))
            else:
                self.load_flync_model(
                    attr,
                    next_path
                    / get_name(attr, self.__get_field_filename(attr)),
                )
        if len(list_content) != 0:
            self.__save_content_to_file(next_path, {field_name: list_content})

    def __handle_load_external_types_dict(  # noqa # nosonar
        self, flync_attribute: dict, external: External, next_path: Path
    ):  # noqa # nosonar
        """Save a dict of external model instances to their output locations.

        When ``output_structure`` is ``SINGLE_FILE``, all values are
        aggregated into a single file keyed by their original dict keys.
        Otherwise each value is written to its own file named after its key.

        Args:
            flync_attribute (dict): The dict of model instances to persist.
            external (External): The ``External`` annotation for this field.
            next_path (Path): The resolved output directory path.
        """
        dict_content = {}
        for attr_name, attr_value in flync_attribute.items():
            if external.output_structure == OutputStrategy.SINGLE_FILE:
                dict_content[attr_name] = self.__get_model_content(
                    attr_value, next_path
                )
            else:
                self.load_flync_model(attr_value, next_path / attr_name)

    def __handle_generic_types_list(  # noqa # nosonar
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
    ) -> bool:  # noqa # nosonar
        """Load an external ``list`` field from disk into ``module_load_info``.

        Iterates files/folders under the external directory for
        ``FOLDER`` strategy, or delegates to a single-file loader for
        ``SINGLE_FILE`` strategy.

        Args:
            base_type_args (tuple): Generic args of the list annotation.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values;
                updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (str): Dot-path context for object tracking.

        Returns:
            bool: ``True`` if the field was handled, ``False`` otherwise.
        """
        list_item_value = []
        list_element_type = base_type_args[0]
        if OutputStrategy.FOLDER in external.output_structure:
            item_dir = path / external_path
            base_type = get_origin(list_element_type)
            base_type_args = get_args(list_element_type)
            for idx, sub_item_path in enumerate(item_dir.iterdir()):
                if not self.is_path_supported(sub_item_path):
                    logger.warning(
                        "Unrecognized file found in FLYNC workspace: %s",
                        str(sub_item_path),
                    )
                    continue
                list_name = self.name_form_file(sub_item_path)
                list_paths = self.add_list_item_object_path(
                    list_name, current_object_paths, idx
                )
                item_info: dict = {}
                if base_type is Union:
                    self.__handle_generic_types_union(
                        base_type_args,
                        external,
                        sub_item_path.name,
                        field_name,
                        item_info,
                        item_dir,
                        list_paths,
                    )
                    list_item_value.append(item_info[field_name])
                else:
                    list_item_value.append(
                        self.__load_from_path(
                            sub_item_path,
                            list_element_type,
                            field_name,
                            list_paths,
                        )
                    )

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
        """Load an external ``dict`` field from disk into ``module_load_info``.

        Iterates items under the external directory for ``FOLDER`` strategy,
        or delegates to a single-file loader for ``SINGLE_FILE`` strategy.

        Args:
            base_type_args (tuple): Generic args of the dict annotation
                ``(key_type, value_type)``.
            external (External): Annotation controlling the load strategy.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values;
                updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (list[str]): Dot-path contexts for object
                tracking.

        Returns:
            bool: ``True`` if the field was handled, ``False`` otherwise.
        """
        dict_item_value = {}
        dict_element_type = base_type_args[1]
        if OutputStrategy.FOLDER in external.output_structure:
            item_dir = path / external_path
            for sub_item_path in item_dir.iterdir():
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
                    self.update_objects_path(
                        current_object_paths, sub_item_path.name
                    ),
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
                current_object_paths=current_object_paths,
            )
            module_load_info.update(dict_info)
            return True
        return False

    def __handle_generic_types_union(  # noqa # nosonar
        self,
        base_type_args: tuple,
        external,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
        current_object_paths: list[str],
    ) -> bool:  # noqa # nosonar
        """Attempt to load an external ``Union`` field by trying each member
        type.

        Iterates through the union's member types and loads the first one
        that succeeds. ``NoneType`` members are skipped.

        Args:
            base_type_args (tuple): The union member types.
            external: The ``External`` annotation for this field.
            external_path (str): Relative path segment for this field.
            field_name (str): Field name on the parent model.
            module_load_info (dict): Accumulator for loaded field values;
                updated in place.
            path (Path): Absolute path of the current directory.
            current_object_paths (list[str]): Dot-path contexts for object
                tracking.

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
                if issubclass(
                    possible_base_type or possible_type, FLYNCBaseModel
                ):
                    module_load_info[field_name] = self.__load_from_path(
                        path / external_path,
                        possible_type,
                        field_name,
                        current_object_paths,
                    )
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
                        current_object_paths,
                    )
                success_union = True
                break
            # What exception are you trying to catch?
            except:  # noqa: E722, B001
                pass
        return success_union

    def __handle_generic_types(  # noqa # nosonar
        self,
        attribute_type: type,
        base_type: type | None,
        base_type_args: tuple,
        external: External,
        path: Path,
        external_path: str,
        module_load_info: dict,
        field_name: str,
        current_object_paths: list[str],
    ):  # noqa # nosonar
        """Dispatch an external field to the correct type-specific loader.

        Routes ``list``, ``dict``, and ``Union`` types to their dedicated
        handlers. Falls through to a direct model load for concrete
        ``FLYNCBaseModel`` subclasses, or does nothing for optional fields
        whose value is absent.

        Args:
            attribute_type (type): The full (possibly generic) annotation type.
            base_type (type | None): The ``get_origin`` of ``attribute_type``,
                or ``None`` for non-generic types.
            base_type_args (tuple): The ``get_args`` of ``attribute_type``.
            external (External): Annotation controlling load strategy.
            path (Path): Absolute path of the current directory.
            external_path (str): Relative path segment for this field.
            module_load_info (dict): Accumulator for loaded field values;
                updated in place.
            field_name (str): Field name on the parent model.
            current_object_paths (str): Dot-path context(s) for object
                tracking.

        Raises:
            ValueError: If the field type is not supported for external
                loading.
        """
        done = False

        if base_type is list:
            if self.__handle_generic_types_list(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
            ):
                done = True

        elif not done and base_type is dict:
            if self.__handle_generic_types_dict(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
            ):
                done = True

        elif (
            not done
            and base_type is Union
            and self.__handle_generic_types_union(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
                current_object_paths,
            )
        ):
            done = True

        if not done and type(None) in base_type_args:
            # optional type
            done = True

        if done:
            # this field might not have been added to the objects since it's
            # not a flync model and has no document. Add it manually.
            self._add_object_to_path(
                path=path / external_path if external_path else path,
                model=(
                    module_load_info[field_name]
                    if field_name in module_load_info
                    else None
                ),
                current_object_paths=current_object_paths,
                start_line=0,
                end_line=0,
                end_column=0,
                start_column=0,
            )
            return

        if not issubclass(
            get_origin(attribute_type) or attribute_type, FLYNCBaseModel
        ):
            raise ValueError(
                "externally annotated field {} cannot be loaded", field_name
            )
        module_load_info[field_name] = self.__load_from_path(
            path / external_path,
            attribute_type,
            field_name,
            current_object_paths,
        )

    def __load_from_path(  # nosonar # noqa
        self,
        path: PathType,
        current_type: Optional[type[FLYNCBaseModel]] = None,
        current_type_name: Optional[str] = None,
        current_object_paths: Optional[list[str]] = None,
    ) -> FLYNCBaseModel | None:
        """Load and validate a model from a filesystem path.

        Recursively processes all fields of ``current_type``, routing external
        fields to their files/directories and collecting implied values. After
        gathering all field data it validates the dict against the type and
        updates the workspace's object and diagnostic stores.

        Args:
            path (PathType): Directory (or file) path to load from.
            current_type (type[FLYNCBaseModel] | None): The expected model
                type. Defaults to the workspace's configured root model.
            current_type_name (str | None): The parent field name for this
                type, used to reconstruct the correct validation type.
            current_object_paths (list[str] | None): Dot-path context(s) for
                object tracking.

        Returns:
            FLYNCBaseModel | None: The validated model instance, or ``None``
            if validation failed.
        """
        # if no type is passed, then this is the starting point
        if current_type is None:
            current_type = self.configuration.root_model
        current_type.model_rebuild(force=True)
        if isinstance(path, str):
            path = Path(path)
        if not current_object_paths:
            current_object_paths = [""]
        path = path.absolute()
        module_load_info: dict = {}
        # start by loading each field
        for field_name, field_info in current_type.model_fields.items():
            external: External | None = get_metadata(
                field_info.metadata, External
            )
            self.__handle_external_field_load(
                path,
                current_object_paths,
                module_load_info,
                field_name,
                field_info,
                external,
            )
            implied: Implied | None = get_metadata(
                field_info.metadata, Implied
            )
            self.__handle_implied_field_load(
                path, module_load_info, field_name, implied
            )

        # then group all the fields into the same object and return it
        self.__append_to_info_dict(path, module_load_info)

        doc_id = self.document_id_from_path(path)
        if doc_id not in self.documents_diags:
            self.documents_diags[doc_id] = []
        else:
            logger.error("File %s was already loaded.", doc_id)
        if not module_load_info:
            return None
        # collected_errors can be reused/reraised further
        try:
            # might need to recalculate the model type
            # based on expected file structure
            original_type = current_type
            if current_type_name:  # part of a parent
                current_type = self.model_graph.rebuild_type_from_parent(
                    current_type, current_type_name
                )
            relative_path = path.relative_to(
                self.workspace_root.absolute()  # type: ignore[union-attr]
            )
            model, errors = validate_with_policy(
                current_type, module_load_info, relative_path.as_posix()
            )
            # errors should be path specific
            self.documents_diags[self.document_id_from_path(path)].extend(
                errors
            )
            if self.configuration.map_objects:
                self._update_objects(
                    path,
                    model,
                    current_object_paths,
                    parent_name=current_type_name,
                )
            if current_type_name:
                model = self.model_graph.normalize_child_to_parent(
                    original_type, current_type_name, model
                )
            return model
        except ValidationError as e:
            self.documents_diags[self.document_id_from_path(path)].extend(
                e.errors()
            )
            return None

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
                raise ValueError(
                    "Attribute {} has an invalid type.", field_name
                )
            base_type: type | None = get_origin(attribute_type)
            base_type_args = get_args(attribute_type)
            external_path = (
                external.path
                if (
                    (external.naming_strategy == NamingStrategy.FIXED_PATH)
                    and (external.path is not None)
                )
                else field_name
            )
            if OutputStrategy.SINGLE_FILE in external.output_structure:
                external_path += self.configuration.flync_file_extension
                if OutputStrategy.OMMIT_ROOT not in external.output_structure:
                    # the output file is a dictionary
                    # we need to load it accordingly
                    attribute_type = dict[
                        str, attribute_type  # type: ignore[valid-type]
                    ]
                    base_type = get_origin(attribute_type)
                    base_type_args = get_args(attribute_type)
            new_paths = [
                self.new_object_path(current, field_name)
                for current in current_object_paths
            ]
            self.__handle_generic_types(
                attribute_type,
                base_type,
                base_type_args,
                external,
                path,
                external_path,
                module_load_info,
                field_name,
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
        """Merge the contents of a FLYNC file into a model load-info dict.

        Opens the file at ``path``, registers it as a document, and merges
        its parsed YAML content into ``model_load_info``. The merge behaviour
        depends on ``output_strategy``:

        - ``OMMIT_ROOT``: assigns the raw content to
          ``model_load_info[field_name]``.
        - ``FIXED_ROOT``: assigns only the ``fixed_name`` key of the content.
        - Default: updates ``model_load_info`` with all top-level keys.

        Does nothing when ``path`` is not a file or is not a recognised FLYNC
        file extension.

        Args:
            path (Path): Path to the FLYNC YAML file.
            model_load_info (dict): Accumulator dict; updated in place.
            output_strategy (OutputStrategy | None): Optional output strategy
                that controls how the file content is merged.
            field_name (str | None): Target key in ``model_load_info`` for
                ``OMMIT_ROOT`` / ``FIXED_ROOT`` strategies.
            fixed_name (str | None): Key inside the file content to extract
                for ``FIXED_ROOT`` strategy.
        """
        if path.is_file():
            if not self.is_flync_file(path):
                logger.error(
                    "trying to load an unsupported file: %s", str(path)
                )
                return
            with open(path, "r", encoding="utf-8") as direct_data:
                self._open_document(path, direct_data.read())
                content = self.documents[self.document_id_from_path(path)].ast
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
        """Return the field name whose value supplies the output filename.

        Searches the model's fields for one annotated with
        :class:`~flync.core.annotations.Implied` using the ``FILE_NAME``
        strategy.

        Args:
            model (FLYNCBaseModel): The model instance to inspect.

        Returns:
            str | None: The field name to use as the file name, or ``None``
            if no such field exists.
        """
        for field, info in type(model).model_fields.items():
            implied: Implied | None = get_metadata(info.metadata, Implied)
            if implied and implied.strategy == ImpliedStrategy.FILE_NAME:
                return field

        return None

    def generate_configs(self, uri: PathType | None = None):
        """Save the workspace to the given path.

        Creates the output directory (if it does not exist) and writes a simple
        representation of the workspace. If a FLYNCModel has been loaded via
        ``load_flync_model``, it attempts to serialize the model to JSON.

        Args:
            uri (str | Path | None): Optional argument to save specific file
                                    instead of the entire workspace.

        Returns: None
        """
        if uri is not None:
            uri = str(uri)
            if uri not in self.documents:
                raise ValueError(
                    f"Document with URI {uri} not found in workspace."
                )
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
    # region helpers
    def is_path_supported(self, path: PathType):
        """Return whether a path is a directory or a recognised FLYNC file.

        Args:
            path (PathType): The path to check.

        Returns:
            bool: ``True`` if the path is a directory or a FLYNC file.
        """
        if not isinstance(path, Path):
            path = Path(path)
        return path.is_dir() or self.is_flync_file(path)

    def is_flync_file(self, path: PathType):
        """Return whether a path has a recognised FLYNC file extension.

        Args:
            path (PathType): The path to check.

        Returns:
            bool: ``True`` if the path's combined suffixes are in
            :attr:`~WorkspaceConfiguration.allowed_extensions`.
        """
        if not isinstance(path, Path):
            path = Path(path)
        return "".join(path.suffixes) in self.configuration.allowed_extensions

    def name_form_file(self, file_name: str | Path) -> str:
        """Strip all recognised FLYNC file extensions from a filename.

        Iterates over every extension in
        :attr:`~flync.sdk.context.workspace_config.WorkspaceConfiguration.allowed_extensions`
        and removes it as a suffix, leaving the bare stem. If a
        :class:`pathlib.Path` is passed, only its ``name`` component is used.

        Args:
            file_name (str | Path): The filename or path to strip.

        Returns:
            str: The filename with all FLYNC extensions removed
            (e.g. ``"my_ecu.flync.yaml"`` → ``"my_ecu"``).
        """
        if isinstance(file_name, Path):
            file_name = file_name.name
        for extension in self.configuration.allowed_extensions:
            file_name = file_name.replace(extension, "")
        return file_name

    def fill_path_from_object(  # noqa # nosonar
        self, model_object: FLYNCBaseModel, object_path: str
    ) -> str:  # noqa # nosonar
        """Replace placeholder segments in an object path with concrete keys.

        Traverses the workspace's root model following ``object_path``,
        substituting ``[]`` with the actual list index and ``{}`` with the
        actual dict key when ``model_object`` is found.

        Args:
            model_object (FLYNCBaseModel): The model instance to locate.
            object_path (str): Dot-separated path containing ``[]`` or ``{}``
                placeholders.

        Returns:
            str: The resolved dot-separated path with concrete index/key
                values.
        """
        parts = object_path.split(".")
        current_parent = self.flync_model
        for parts_idx, part in enumerate(parts):
            if part == "[]":
                for idx, obj in enumerate(
                    current_parent  # type: ignore[arg-type]
                ):
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

    __cached_uris: dict[Path, Path] = {}

    def document_id_from_path(self, doc_path: Path) -> str:
        """Return the workspace-relative string identifier for a document path.

        Args:
            doc_path (Path): An absolute path to a document file.

        Returns:
            str: The path relative to the workspace root, as a string.
        """
        if doc_path not in self.__cached_uris:
            self.__cached_uris[doc_path] = doc_path.absolute().relative_to(
                self.workspace_root  # type: ignore[arg-type]
            )
        return self.__cached_uris[doc_path].as_posix()

    @staticmethod
    def new_object_path(current_path: str, new_object_name: int | str) -> str:
        """Extend a dot-separated object path with a new segment.

        Args:
            current_path (str): The existing dot-separated path.
            new_object_name (int | str): The segment to append.

        Returns:
            str: The extended path string.
        """
        return ".".join([current_path, str(new_object_name)])

    def update_objects_path(
        self, current_paths: list[str], new_object_name: str
    ) -> list[str]:
        """Extend every path in a list with a new segment.

        Args:
            current_paths (list[str]): Existing dot-separated paths.
            new_object_name (str): The segment to append to each path.

        Returns:
            list[str]: New list of extended path strings.
        """
        return [
            self.new_object_path(current_path, new_object_name)
            for current_path in current_paths
        ]

    # endregion

    # region semantic APIs (SDK)

    def _update_objects(  # nosonar # noqa
        self,
        path: Path,
        model: FLYNCBaseModel | None,
        current_object_paths: list[str],
        node: Node | None = None,
        parent_name: str | None = None,
    ):
        """Recursively register model values and their source positions.

        Walks the YAML AST node alongside the validated model, calling
        :meth:`_add_object_to_path` for every value encountered so that
        each semantic object is associated with its source location.

        Args:
            path (Path): Absolute path of the document containing this node.
            model (FLYNCBaseModel): The validated model value at this node.
            current_object_paths (str | list[str]): Dot-path context(s) for
                the current model value.
            node (Node | None): The ruamel.yaml AST node corresponding to
                ``model``. Defaults to the document's root compose AST.
            parent_name (str | None): The field name on the parent that
                points to this node, used for sequence items.
        """
        start_line = 0
        end_line = 0
        start_column = 0
        end_column = 0
        if isinstance(model, RootModel):
            model = model.root
        path_id = self.document_id_from_path(path)
        if model is not None and path_id in self.documents:
            # object is all external fields
            # should already be updated
            document = self.documents[path_id]
            if node is None:
                node = document.compose_ast
            if isinstance(node, MappingNode):
                self._update_mapping_node_objects(
                    path, model, current_object_paths, node
                )
            elif isinstance(node, SequenceNode):
                self._update_sequence_node_objects(
                    path, model, current_object_paths, node, parent_name
                )
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
            path,
            model,
            current_object_paths,
            start_line,
            end_line,
            start_column,
            end_column,
        )

    def _update_sequence_node_objects(
        self, path, model, current_object_paths, node, parent_name
    ):
        for idx, item in enumerate(node.value):
            list_paths = self.add_list_item_object_path(
                getattr(model[idx], "name", None),  # type: ignore
                current_object_paths,
                idx,
            )
            self._update_objects(
                path,
                model[idx],  # type: ignore[index]
                list_paths,
                item,
                parent_name=parent_name,
            )

    def _update_mapping_node_objects(
        self, path, model, current_object_paths, node
    ):
        for key_node, val_node in node.value:
            if isinstance(model, dict):
                model_value = model[key_node.value]
            else:
                model_value = getattr(model, key_node.value, None)
                if model_value is None:
                    field_alias = get_name_by_alias(
                        type(model), key_node.value
                    )
                    model_value = getattr(model, field_alias)
            self._update_objects(
                path,
                model_value,
                self.update_objects_path(current_object_paths, key_node.value),
                val_node,
                key_node.value,
            )

    def add_list_item_object_path(self, item_name, current_object_paths, idx):
        """Build the object path(s) for a single list item.

        Depending on
        :attr:`~flync.sdk.context.workspace_config.WorkspaceConfiguration.list_objects_mode`,
        the item may be registered under its numeric index, its name, or both:

        - :attr:`~flync.sdk.context.workspace_config.ListObjectsMode.INDEX`:
          appends the zero-based integer index as a path segment.
        - :attr:`~flync.sdk.context.workspace_config.ListObjectsMode.NAME`:
          appends ``item_name`` as an additional path segment when the name is
          non-empty. For external (folder-based) lists the name comes from the
          file/directory stem; for inline lists it comes from the model's
          ``name`` attribute.

        Both flags are active by default, so a list item is accessible under
        two IDs simultaneously (e.g. ``controllers.0`` and
        ``controllers.my_ctrl``).

        Args:
            item_name (str | None): Name of the list item, or ``None`` /
                empty string when the item has no name.
            current_object_paths (list[str]): Parent path(s) to extend.
            idx (int): Zero-based position of the item in the list.

        Returns:
            list[str]: New list of object paths for this item.
        """
        list_paths = []
        if (
            ListObjectsMode.INDEX in self.configuration.list_objects_mode
        ) or not item_name:
            list_paths += self.update_objects_path(current_object_paths, idx)
        if (
            ListObjectsMode.NAME in self.configuration.list_objects_mode
        ) and item_name:
            list_paths += self.update_objects_path(
                current_object_paths, item_name
            )

        return list_paths

    def _add_object_to_path(  # noqa # nosonar
        self,
        path: Path,
        model,
        current_object_paths: list[str],
        start_line,
        end_line,
        start_column,
        end_column,
    ):  # noqa # nosonar
        """Register a model value and its source location for each given path.

        Creates entries in :attr:`objects` and :attr:`sources` for every path
        in ``current_object_paths``. Skips paths that are already registered.

        Args:
            path (Path): Absolute path of the document containing the object.
            model: The semantic object value to store.
            current_object_paths (list[str]): Dot-separated object ids to
                register.
            start_line (int): 1-based start line of the object in the document.
            end_line (int): 1-based end line of the object.
            start_column (int): 1-based start column.
            end_column (int): 1-based end column.
        """
        for object_path in current_object_paths:
            object_id = ObjectId(object_path.strip("."))
            if object_id in self.objects:
                return
            self.objects[object_id] = SemanticObject(object_id, model)
            self.sources[object_id] = SourceRef(
                self.document_id_from_path(path),
                Range(
                    start=Position(start_line, start_column),
                    end=Position(end_line, end_column),
                ),
            )

    def get_object(self, id: ObjectId) -> SemanticObject:
        """Retrieve a semantic object by its ObjectId.

        Args:
            id (ObjectId):
                Identifier of the semantic object.

        Returns:
            SemanticObject:
                The requested semantic object.
        """
        return self.objects[id]

    def has_object(self, id: ObjectId) -> bool:
        """Checks if a specific key exists within a dictionary of objects.

        Args:
            id (ObjectId):
                Identifier of the semantic object.

        Returns:
            bool:
                True if the key is found, False otherwise.
        """
        return id in self.objects.keys()

    def list_objects(self) -> list[ObjectId]:
        """Return a list of all ObjectIds present in the workspace.

        Returns:
            list[ObjectId]:
                List of object identifiers.
        """
        return list(self.objects.keys())

    def get_definition(
        self, object_id: ObjectId, field_name: str
    ) -> Optional[ObjectId]:
        """
        Resolve and return definition identifiers for a given field reference.
        Args:
            object_id (ObjectId):
                Identifier of the semantic object.
            field_name (str)
                The field name of referencing object
        Returns

            ObjectId
                A list of object identifiers that match the resolved reference
                criteria. The list may be empty if no definitions are found
                or if the field has no valid reference metadata.
        """

        def_id: Optional[ObjectId] = None
        sematic_obj: SemanticObject = self.get_object(object_id)
        model_type = type(sematic_obj.model)
        if not hasattr(model_type, "model_fields"):
            return def_id

        field_name = get_field_name_from_alias(model_type, field_name)
        fields = model_type.model_fields
        field_info = fields[field_name]
        ref: Reference | None = get_metadata(field_info.metadata, Reference)
        if ref and ReferenceStrategy.PRIVATE_ATTR in ref.reference_strategy:
            if def_obj := getattr(sematic_obj.model, ref.source, None):
                if so := self.get_semantic_object_from_model(def_obj):
                    def_id = so.id
        return def_id

    def get_references_of(self, object_id: ObjectId) -> list[ObjectId]:
        """Return all ObjectIds that reference the given object.

        Iterates over every semantic object in the workspace and checks whether
        any of its fields are defined by the same model as the target object.
        For each matching field, the concrete path to that field is collected
        via `find_path_from_field`.

        Args:
            object_id (ObjectId):
                The id of the object whose references should be found.

        Returns:
            list[ObjectId]:
                A list of ObjectIds representing all fields across the
                workspace that reference the given object.
        """
        refs: list[ObjectId] = []
        current_obj = self.get_object(object_id)

        for semantic_obj in self.objects.values():
            fields: dict | None = getattr(
                type(semantic_obj.model), "model_fields", None
            )
            if fields is None:
                continue

            for field, info in fields.items():
                if obj_id_def := self.get_definition(semantic_obj.id, field):
                    model_def = self.get_object(obj_id_def)
                    if model_def.model is current_obj.model:
                        self.find_path_from_field(
                            object_id, refs, semantic_obj, field, info
                        )
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

        Tries to build the path as `<semantic_obj.id>.<field>`, falling back to
        `<semantic_obj.id>.<info.alias>` when the first candidate is not
        present in the workspace. Raises if neither candidate exists.

        Args:
            object_id (ObjectId):
                The id of the target object being referenced (used in the
                error message when the path cannot be resolved).
            refs (list[ObjectId]):
                Accumulator list to which the resolved path is appended.
            semantic_obj (SemanticObject):
                The semantic object that owns the field being inspected.
            field (str):
                The field name on `semantic_obj`'s model.
            info:
                The Pydantic `FieldInfo` for the field, used to access the
                field alias as a fallback path segment.

        Raises:
            ValueError:
                If neither the field name nor its alias resolves to a known
                object in the workspace.
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

    def get_semantic_object_from_model(
        self, model: FLYNCBaseModel
    ) -> SemanticObject | None:
        """Find and return the semantic object that corresponds
        to a validated Flync object.

        Args:
            model (FLYNCBaseModel):
                Validated Flync model.

        Returns:
            SemanticObject | None:
                Optional semantic object that corresponds to Flync object.
        """
        for semantic_object in self.objects.values():
            if model is semantic_object.model:
                return semantic_object

        return None

    # endregion

    # region source APIs (LSP)

    def get_source(self, id: ObjectId) -> SourceRef:
        """Retrieve the source reference for a given ObjectId.

        Args:
            id (ObjectId):
                Identifier of the object.

        Returns:
            SourceRef:
                The source reference associated with the object.
        """
        return self.sources[id]

    def objects_at(
        self, uri: str, line: int, character: int
    ) -> list[ObjectId]:
        """Return the list of ObjectIds located at the specified position in a
        document.

        Args:
            uri (str):
                Document URI.
            line (int):
                1-based line number, consistent with the
                :class:`~flync.sdk.workspace.source.Position` values stored
                during YAML parsing.
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
            if (
                line > r.start.line
                or (line == r.start.line and character >= r.start.character)
            ) and (
                line < r.end.line
                or (line == r.end.line and character <= r.end.character)
            ):
                result.append(oid)
        return result

    # endregion
