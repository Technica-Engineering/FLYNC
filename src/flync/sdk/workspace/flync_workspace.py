"""
Workspace module for FLYNC SDK.

Provides classes and functions to manage workspace operations.
"""

from pathlib import Path
from typing import Dict, Optional, Union, get_args, get_origin

import yaml
from pydantic_core import ErrorDetails, ValidationError

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions_handling import (
    errors_to_init_errors,
    validate_with_policy,
)
from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.utils.field_utils import get_metadata, get_name

from .document import Document


class FLYNCWorkspace:
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

    def __init__(
        self,
        name: str,
        workspace_path: Path | str = "",
        configuration: WorkspaceConfiguration | None = None,
    ):
        """Initialize the workspace with the given name.

        Args:
            name (str): The name of the workspace.
        """
        self.name = name
        self.configuration = configuration or WorkspaceConfiguration()
        # documents
        self.documents: Dict[str, Document] = {}
        # root information (if any)
        self.flync_model: Optional[FLYNCModel] = None
        self.workspace_root: Optional[Path] = None
        if isinstance(workspace_path, str):
            if not workspace_path:
                raise ValueError(
                    "Passed an invalid value for workspace root {}",
                    workspace_path,
                )
            workspace_path = Path(workspace_path)
        self.workspace_root = workspace_path
        self.load_errors: list[ErrorDetails] = []

    # region creator
    @classmethod
    def load_model(
        cls,
        flync_model: FLYNCModel,
        workspace_name: str | None = "generated_workspace",
        file_path: Path | str = "",
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
        output = FLYNCWorkspace(name=workspace_name, workspace_path=file_path)
        # assign this to the workspace if it's the root object
        output.flync_model = flync_model
        output.__load_flync_model(flync_model, file_path)
        return output

    @classmethod
    def load_workspace(
        cls, workspace_name: str, workspace_path: Path | str
    ) -> "FLYNCWorkspace":
        """loads a workspace object from a location of the Yaml Configuration.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """
        output = FLYNCWorkspace(
            name=workspace_name, workspace_path=workspace_path
        )
        model = output.__load_from_path(workspace_path)

        if not isinstance(model, FLYNCModel):
            raise ValidationError.from_exception_data(
                title=f"Model ({workspace_name}) Creation Error",
                line_errors=errors_to_init_errors(output.load_errors),
            )
        output.flync_model = model
        return output

    # endregion
    # region ingestion
    def _open_document(self, uri: Path | str, text: str):
        """Open a document, parse it, and add it to the workspace.

        Args:
            uri (str): The document's URI.

            text (str): The raw text content of the document.

        Returns: None
        """
        if isinstance(uri, Path):
            uri = uri.as_uri()
        doc = Document(uri, text)
        doc.parse()
        self.documents[uri] = doc

    def _update_document_text(self, uri: str, text: str):
        """Update the text of an existing document and re-apply analysis.

        Args:
            uri (str): The document's URI.

            text (str): The new text content for the document.

        Returns: None
        """
        doc = self.documents[uri]
        doc.update_text(text)

    def __load_flync_model(
        self, flync_model: FLYNCBaseModel, file_path: Path | str = ""
    ):
        """Load a FLYNCModel into the workspace.

        This is a placeholder implementation that stores the model for later
        use.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)
        content = self.__get_model_content(flync_model, file_path)
        self.__save_content_to_file(file_path, content)

    def __save_content_to_file(self, file_path: Path, content):
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
        doc = Document(uri, content)
        self.documents[str(uri)] = doc
        self.generate_configs(uri)

    def __get_model_content(self, flync_model: FLYNCBaseModel, file_path):
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
            if (
                implied is not None
                and implied.strategy == ImpliedStrategy.FOLDER_NAME
            ):
                exclude.add(field_name)

        content = flync_model.model_dump(
            exclude=exclude, exclude_unset=self.configuration.exclude_unset
        )
        return content

    def __handle_load_external_types(
        self,
        file_path: Path,
        flync_attribute,
        external: External,
        field_name: str,
    ):

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
            self.__load_flync_model(flync_attribute, next_path)
        else:
            raise ValueError(
                "Unable to load object {} from flync object", field_name
            )

    def __handle_load_external_types_list(
        self,
        flync_attribute: list,
        external: External,
        next_path: Path,
        field_name: str,
    ):
        list_content = []
        for attr in flync_attribute:
            if external.output_structure == OutputStrategy.SINGLE_FILE:
                list_content.append(self.__get_model_content(attr, next_path))
            else:
                self.__load_flync_model(
                    attr,
                    next_path
                    / get_name(attr, self.__get_field_filename(attr)),
                )
        if len(list_content) != 0:
            self.__save_content_to_file(next_path, {field_name: list_content})

    def __handle_load_external_types_dict(
        self, flync_attribute: dict, external: External, next_path: Path
    ):
        dict_content = {}
        for attr_name, attr_value in flync_attribute.items():
            if external.output_structure == OutputStrategy.SINGLE_FILE:
                dict_content[attr_name] = self.__get_model_content(
                    attr_value, next_path
                )
            else:
                self.__load_flync_model(attr_value, next_path / attr_name)

    def __handle_generic_types_list(
        self,
        base_type_args: tuple,
        external: External,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
    ) -> bool:
        list_item_value = []
        list_element_type = base_type_args[0]
        if external.output_structure == OutputStrategy.FOLDER:
            item_dir = path / external_path
            base_type = get_origin(list_element_type)
            base_type_args = get_args(list_element_type)
            for sub_item_path in item_dir.iterdir():
                item_info: dict = {}
                if base_type is Union:
                    self.__handle_generic_types_union(
                        base_type_args,
                        external,
                        sub_item_path.name,
                        field_name,
                        item_info,
                        item_dir,
                    )
                    list_item_value.append(item_info[field_name])
                else:
                    list_item_value.append(
                        self.__load_from_path(sub_item_path, list_element_type)
                    )
            module_load_info[field_name] = list_item_value
            return True

        return False

    def __handle_generic_types_dict(
        self,
        base_type_args: tuple,
        external,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
    ) -> bool:
        dict_item_value = {}
        dict_element_type = base_type_args[1]
        if external.output_structure == OutputStrategy.FOLDER:
            item_dir = path / external_path
            for sub_item_path in item_dir.iterdir():
                dict_item_value[sub_item_path.name] = self.__load_from_path(
                    sub_item_path, dict_element_type
                )
            module_load_info[field_name] = dict_item_value
            return True
        return False

    def __handle_generic_types_union(
        self,
        base_type_args: tuple,
        external,
        external_path: str,
        field_name: str,
        module_load_info: dict,
        path: Path,
    ) -> bool:
        success_union = False
        for possible_type in base_type_args:
            try:
                if possible_type is None:
                    # optional external field, don't do anything
                    continue
                possible_base_type = get_origin(possible_type)
                if issubclass(
                    possible_base_type or possible_type, FLYNCBaseModel
                ):
                    module_load_info[field_name] = self.__load_from_path(
                        path / external_path, possible_type
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
    ):

        done = False

        if base_type is list:
            if self.__handle_generic_types_list(
                base_type_args,
                external,
                external_path,
                field_name,
                module_load_info,
                path,
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
            )
        ):
            done = True

        if not done and attribute_type is type(None):
            # optional type
            done = True

        if done:
            return

        if not issubclass(
            get_origin(attribute_type) or attribute_type, FLYNCBaseModel
        ):
            raise ValueError(
                "externally annotated field {} cannot be loaded", field_name
            )
        module_load_info[field_name] = self.__load_from_path(
            path / external_path, attribute_type
        )

    def __load_from_path(
        self,
        path: Path | str,
        current_type: Optional[type[FLYNCBaseModel]] = None,
    ) -> FLYNCBaseModel | None:
        # if no type is passed, then this is the starting point
        if current_type is None:
            current_type = FLYNCModel
        if isinstance(path, str):
            path = Path(path)
        module_load_info: dict = {}
        # start by loading each field
        for field_name, field_info in current_type.model_fields.items():
            external: External | None = get_metadata(
                field_info.metadata, External
            )
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
                    self.__append_to_info_dict(
                        path / external_path,
                        module_load_info,
                        external.output_structure,
                        field_name,
                        external.root,
                    )
                    continue
                self.__handle_generic_types(
                    attribute_type,
                    base_type,
                    base_type_args,
                    external,
                    path,
                    external_path,
                    module_load_info,
                    field_name,
                )
            implied: Implied | None = get_metadata(
                field_info.metadata, Implied
            )
            if implied is not None:
                if implied.strategy == ImpliedStrategy.FOLDER_NAME:
                    module_load_info[field_name] = path.name

        # then group all the fields into the same object and return it
        self.__append_to_info_dict(path, module_load_info)

        # collected_errors can be reused/reraised further
        try:
            model, errors = validate_with_policy(
                current_type, module_load_info
            )
            self.load_errors.extend(errors)
            return model
        except ValidationError as e:
            self.load_errors.extend(e.errors())
            return None

    def __append_to_info_dict(
        self,
        path: Path,
        modle_load_info: dict,
        output_strategy: Optional[OutputStrategy] = None,
        field_name: Optional[str] = None,
        fixed_name: Optional[str] = None,
    ):
        if path.is_file():
            with open(path, "r", encoding="utf-8") as direct_data:
                content = yaml.safe_load(direct_data)
                self._open_document(path, direct_data.read())
                if output_strategy:
                    if OutputStrategy.OMMIT_ROOT in output_strategy:
                        modle_load_info[field_name] = content
                        return
                    elif OutputStrategy.FIXED_ROOT in output_strategy:
                        modle_load_info[field_name] = content[fixed_name]
                        return
                modle_load_info.update(content)

    @staticmethod
    def __get_field_filename(model: FLYNCBaseModel):
        for field, info in type(model).model_fields.items():
            implied: Implied | None = get_metadata(info.metadata, Implied)
            if implied and implied.strategy == ImpliedStrategy.FILE_NAME:
                return field

        return None

    def generate_configs(self, uri: Path | str | None = None):
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
