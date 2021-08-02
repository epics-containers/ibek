import builtins
from builtins import getattr
from dataclasses import Field, dataclass, field, make_dataclass
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
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
    default: Default[int] = Undefined


@dataclass
class FloatArg(Arg):
    """An argument with a float value"""

    type: Literal["float"] = "float"
    default: Default[float] = Undefined


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

        # put the literal name in as 'type' for this Entity this gives us
        # a unique key for each of the entity types we may instantiate
        fields: Iterable[
            Union[Tuple[str], Tuple[str, type], Tuple[str, type, Field[Any]]]
        ] = [(str("type"), Literal[name])]

        # add in each of the arguments

        for arg in self.args:
            this_field: Union[
                Tuple[str], Tuple[str, type], Tuple[str, type, Field[Any]]
            ] = (arg.name,)

            if arg.description:
                this_field += (A[getattr(builtins, arg.type), desc(arg.description)],)
            else:
                this_field += (getattr(builtins, arg.type),)
            if arg.default:
                this_field += (field(default=arg.default),)
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
class EntityInstance:
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

    def get_module(self):
        """
        define a new EntityInstance base class every time this method is called.

        If this is created in the scope of the Support class or the top
        level of the module subclasses can persist with each call of
        self.get_module causing conflicts

        # TODO is this needed if we fully qualify entity instance types
        e.g. pmac.PmacAsynIPPort? could we therefore define EntityInstance
        globally?

        # TODO - moving entity instance out for a moment ...
        # TODO - also made namespace a CLASS variable of Support - meaning there
        # is only one and all generated classes must have unique names
        """

        @dataclass
        class ModuleSuperclass:
            @classmethod
            def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
                return deserialize(cls, d)

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
