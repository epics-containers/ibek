#!/bin/env dls-python
import re
import sys

# import required modules
from pkg_resources import require

require("iocbuilder")
require("dls_dependency_tree")
require("ruamel.yaml")
require("mock")


from dls_dependency_tree import dependency_tree  # isort:skip
from iocbuilder import ParseEtcArgs, configure, device  # isort:skip
from iocbuilder.recordset import RecordsSubstitutionSet  # isort:skip
from mock import MagicMock  # isort:skip
from ruamel.yaml import YAML  # isort:skip
from ruamel.yaml.comments import CommentedMap as ordereddict  # isort:skip


class_name_re = re.compile(r"class '.*\.(.*)'")
description_re = re.compile(r"(.*)\n<type")
arg_values_re = re.compile(r"(\d*):(.*)")

# use dls-python -i builder2ibek.support.py PATH_TO_SUPPORT_MODULE and then
# use global MODULE to interactively inspect the builder Classes
MODULE = None
ARG_VALUES = {}


class MockArg(MagicMock):
    """
    A mock object that can be used to represent an argument to a builder class
    """

    ARG_NUM = 0

    def __init__(self, name="", path="", *args, **kwargs):
        super(MockArg, self).__init__(*args, **kwargs)

        MockArg.ARG_NUM += 1

        self.path = path  # tracks the object path to get to this mock object
        self.arg_num = MockArg.ARG_NUM
        self.arg_name = name
        self.arg_render = RenderAsArg(name)
        self.arg_value = ARG_VALUES.get(str(self.arg_num), None)

        if self.arg_value is not None:
            self.__str__ = lambda self: self.arg_value

        print("MockArg: %s, %s, %s" % (self.arg_num, name, self.arg_value))

    def __repr__(self):
        return self.arg_value or "MockArg(%s, %s)" % (self.arg_num, self.arg_name)

    # def __getattr__(self, name):
    #     if name in ("_mock_methods", "_mock_unsafe"):
    #         return super(MockArg, self).__getattr__(name)

    #     print("MockArg %s, attr: %s, value: %s" % (self.arg_num, name, self.arg_value))
    #     return MockArg(path=self.path + "." + name)


class RenderAsArg:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        return RenderAsArg(self.name + "." + attr)

    def __str__(self):
        return "{{ " + self.name + " }}"


def arg_details(args, arg_name, builder_class, default=None):
    arg = builder_class.ArgInfo.descriptions[arg_name]

    matches = description_re.findall(arg.desc)
    description = matches[0] if len(matches) > 0 else "NO DESCRIPTION"

    if arg_name == getattr(builder_class, "UniqueName", "name"):
        typ = "id"
    elif arg.typ == str:
        typ = "string"
    elif arg.typ == int:
        typ = "int"
    elif arg.typ == bool:
        typ = "bool"
    elif arg.typ == float:
        typ = "float"
    elif "iocbuilder.modules" in str(arg.typ):
        typ = "object"
    else:
        typ = "UNKNOWN"

    arg = ordereddict()
    arg["type"], arg["name"], arg["description"] = typ, arg_name, description
    if default is not None:
        arg["default"] = default

    args.append(arg)


def instantiate_builder_object(args, builder_class):
    args_dict = {}

    # Mock up a set of args with which to instantiate a builder object
    for arg in args:
        arg_name = arg["name"]
        # if the arg is a Choice then use the first Choice as the value
        desc = builder_class.ArgInfo.descriptions[arg_name]
        if hasattr(desc, "labels"):
            args_dict[arg_name] = desc.labels[0]
        # Otherwise use an identifiable Mock object
        else:
            magic_arg = MockArg(arg_name)
            args_dict[arg_name] = magic_arg.arg_value or magic_arg

    builder_object = builder_class(**args_dict)

    all_substitutions = RecordsSubstitutionSet._SubstitutionSet__Substitutions

    # extract the set of templates with substitutions for the new builder object
    while all_substitutions:
        template, substitutions = all_substitutions.popitem()
        first_substitution = substitutions[1][0]
        print("SUBSTITUTION: %s, %s" % (template, first_substitution))
        first_substitution._PrintSubstitution()

    # try:
    #     builder_object.Initialise()
    # except (AttributeError, ValueError):
    #     print("FAILED to initialise builder object for %s" % builder_class)


def main():
    if len(sys.argv) < 2:
        print("Usage: %s <path to support module>" % sys.argv[0])
        sys.exit(1)

    for i in range(2, len(sys.argv)):
        m = arg_values_re.match(sys.argv[i])
        assert len(m.groups()) == 2, "Invalid argument format %s" % sys.argv[i]
        ARG_VALUES[m.group(1)] = m.group(2)

    global MODULE
    # Here we will build up a tree of objects representing the YAML structure
    object_tree = ordereddict()

    options, args = ParseEtcArgs(architecture="linux-x86_64")

    # ParseAndConfigure expects to be in etc/makeIocs and looks for
    # ../../configure/RELEASE relative to that
    options.build_root = sys.argv[1] + "/etc/makeIocs"

    modules = configure.ParseAndConfigure(options, dependency_tree)

    # the last module is the root module that we are interested in
    MODULE = modules[-1]

    object_tree["module"] = MODULE.Name()

    defs = object_tree["defs"] = []

    for builder_class in MODULE.ClassesList:
        name = class_name_re.findall(str(builder_class))[0]
        if (
            hasattr(builder_class, "ArgInfo")
            and not name.startswith("_")
            and not name.endswith("Template")
        ):
            this_def = ordereddict()
            defs.append(this_def)
            this_def["name"] = name
            if builder_class.__doc__:
                desc = builder_class.__doc__.strip()
            else:
                desc = "TODO ------ NO DESCRIPTION -------"
            this_def["description"] = desc
            args = this_def["args"] = []

            for arg_name in builder_class.ArgInfo.required_names:
                arg_details(args, arg_name, builder_class)

            for arg_name in builder_class.ArgInfo.optional_names:
                arg_details(args, arg_name, builder_class, "UNDEFINED")

            for index, arg_name in enumerate(builder_class.ArgInfo.default_names):
                arg_details(
                    args,
                    arg_name,
                    builder_class,
                    builder_class.ArgInfo.default_values[index],
                )

            instantiate_builder_object(args, builder_class)

    yaml = YAML()
    yaml.default_flow_style = False

    # yaml.dump(object_tree, sys.stdout)

    # print(RecordsSubstitutionSet._SubstitutionSet__Substitutions)


if __name__ == "__main__":
    # TODO pmac driver blows up on device.__CheckResources with
    # missing vx works library but this does not help ASK TOM
    device._ResourceExclusions["vxWorks-ppc604_long"] = ["library", "object"]

    main()
