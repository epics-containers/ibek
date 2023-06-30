#!/bin/env dls-python
"""
Diamond Light Source specific script to convert IOC builder classes into
ibek.support.yaml
"""

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
from mock import MagicMock, Mock  # isort:skip
from ruamel.yaml import YAML  # isort:skip
from ruamel.yaml.comments import CommentedMap as ordereddict  # isort:skip


class_name_re = re.compile(r"class '.*\.(.*)'")
description_re = re.compile(r"(.*)\n<type")
arg_values_re = re.compile(r"(\d*):(.*)")
is_int_re = re.compile(r"[-+]?\d+$")
is_float_re = re.compile(r"[-+]?\d*\.\d+([eE][-+]?\d+)?$")


class Builder2Support:
    arg_value_overrides = {}

    def __init__(self, support_module_path, arg_value_overrides):
        self.support_module_path = support_module_path
        Builder2Support.arg_value_overrides = arg_value_overrides
        self.yaml_tree = ordereddict()
        self.builder_module = self._configure()

    def _configure(self):
        # Dont bother with checking for libs and object files
        device._ResourceExclusions["linux-x86_64"] = ["library", "object"]

        # ParseAndConfigure expects to be in etc/makeIocs and looks for
        # ../../configure/RELEASE relative to that
        options, _args = ParseEtcArgs(architecture="linux-x86_64")
        options.build_root = sys.argv[1] + "/etc/makeIocs"

        # this will find and load into global namespace all support modules
        # builder classes defined in **/etc/builder.py
        modules = configure.ParseAndConfigure(options, dependency_tree)

        # the last support module is the root module that we are interested in
        return modules[-1]

    def make_yaml_tree(self):
        self.yaml_tree["module"] = self.builder_module.Name()

        defs = self.yaml_tree["defs"] = []

        for builder_class in self.builder_module.ClassesList:
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
                    args.append(self._make_arg(arg_name, builder_class))

                for arg_name in builder_class.ArgInfo.optional_names:
                    args.append(self._make_arg(arg_name, builder_class, "UNDEFINED"))

                for index, arg_name in enumerate(builder_class.ArgInfo.default_names):
                    args.append(
                        self._make_arg(
                            arg_name,
                            builder_class,
                            builder_class.ArgInfo.default_values[index],
                        )
                    )

                self.instantiate_builder_object(args, builder_class)

    def _make_arg(self, arg_name, builder_class, default=None):
        arg_info = builder_class.ArgInfo.descriptions[arg_name]

        matches = description_re.findall(arg_info.desc)
        description = matches[0] if len(matches) > 0 else "NO DESCRIPTION"

        if arg_name == getattr(builder_class, "UniqueName", "name"):
            typ = "id"
        elif arg_info.typ == str:
            typ = "string"
        elif arg_info.typ == int:
            typ = "int"
        elif arg_info.typ == bool:
            typ = "bool"
        elif arg_info.typ == float:
            typ = "float"
        elif "iocbuilder.modules" in str(arg_info.typ):
            typ = "object"
        else:
            typ = "UNKNOWN"

        arg = ordereddict()
        arg["type"], arg["name"], arg["description"] = typ, arg_name, description
        if default is not None:
            arg["default"] = default

        return arg

    # print(RecordsSubstitutionSet._SubstitutionSet__Substitutions)
    def instantiate_builder_object(self, args, builder_class):
        args_dict = {}

        # Mock up a set of args with which to instantiate a builder object
        for arg in args:
            arg_name = arg["name"]
            # if the arg is a Choice then use the first Choice as the value
            desc = builder_class.ArgInfo.descriptions[arg_name]

            if hasattr(desc, "labels"):
                value = desc.labels[0]
            elif "default" in arg:
                value = arg["default"]
            elif arg["type"] == "int":
                value = 1
            elif arg["type"] == "float":
                value = 1.0
            elif arg["type"] == "bool":
                value = False
            elif arg["type"] == "string":
                value = "UNDEFINED"
            else:
                value = None

            magic_arg = MockArg(wraps=value, name=arg_name)
            args_dict[arg_name] = magic_arg

            # if hasattr(desc, "labels"):
            #     args_dict[arg_name] = desc.labels[0]
            # # Otherwise use an identifiable Mock object
            # else:
            #     magic_arg = MockArg(arg_name, arg)
            #     args_dict[arg_name] = magic_arg.arg_value or magic_arg

        builder_object = builder_class(**args_dict)

        all_substitutions = RecordsSubstitutionSet._SubstitutionSet__Substitutions

        # extract the set of templates with substitutions for the new builder object
        while all_substitutions:
            template, substitutions = all_substitutions.popitem()
            first_substitution = substitutions[1][0]
            print("SUBSTITUTION: %s, %s" % (template, first_substitution))
            first_substitution._PrintSubstitution()

        # TODO - get the Initialise source code instead of calling it
        if False:
            try:
                builder_object.Initialise()
            except (AttributeError, ValueError):
                print("FAILED to initialise builder object for %s" % builder_class)

    def write_yaml_tree(self):
        yaml = YAML()
        yaml.default_flow_style = False

        yaml.dump(self.yaml_tree, sys.stdout)


class MockArg(Mock):
    """
    A mock object that can be used to represent an argument to a builder class
    """

    ARG_NUM = 0

    def __init__(self, wraps=None, name="", *args, **kwargs):
        MockArg.ARG_NUM += 1

        wraps = Builder2Support.arg_value_overrides.get(str(MockArg.ARG_NUM), wraps)

        super(MockArg, self).__init__(wraps=wraps, name=name, *args, **kwargs)
        print("MockArg: %s, %s, %s" % (MockArg.ARG_NUM, name, wraps))

        self.arg_num = MockArg.ARG_NUM

    def __add__(self, other):
        result = "%s + %s" % (str(self), other)
        return result

    def __int__(self):
        if self._mock_wraps is None:
            return 1
        else:
            return int(self._mock_wraps)


def parse_args():
    if len(sys.argv) < 2:
        print("Usage: %s <path to support module>" % sys.argv[0])
        sys.exit(1)

    module_path = sys.argv[1]

    arg_overrides = {}
    for i in range(2, len(sys.argv)):
        m = arg_values_re.match(sys.argv[i])
        assert len(m.groups()) == 2, "Invalid argument format %s" % sys.argv[i]
        value = m.group(2)
        if re.match(is_int_re, value):
            print("INT")
            value = int(value)
        elif re.match(is_float_re, value):
            value = float(value)
        arg_overrides[m.group(1)] = value

    return module_path, arg_overrides


if __name__ == "__main__":
    support_module_path, arg_value_overrides = parse_args()
    builder2support = Builder2Support(support_module_path, arg_value_overrides)
    builder2support.make_yaml_tree()
    builder2support.write_yaml_tree()
