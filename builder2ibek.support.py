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
        description = (
            matches[0] if len(matches) > 0 else "TODO ------ NO DESCRIPTION -------"
        )

        # create a YAML type for the argument
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

        # Special case for the CS ArgInfo which is failing to show as int
        # in the pmac builder class CS (maybe because class==ArgInfo name ?)
        if arg_name == "CS":
            typ = "int"

        # Create the object representing a YAML argument
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

            # pick a sensible value for the argument to builder object's __init__
            if hasattr(desc, "labels"):
                value = desc.labels[0]
            elif hasattr(desc, "ident"):
                # wrapping None means that this behaves as a Mock
                value = None
            elif "default" in arg:
                value = arg["default"]
            elif arg["type"] == "int":
                value = 1
            elif arg["type"] == "float":
                value = 1.0
            elif arg["type"] == "bool":
                value = False
            elif arg["type"] == "string":
                value = arg_name + "_STRING"
            elif arg["type"] == "id":
                value = arg_name + "_ID"
            else:
                assert 0, "Unknown type %s" % arg["type"]

            magic_arg = MockArg(wraps=value, name=arg_name)
            if magic_arg.overridden:
                print("OVERRIDDEN: %s, %s" % (arg_name, magic_arg._mock_wraps))
                args_dict[arg_name] = magic_arg._mock_wraps
            else:
                args_dict[arg_name] = magic_arg

        # instantiate the builder object with our mock arguments
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
    __init__ method.

    We use the mock object "name" to store the name of the argument and
    the mock object "wraps" to store a value for the argument.
    """

    ARG_NUM = 0

    def __init__(self, wraps=None, name="", *args, **kwargs):
        MockArg.ARG_NUM += 1

        # override the wrapped value if a command line override was specified
        new_wrap = Builder2Support.arg_value_overrides.get(str(MockArg.ARG_NUM), wraps)

        super(MockArg, self).__init__(wraps=new_wrap, name=name, *args, **kwargs)

        # this print is required to assist users in deciding which numbered
        # MockArk to override on the command line when an error occurs without
        # overrides
        print(
            "MockArg: %s, %s, %s, %s"
            % (MockArg.ARG_NUM, name, new_wrap, type(new_wrap).__name__)
        )

        self.arg_num = MockArg.ARG_NUM
        self.overridden = new_wrap != wraps
        self.repr = "MockArg(%s, %s, %s)" % (self.arg_num, name, new_wrap)

    def __repr__(self):
        return self.repr

    ################################################################################
    # BELOW - we override methods that are called by builder.py on the builder #####
    # object's arguments.                                                      #####

    def __add__(self, other):
        return self._mock_wraps + other

    def __int__(self):
        try:
            return int(self._mock_wraps)
        except ValueError:
            pass

        try:
            return int(bool(self._mock_wraps))
        except ValueError:
            pass

        return 1

    def __iter__(self):
        return iter(self._mock_wraps)

    def __setitem__(self, _key, _value):
        pass

    def __getitem__(self, key):
        return "%s[%s]" % (self, key)

    def __lt__(self, other):
        return self._mock_wraps < other

    def __gt__(self, other):
        return self._mock_wraps > other

    def __eq__(self, other):
        return self._mock_wraps == other


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
