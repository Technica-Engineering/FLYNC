"""Main module."""

import abc
import logging
import warnings
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Union,
)

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    IPvAnyAddress,
    conset,
    field_serializer,
    field_validator,
    model_validator,
)

import flync.core.utils.common_validators as common_validators
from flync.core.annotations.external import External, OutputStrategy
from flync.core.base_models import DictInstances, FLYNCBaseModel
from flync.core.utils.exceptions import err_major, err_minor
from flync.model.flync_4_metadata import SOMEIPServiceMetadata
from flync.model.flync_4_someip.someip_datatypes import AllTypes


class SOMEIPField(FLYNCBaseModel):
    """
    Base datastructure to design a SOME/IP Field

    Parameters
    ----------
    name : str
        Name of the Field.

    parameters list[:class:`~SOMEIPParameters`]
        List of Parameters of the Field.

    description : str, optional
        Description of the Field.

    notifier_id : int, optional
        Identifies the Field Notifier.
        Must be greater than 0 and lower or equal than 0xFFFF.
        Defaults to 1.

    setter_id : int, optional
        Identifies the Field Setter.
        Must be greater than 0 and lower or equal than 0xFFFF.

    getter_id : int, optional
        Identifies the Field Getter.
        Must be greater than 0 and lower or equal than 0xFFFF.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(description="name of the field")
    parameters: Annotated[
        Optional[List["SOMEIPParameter"]],
        Field(description="name of the parameter"),
    ] = Field(default=[])
    description: Optional[str] = Field(default="")

    notifier_id: Optional[
        Annotated[int, Field(gt=0, le=0xFFFF, strict=True)]
    ] = Field(description="identifies the field setter", default=None)
    setter_id: Optional[
        Annotated[int, Field(gt=0, le=0xFFFF, strict=True)]
    ] = Field(description="identifies the field setter", default=None)
    getter_id: Optional[
        Annotated[int, Field(gt=0, le=0xFFFF, strict=True)]
    ] = Field(description="identifies the field getter", default=None)

    @property
    def id(self):
        return self.notifier_id

    @model_validator(mode="after")
    def validate_at_least_one_identifier_to_be_defined(self):
        """Validate that at least one identifier of the
        field is defined. [feat_req_someip_632]"""
        if (
            self.notifier_id is not None
            or self.setter_id is not None
            or self.getter_id is not None
        ):
            err_minor(
                f'Field "{self.name}": [feat_req_someip_632] - '
                "A field without a setter and without a getter and "
                "without a notifier shall not exist."
            )
        return self


class SOMEIPParameter(FLYNCBaseModel):
    """Definition of Parameters for SOME/IP.

    Parameters
    ----------

    name : str
        Identifies the parameter.

    description : str, optional
        Human-readable description of the datatype.

    type : :class:`~flync.model.flync_4_someip.someip_datatypes.AllTypes`
        Datatype of the Parameter.
    """

    name: str = Field(description="identifies the parameter")
    description: Optional[str] = Field("", description="Optional description")
    datatype: "AllTypes"

    # @field_serializer("type")
    # def serialize_type(self, type):
    #    if type is not None:
    #        return getattr(type, "type", str(type))

    # @field_validator("type", mode="before")
    # def wrap_type(cls, v):
    #    if isinstance(v, str):
    #        return {"type": v}
    #    return v


class SOMEIPEvent(FLYNCBaseModel):
    """
    Defines a SOME/IP event definition.

    This model is used to describe a SOME/IP event, including its identifier,
    reliability settings, optional E2E protection configuration, and the list
    of parameters that the event transports.

    Parameters
    ----------
    name : str
        Name of the event.

    description : str, optional
        Human-readable description of the event.

    id : int
        Unique identifier of the event.
        Must be greater than 0 and lower or equal than 0xFFFF.

    reliable : bool
        Indicates whether the event is transmitted reliably.

    parameters list[:class:`~SOMEIPParameters`]
        Parameters of the Event
    """

    INSTANCES_BY_NAME: ClassVar[Dict[str, "SOMEIPEvent"]] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(description="name of the event")
    description: Optional[str] = Field(default="")
    id: Annotated[int, Field(gt=0, le=0xFFFF, strict=True)] = Field(
        description="identifies the event"
    )
    reliable: bool = Field(default=False)
    # e2e: Optional[E2EConfig]
    parameters: Annotated[
        Optional[List["SOMEIPParameter"]],
        Field(description="name of the parameter"),
    ] = Field(default=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.INSTANCES_BY_NAME[self.name] = self


def validate_unique_id(
    events: list[SOMEIPEvent | SOMEIPField],
) -> list[SOMEIPEvent | SOMEIPField]:
    """Validate that events/fields are included in an eventgroup only once."""
    ensure_unique(
        events, key=lambda e: e.id, label="id", fmt=lambda x: f"0x{x:04X}"
    )
    return events


def validate_unique_e2e_data_id(
    events: list[SOMEIPEvent | SOMEIPField],
) -> list[SOMEIPEvent | SOMEIPField]:
    """Validate that E2E Events in one Service are uniquely identified."""
    only_events = [
        e for e in events if hasattr(e, "e2e") and e.e2e is not None
    ]
    ensure_unique(
        only_events,
        key=lambda e: int(e.e2e.data_id),
        label="e2e.data_id",
        fmt=lambda x: f"0x{x:08X}",
    )
    return events


def ensure_unique(
    items: Iterable[Any],
    key: Callable[[Any], Any],
    label: str = "key",
    fmt: Callable[[Any], str] | None = None,
) -> None:
    """
    Check, if key(item) is unique for all items.
    - label: Name of the field in error messages (e.g. 'data_id' or 'id').
    - fmt: optional formatter (e.g. hex format for numbers).
    Raises err_major on duplicates.
    """
    from collections import defaultdict

    buckets = defaultdict(list)
    for it in items:
        k = key(it)
        buckets[k].append(it)

    dups = {k: v for k, v in buckets.items() if len(v) > 1}
    if dups:
        lines = []
        for k, vs in dups.items():
            k_str = fmt(k) if fmt else str(k)
            names = []
            for it in vs:
                nm = (
                    getattr(it, "name", None)
                    if hasattr(it, "name")
                    else (it.get("name") if isinstance(it, dict) else None)
                )
                names.append(nm or "<unnamed>")
            lines.append(
                f"{label}={k_str} appears {len(vs)} times: {', '.join(names)}"
            )
        raise err_major("Duplicates found:\n  " + "\n  ".join(lines))


class SOMEIPEventgroup(FLYNCBaseModel):
    """
    Main datastructure to model a SOME/IP Eventgroup.

    Parameters
    ----------
    name : str
        Name of the Eventgroup.

    description : str, optional

    id : int
        Identifies the Eventgroup.
        Must be greater than 0 and lower or equal than 0xFFFF.

    multicast_threshold : int, optional
        Identifies the multicast threshold.
        Must be greater than 0.
        Defaults to 0.

    events: list[:class:`~SOMEIPEvent` | :class:`~SOMEIPField`]
        The events and fields this eventgroup contains.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(description="name of the eventgroup")
    description: Optional[str] = Field(default="")
    id: Annotated[int, Field(gt=0, le=0xFFFF, strict=True)] = Field(
        description="identifies the eventgroup"
    )
    multicast_threshold: Optional[int] = Field(
        default=0,
        gt=0,
        strict=True,
        description="identifies the multicast threshold",
    )
    events: Annotated[
        List[SOMEIPEvent | SOMEIPField],
        conset(item_type=SOMEIPEvent | SOMEIPField, min_length=1),
        AfterValidator(validate_unique_id),
        AfterValidator(validate_unique_e2e_data_id),
    ] = Field(description="the events this eventgroup contains")

    @classmethod
    def __lookup_event_by_name(cls, value: SOMEIPEvent | SOMEIPField):
        """looks up a single event if just the name was provided"""
        if type(value) is not str:
            return value
        lookup_event: Optional[SOMEIPEvent] = (
            SOMEIPEvent.INSTANCES_BY_NAME.get(value)
        )
        if not lookup_event:
            logging.info(f"!!!!did not find event by name {value}")
        return lookup_event

    @field_validator("events", mode="before")
    @classmethod
    def _lookup_events_by_name(cls, value: List[SOMEIPEvent | SOMEIPField]):
        """_lookup_events_by_name Look up events by name .

        [extended_summary]

        :param value: [description]
        :type value: List[Event | Field | Str]
        """
        new_value = list(map(cls.__lookup_event_by_name, value))
        return new_value

    @property
    def fields(self) -> List[SOMEIPField]:
        """fields Returns the list of fields that this eventgroup contains."""
        return [e for e in self.events if isinstance(e, SOMEIPField)]


class SOMEIPTP(FLYNCBaseModel):
    """SOME/IP Transport Protocol configuration.

    Parameters
    ----------

    enabled : bool
        Indicates whether SOME/IP-TP is enabled or not.
        Defaults to False.

    max_segment_length : int
        maximum segment length.
        Defaults to 0.
    """

    enabled: bool = Field(default=False)
    max_segment_length: int = Field(
        default=0, description="maximum segment length"
    )


class SOMEIPMethod(FLYNCBaseModel):
    """
    Datastructure to model SOME/IP methods.

    Parameters
    ----------
    name : str
        Name of the Method.

    description : str, optional
        Description of the Method.

    type : Literal["request_response", "fire_and_forget"]
        Type of the Method.

    id : int
        Unique method identifier for the service interface.
        Must be greater than 0 and lower or equal than 0xFFFF.

    reliable : bool
        Indicates whether the event is transmitted reliably.

    someip_tp : :class:`~SOMEIPTP`
        SOME/IP Transport Protocol configuration for this method.

    input_parameters : list[:class:`~SOMEIPParameters`]
        The parameters of the Request

    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(description="name of the method")
    description: Optional[str] = Field(
        description="a short description on what this method does", default=""
    )
    type: Literal["request_response", "fire_and_forget"]
    id: Annotated[int, Field(gt=0, le=0xFFFF, strict=True)] = Field(
        gt=0,
        strict=True,
        description="method identifier unique for the service interface",
    )
    reliable: bool = Field(default=False)
    someip_tp: Optional[SOMEIPTP] = Field(
        description="SOME/IP Transport Protocol configuration for this method",
        default=None,
    )
    input_parameters: Annotated[
        Optional[List["SOMEIPParameter"]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SOMEIPRequestResponseMethod(SOMEIPMethod):
    """
    Allows to model SOME/IP methods which will return a response.

    Parameters
    ----------

    output_parameters : list[:class:`~SOMEIPParameters`], optional
        The parameters of the Response

    """

    type: Literal["request_response"] = "request_response"
    output_parameters: Annotated[
        Optional[List["SOMEIPParameter"]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SOMEIPFireAndForgetMethod(SOMEIPMethod):
    """
    Allows to model SOME/IP methods which will not return a response.
    """

    type: Literal["fire_and_forget"] = "fire_and_forget"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SOMEIPServiceInterface(DictInstances):
    """
    Class to create a SOME/IP service interface definition.

    Parameters
    ----------

    name : str
        Name of the service

    description : str, optional

    id : int
        Unique identifier for the service.
        Must be greater than 0 and lower or equal than 0xFFFF.

    major_version : int
        The major version of this service interface.
        Must be greater than 0 and lower or equal than 0xFF.

    minor_version : int
        The minor version of this service interface.
        Must be greater than 0 and lower or equal than 0xFFFFFFFF.

    fields : List[ :class:`~SOMEIPField`]
        Fields of the service.

    events : List[:class:`~SOMEIPEvent`]
        Events of the service.

    eventgroups : List[:class:`~SOMEIPEventgroup`]
        Eventgroups of the service.

    methods : List[ :class:`~SOMEIPFireAndForgetMethod` | \
    :class:`~SOMEIPRequestResponseMethod` ]
        Methods of the service.

    meta : :class:`~flync.model.flync_4_metadata.SOMEIPServiceMetadata`
        Metadata for the SOME/IP Service.
    """

    INSTANCES: ClassVar[Dict[Any, "SOMEIPServiceInterface"]] = {}
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(description="name of the service")
    description: Optional[str] = Field(default="")
    id: Annotated[int, Field(gt=0, le=0xFFFF, strict=True)] = Field(
        description="identifies the service"
    )

    major_version: Annotated[int, Field(ge=0, le=0xFF, strict=True)] = Field(
        description="the major version of this service interface", default=0
    )
    minor_version: Annotated[int, Field(ge=0, le=0xFFFFFFFF, strict=True)] = (
        Field(
            description="the minor version of this service interface",
            default=0,
        )
    )
    fields: Annotated[
        Optional[List[SOMEIPField]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[], description="fields of the service")
    events: Annotated[
        Optional[List[SOMEIPEvent]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[], description="events of the service")
    eventgroups: Annotated[
        Optional[List[SOMEIPEventgroup]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[], description="eventgroups of the service")
    methods: Annotated[
        List[Union[SOMEIPFireAndForgetMethod, SOMEIPRequestResponseMethod]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[], description="methods of the service")
    meta: SOMEIPServiceMetadata = Field()

    def get_dict_key(self):
        return self.id

    @model_validator(mode="after")
    def validate_for_notifiers_without_eventgroup(self):
        """Validate that all notifiers are in at least one eventgroup."""
        all_notifiers_in_eg = []
        for eg in self.eventgroups:
            all_notifiers_in_eg.extend(eg.events)
        field_notifiers = [f for f in self.fields if f.notifier_id is not None]
        for notifier in self.events + field_notifiers:
            if notifier not in all_notifiers_in_eg:
                warnings.warn(
                    f"Notifier '{notifier.name}' is not assigned"
                    " to an eventgroup",
                    stacklevel=2,
                )
        return self

    @model_validator(mode="after")
    def validate_service_owns_elements_of_eventgroups(self):
        """Validate that eventgroups' elements are in
        events/fields of service."""
        for eg in self.eventgroups:
            for event in eg.events:
                if event in (self.events + self.fields):
                    err_minor(
                        f'Eventgroup references "{event.name}", '
                        "but it is not in events/fields of Service"
                        f'"{self.name}"'
                    )
        return self

    @model_validator(mode="after")
    def validate_all_identifiers_to_be_unique(self):
        """Validate that all identifiers in service
        are unique. [feat_req_someip_56]"""
        ids = {}
        for event in self.events:
            ids.setdefault(event.id, []).append(("id", event))
        for field in self.fields:
            ids.setdefault(field.notifier_id, []).append(
                ("notifier_id", field)
            )
            ids.setdefault(field.getter_id, []).append(("getter_id", field))
            ids.setdefault(field.setter_id, []).append(("setter_id", field))
        for method in self.methods:
            ids.setdefault(method.id, []).append(("id", method))
        for identifier in ids:
            if identifier is None:
                continue
            entries = ids[identifier]
            if len(entries) == 1:
                err_minor(
                    f"Entities share same identifier: {identifier} | "
                    + ", ".join(
                        [
                            f"'{entity.name}'({type(entity).__name__}"
                            f".{attr_name})"
                            for attr_name, entity in entries
                        ]
                    )
                    + " [feat_req_someip_56]"
                )
        return self


class SDTimings(DictInstances):
    """
    Configurations for SOME/IP-SD Timings.

    Parameters
    ----------

    profile_id : str
        A unique ID for the SOME/IP-SD timings profile.

    initial_delay_min : float
        Initial delay in milliseconds: This parameter keeps \
        back service offers to pack more entries together.
        Must be greater or equal to 0 and lower or equal to 10.
        Defaults to 10.

    initial_delay_max : float
        Initial delay in milliseconds: This parameter keeps \
        back service offers to pack more entries together.
        Must be greater or equal to 0 and lower or equal to 10.
        Defaults to 10.

    repetitions_base_delay : float
        Repetitions Base delay in milliseconds: This \
        parameter helps in fast startup and to make startup more \
        robust.Loss of the first offer results in this delay.
        Must be greater or equal to 0 and lower or equal to 30.
        Defaults to 30.

    repetitions_max : float
        Number of repetitions while doubling delay.
        Must be greater or equal to 0 and lower or equal to 3.
        Defaults to 3.

    request_response_delay_min : float
        Request response delay in milliseconds: This \
        parameter keeps back subscribes to pack more entries together.
        Must be greater or equal to 0 and lower or equal to 10.
        Defaults to 10.

    request_response_delay_max : float = Field(
        Request response delay in milliseconds: This \
        parameter keeps back subscribes to pack more entries together.",
        Must be greater or equal to 0 and lower or equal to 10.
        Defaults to 10.

    offer_cyclic_delay: float, optional
        Offer cyclic delay in milliseconds: This parameter \
        keeps system alive with cyclic offer.
        Must be greater or equal to 0 and lower or equal to 1000.
        Defaults to 1000.

    offer_ttl : float, optional
        Time to live in milliseconds: This parameter \
        determines how fast to age out state.
        Must be greater or equal to 0 and lower or equal to 3000.
        Defaults to 3000.

    find_ttl : float, optional
        Offer cyclic delay in milliseconds: This parameter \
        keeps system alive with cyclic offer.
        Must be greater or equal to 0 and lower or equal to 1000.
        Defaults to 1000.

    subscribe_ttl: float, optional
        Time to live in milliseconds: This parameter \
        determines how fast to age out state.
        Must be greater or equal to 0 and lower or equal to 3000.
        Defaults to 3.
    """

    INSTANCES: ClassVar[Dict[Any, "SDTimings"]] = {}
    profile_id: str = Field(
        description="A unique ID for the SOME/IP-SD timings profile"
    )

    initial_delay_min: float = Field(
        ge=0,
        le=10,
        description="Initial delay in milliseconds: This parameter keeps \
            back service offers to pack more entries together.",
        default=10,
    )

    initial_delay_max: float = Field(
        ge=0,
        le=10,
        description="Initial delay in milliseconds: This parameter keeps \
            back service offers to pack more entries together.",
        default=10,
    )

    repetitions_base_delay: float = Field(
        ge=0,
        le=30,
        description="Repetitions Base delay in milliseconds: This \
            parameter helps in fast startup and to make startup more \
                robust.Loss of the first offer results in this delay.",
        default=30,
    )
    repetitions_max: float = Field(
        ge=0,
        le=3,
        description="Number of repetitions while doubling delay",
        default=3,
    )

    request_response_delay_min: float = Field(
        ge=0,
        le=10,
        description="Request response delay in milliseconds: This \
            parameter keeps back subscribes to pack more entries together.",
        default=10.0,
    )

    request_response_delay_max: float = Field(
        ge=0,
        le=10,
        description="Request response delay in milliseconds: This \
            parameter keeps back subscribes to pack more entries together.",
        default=10,
    )

    offer_cyclic_delay: Optional[float] = Field(
        ge=0,
        le=1000,
        description="Offer cyclic delay in milliseconds: This parameter \
            keeps system alive with cyclic offer.",
        default=1000,
    )

    offer_ttl: Optional[float] = Field(
        ge=0,
        le=3000,
        description="Time to live in milliseconds: This parameter \
            determines how fast to age out state.",
        default=3,
    )

    find_ttl: Optional[float] = Field(
        ge=0,
        le=1000,
        description="Offer cyclic delay in milliseconds: This parameter \
            keeps system alive with cyclic offer.",
        default=1000,
    )

    subscribe_ttl: Optional[float] = Field(
        ge=0,
        le=3000,
        description="Time to live in milliseconds: This parameter \
            determines how fast to age out state.",
        default=3,
    )

    def get_dict_key(self):
        return self.profile_id


class SDConfig(FLYNCBaseModel):
    """allows to configure the SOME/IP Service-Discovery.
    Represent from the Chapter SD, the Endpoint and SD Endpoint.

    Parameters
    ----------

    ip_address : :class:`~IPvAnyAddress`
        IP on which the service discovery operates.

    port : int
        Port which the service discovery operates on.
        Must be greater than 0 and lower than 0xFFFF.

    sd_timings : List[ :class:`~SDTimings` ]
        Timing Configurations for SOME/IP-SD.
    """

    ip_address: Annotated[
        IPvAnyAddress, AfterValidator(common_validators.validate_ip_multicast)
    ] = Field(description="IP on which the service discovery operates")
    port: Annotated[int, Field(gt=0, lt=0xFFFF)] = Field(
        default=30490,
        description="port which the service discovery operates on",
    )
    sd_timings: List[SDTimings] = Field()

    @field_serializer("ip_address")
    def serialize_addresses(self, ip_address):
        if ip_address is not None:
            return str(ip_address).upper()


class SOMEIPConfig(FLYNCBaseModel):
    """
    Basic configuration of SOME/IP for a target system.

    Parameters
    ----------

    version: Literal[ "1.0" ]
        The version of this config.

    services: list[ :class:`~SOMEIPServiceInterface` ]
        List of SOME/IP Services.

    sd_config: :class:`~SDConfig`
        Configuration of the Service-Discovery.
    """

    version: Literal["1.0"] = Field(
        default="1.0", description="the version of this config"
    )
    services: Annotated[List[SOMEIPServiceInterface], External()] = Field(
        description="list of services"
    )
    sd_config: Annotated[
        SDConfig,
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ] = Field(description="configuration of the service discovery")
