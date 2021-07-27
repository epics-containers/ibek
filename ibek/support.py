import builtins
from builtins import getattr
from dataclasses import dataclass, make_dataclass
from typing import Any, Mapping, Optional, Sequence, Type, TypeVar, Union

from apischema import Undefined, UndefinedType, deserialize, deserializer, schema
from apischema.conversions import Conversion, identity
from jinja2 import Template
from typing_extensions import Annotated as A
from typing_extensions import Literal

T = TypeVar("T")


def desc(description: str):
    return schema(description=description)


@dataclass
class Arg:
    name: A[str, desc("Name of the argument that the IOC instance should pass")]
    description: A[str, desc("Description of what the argument will be used for")]

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

    def format_script(self, **kwargs: Any) -> str:
        all_lines = "\n".join(self.script)
        template = Template(all_lines)
        result = template.render(**kwargs)
        return result

    def get_entity_instances(self, EntityInstance, namespace):
        name = self.name
        fields = []
        for arg in self.args:
            if arg.description:
                fields += [
                    (arg.name, A[getattr(builtins, arg.type), desc(arg.description)])
                ]
            else:
                fields += [(arg.name, getattr(builtins, arg.type))]
        namespace[name] = make_dataclass(name, fields, bases=(EntityInstance,))


@dataclass
class Support:
    """Lists the entities a support module can build"""

    module: A[str, desc("Support module name, normally the repo name")]
    entities: A[
        Sequence[Entity], desc("The entities an IOC can create using this module")
    ]

    def get_module(self):
        """
        define an EntityInstance base class that is created every time this method
        is called if this is called in the scope of the Support class or the top
        level of the module subclasses can persist with each call of
        self.get_module causing conflicts
        """

        @dataclass
        class ModuleSuperclass:
            @classmethod
            def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
                return deserialize(cls, d)

        @dataclass
        class EntityInstance:
            def __init_subclass__(cls) -> None:
                deserializer(Conversion(identity, source=cls, target=EntityInstance))

        namespace = {}
        namespace["entityinstance"] = EntityInstance

        for entity in self.entities:
            entity.get_entity_instances(namespace["entityinstance"], namespace)

        namespace[self.module] = make_dataclass(
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
        print(namespace["entityinstance"].__subclasses__())
        return namespace[self.module]

    @classmethod
    def deserialize(cls: Type[T], d: Mapping[str, Any]) -> T:
        return deserialize(cls, d)
