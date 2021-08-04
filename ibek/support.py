import builtins
from builtins import getattr
from dataclasses import Field, dataclass, field, make_dataclass
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from apischema import Undefined, UndefinedType, deserialize, deserializer, schema
from apischema.conversions import Conversion, identity
from typing_extensions import Annotated as A
from typing_extensions import Literal


def desc(description: str):
    return schema(description=description)


T = TypeVar("T")

"""
The Support Class represents a deserialized <MODULE_NAME>.ibek.yaml file.
It is a hierarchy of dataclasses. This module also defines all of the
dataclasses that can appear as children of Support in the object graph.

TODO: There are a couple of problems with deserialize and defaults. These
are worked around as follows. I need to verify that this is the best
approach to dealing with this.

- str default "" == no default
    - using " " for now (I'm not sure I'm happy with this)
- int default 0 or null == no default
    - using "0" and added str type to IntArg
- float values in json have a trailing 'f' and this comes back as str on deserialize
    - added str type to FloatArg
    - added __post_init__ to FloatArg to strip the 'f'
"""


@dataclass
class Arg:
    name: A[str, desc("Name of the argument that the IOC instance should pass")]
    description: A[str, desc("Description of what the argument will be used for")]
    type: str
    default: Any

    # https://wyfo.github.io/apischema/examples/subclasses_union/
    def __init_subclass__(cls):
        # Deserializers stack directly as a Union
        deserializer(Conversion(identity, source=cls, target=Arg))


Default = A[
    Union[Optional[T], UndefinedType],
    desc("If given, and instance doesn't supply argument, what value should be used"),
]


@dataclass
class StrArg(Arg):
    """An argument with a str value"""

    type: Literal["str"] = "str"
    default: Default[str] = Undefined
    is_id: A[
        bool, desc("If true, instances may refer to this instance by this arg")
    ] = False


@dataclass
class IntArg(Arg):
    """An argument with an int value"""

    type: Literal["int"] = "int"
    default: Default[Union[int, str]] = Undefined


@dataclass
class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    # FloatArg defaults always look like str of the form "0.5f"
    default: Default[Union[float, str]] = Undefined

    # Strip the trailing f so that the string resolves to a float for EPICS
    def __post_init__(self):
        if isinstance(self.default, str):
            if self.default.endswith("f"):
                self.default = self.default[:-1]


@dataclass
class ObjectArg(Arg):
    """A reference to another entity defined in this IOC"""

    type: A[str, desc("Entity class, <module>.<entity_name>")]
    default: Default[str] = Undefined


@dataclass
class Database:
    """A database file that should be loaded by the startup script and its args"""

    file: A[str, desc("Filename of the database template in <module_root>/db")]
    include_args: A[
        Sequence[str], desc("List of args to pass through to database")
    ] = ()
    define_args: A[str, desc("Arg string list to be generated as Jinja template")] = ""


@dataclass
class Entity:
    """A single entity that an IOC can instantiate"""

    name: A[str, desc("Publish Entity as type <module>.<name> for IOC instances")]
    args: A[Sequence[Arg], desc("The arguments IOC instance should supply")] = ()
    databases: A[Sequence[Database], desc("Databases to instantiate")] = ()
    script: A[
        Sequence[str], desc("Startup script snippet defined as Jinja template")
    ] = ()

    def get_entity_instances(
        self,
        baseclass: Any,
        namespace: Dict[str, Any],
        module_name: str,
        entity: "Entity",
    ):
        """
        We can get a set of Entities by deserializing an ibek support module
        YAML file. This  function creates an EntityInstance class from
        an Entity. See :ref:`entities`
        """
        # we need to qualify the name with the module so as to avoid cross
        # module name clashes
        name = f"{module_name}.{self.name}"

        if name in namespace:
            return

        # put the literal name in as 'type' for this Entity this gives us
        # a unique key for each of the entity types we may instantiate
        fields: List[Any] = [(str("type"), Literal[name])]

        # add in each of the arguments

        for arg in self.args:
            this_field: Union[str, Tuple[str, type], Tuple[str, type, Field[Any]]] = ""

            if arg.description:
                arg_type = getattr(builtins, arg.type)
                this_field = (
                    arg.name,
                    A[arg_type, desc(arg.description)],
                )
            else:
                this_field = (arg.name, getattr(builtins, arg.type))
            if arg.default:
                default: Field[Any] = field(default=arg.default)
                this_field += (default,)

            fields.append(this_field)

        # make the EntityInstance derived dataclass for this EntityClass
        entity_instance_cls: EntityInstance = cast(
            EntityInstance, make_dataclass(name, fields, bases=(baseclass,))
        )

        # add a reference to the entity class for this entity instance class
        # (oh boy, that sounds confusing: see `explanations/entities`)
        setattr(entity_instance_cls, "entity", entity)

        namespace[name] = entity_instance_cls


@dataclass
class ModuleSuperclass:
    """
    A base class for all generated module classes. Provides the deserialize
    entry point only
    """

    ioc_name: str

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)


@dataclass
class EntityInstance:
    """
    A baseclass for all generated Entity classes. Provides the deserialize
    entry point only
    """

    entity: ClassVar[Entity]

    def __init_subclass__(cls) -> None:
        deserializer(Conversion(identity, source=cls, target=EntityInstance))


@dataclass
class Support:
    """Lists the entities a support module can build"""

    module: A[str, desc("Support module name, normally the repo name")]
    entities: A[
        Sequence[Entity], desc("The entities an IOC can create using this module")
    ]

    # a global namespace for holding all generated classes
    namespace: ClassVar[Dict[str, Any]] = {}

    def get_module(self) -> ModuleSuperclass:
        """
        Generate an in memory module class with a set of EntityInstance classes.

        Instances of this module are used to represent individual instances of
        IOCs.
        """

        self.namespace["entityinstance"] = EntityInstance

        for entity in self.entities:
            entity.get_entity_instances(
                self.namespace["entityinstance"], self.namespace, self.module, entity,
            )

        self.namespace[self.module] = make_dataclass(
            self.module,
            [
                ("ioc_name", A[str, desc("Name of IOC")]),
                (
                    "instances",
                    A[
                        Sequence[EntityInstance],
                        desc("List of entity instances of the IOCs"),
                    ],
                ),
            ],
            bases=(ModuleSuperclass,),
        )
        print(self.namespace["entityinstance"].__subclasses__())
        return self.namespace[self.module]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
