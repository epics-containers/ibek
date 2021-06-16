import json
from dataclasses import field, make_dataclass
from typing import Literal, Sequence

from apischema.json_schema import deserialization_schema
from ruamel.yaml import YAML

from ibek.support import Entity, Support

yaml = YAML()

with open("/Users/richardparke/Documents/K8-IOCs/ibek/tests/pmac.ibek.yaml", "r") as f:
    ioc_class = Support.deserialize(yaml.load(f))


def make_module(ioc_class):
    """ take a support instance as argument and return a dataclass defining a support module"""
    return ioc_class.get_support_dataclass()


def make_entities(ioc_class):
    """Take a list an instance of Support and return a list of dataclasses """


entity = ioc_class.entities[0]
entity_dataclass_name = entity.name
entity_args = entity.args
args = []
for arg in entity_args:
    args += [(arg.name, arg.type)]
args += [("script", Sequence[str], field(default=entity.script))]

entity_dataclass = make_dataclass(entity.name, fields=args)

