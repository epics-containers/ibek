#!/bin/env dls-python

"""
Diamond Light Source specific script to convert IOC builder classes from
etc/builder.py into **ibek.support.yaml files
"""

import argparse
import inspect
import re
import sys

# import required modules
from pkg_resources import require

require("iocbuilder")
require("dls_dependency_tree")
require("ruamel.yaml")
require("mock")

UNDEFINED = "UNDEFINED"


from dls_dependency_tree import dependency_tree  # noqa: E402 isort:skip
from iocbuilder import ParseEtcArgs, configure, device  # noqa: E402 isort:skip
from iocbuilder.recordset import RecordsSubstitutionSet  # noqa: E402 isort:skip
from mock import Mock  # noqa: E402 isort:skip
from ruamel.yaml import YAML  # noqa: E402 isort:skip
from ruamel.yaml.comments import CommentedMap as ordereddict  # noqa: E402 isort:skip


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
        self.builder_module, self.builder_classes = self._configure()

    def _configure(self):
        """
        Setup the IOC builder environment and parse the support module
        """

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
        module = modules[-1]
        classes = self._valid_classes(module.ClassesList)

        return module, classes

    def _valid_classes(self, class_list):
        """
        Extract the list of builder classes that are relevant for conversion
        to ibek YAML.
        """
        classes = {}
        for builder_class in class_list:
            name = class_name_re.findall(str(builder_class))[0]
            if (
                hasattr(builder_class, "ArgInfo")
                and not name.startswith("_")
                and not name.endswith("Template")
            ):
                classes[name] = builder_class

        return classes

    def _make_builder_object(self, name, builder_class):
        """
        Make an instance of a builder class by generating a best guess
        set of arguments to the builder class __init__ method.

        Returns:
            A tuple containing the generated arguments as an ibek.support.yaml
            definition object graph, plus the instantiated builder object.
        """
        this_def = ordereddict()
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
            args.append(self._make_arg(arg_name, builder_class, UNDEFINED))

        for index, arg_name in enumerate(builder_class.ArgInfo.default_names):
            if builder_class.ArgInfo.default_values[index] is not None:
                default = builder_class.ArgInfo.default_values[index]
            else:
                default = UNDEFINED
            args.append(self._make_arg(arg_name, builder_class, default))

        return this_def, self._instantiate_builder_objects(args, builder_class)

    def _make_arg(self, arg_name, builder_class, default=None):
        """
        Generate a ibek YAML argument from a builder ArgInfo
        """
        arg_info = builder_class.ArgInfo.descriptions[arg_name]

        matches = description_re.findall(arg_info.desc)
        description = (
            matches[0] if len(matches) > 0 else "TODO ------ NO DESCRIPTION -------"
        )

        # create a YAML type for the argument
        if arg_name == getattr(builder_class, "UniqueName", "name"):
            typ = "id"
        elif arg_info.typ == str:
            typ = "str"
        elif arg_info.typ == int:
            typ = "int"
            if default == UNDEFINED:
                default = 0
        elif arg_info.typ == bool:
            typ = "bool"
            if default == UNDEFINED:
                default = False
        elif arg_info.typ == float:
            typ = "float"
            if default == UNDEFINED:
                default = 0
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

    def _instantiate_builder_objects(self, args, builder_class):
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
            elif arg["type"] == "str":
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

        # instantiate a builder object using our mock arguments
        return builder_class(**args_dict)

    def _extract_substitutions(self):
        """
        Extract all of the database substitutions from the builder class
        and populate the ibek YAML database object graph.

        This function removes the substitutions from all_substitutions
        so must be called inside a loop that iterates over each of the
        builder classes in a module.

        Returns:
            A database object graph for the ibek YAML file, the root is an
            array of databases, since each builder class can instantiate
            multiple database templates.
        """
        all_substitutions = RecordsSubstitutionSet._SubstitutionSet__Substitutions

        databases = []

        # extract the set of templates with substitutions for the new builder object
        while all_substitutions:
            database = ordereddict()
            databases.append(database)

            template, substitutions = all_substitutions.popitem()
            first_substitution = substitutions[1][0]

            database["file"] = template

            database["args"] = {a[0]: None for a in first_substitution.args.items()}

        return databases

    def _make_init_script(self, builder_object, func_name, typ, script):
        """
        Find the source code for a builder class method and create an object
        graph representing as script entries in the ibek YAML file.
        """
        func = getattr(builder_object, func_name, None)
        if func:
            script_item = ordereddict()
            script_item["type"] = typ
            func_text = inspect.getsource(func)
            script_item["value"] = func_text
            script.append(script_item)

    def _call_initialise(self, builder_object):
        """
        Extract the code from the builder class Initialise() method
        to insert into the ibek YAML script object graph.

        Also extract the code from the builder class PostIocInitialise()
        and InitialiseOnce() methods.

        """
        # TODO - get the Initialise source code if Initialise() fails
        script = []
        self._make_init_script(builder_object, "InitialiseOnce", "once", script)
        self._make_init_script(builder_object, "Initialise", "text", script)
        self._make_init_script(
            builder_object, "PostIocInitialise", "post_ioc_init", script
        )

        # TODO - disabled for schema checking DATABASE section changes
        # TODO delete this line
        script = []

        return script

    def dump_subst_file(self):
        """
        Print out the database substitutions for all the builder classes
        in the support module
        """
        for name, builder_class in self.builder_classes.items():
            self._make_builder_object(name, builder_class)

        RecordsSubstitutionSet.Print()

    def make_yaml_tree(self):
        """
        Main entry point: generate the ibek YAML object graph from
        builder classes.
        """
        builder_objects = []
        self.yaml_tree["module"] = self.builder_module.Name()

        yaml_defs = self.yaml_tree["defs"] = []

        for name, builder_class in self.builder_classes.items():
            one_def, builder_object = self._make_builder_object(name, builder_class)
            yaml_defs.append(one_def)
            builder_objects.append(builder_object)
            one_def["databases"] = self._extract_substitutions()
            one_def["script"] = self._call_initialise(builder_object)

    def write_yaml_tree(self, filename):
        """
        Convert the yaml object graph into a YAML file
        """

        def add_blank_lines(yaml):
            # add blank lines between major fields
            for field in ["- type:", "- file:", "- name:", "databases:"]:
                yaml = re.sub(r"(\s*%s)" % field, "\n\\g<1>", yaml)

            # cheesy way to make multiline Init Function strings readable in YAML
            # because ruamel quotes them and escapes newlines
            yaml = re.sub(r"(\\ *\n *\\?)", "", yaml, flags=re.MULTILINE)
            yaml = re.sub(r"(\\n)", "\n      # ", yaml, flags=re.MULTILINE)
            yaml = re.sub(r"\\\"", '"', yaml, flags=re.MULTILINE)
            yaml = re.sub(
                r"value: \"",
                "value:\n      # "
                + "TODO --- CONVERT THE FOLLOWING TO AN IBEK FUNCTION"
                + "\n      # ",
                yaml,
                flags=re.MULTILINE,
            )
            yaml = re.sub(r"      # \"", "", yaml, flags=re.MULTILINE)
            return yaml

        yaml = YAML()

        yaml.default_flow_style = False

        # add a placeholder for the schema using a relative path
        # this is more useful than the URL during support yaml development
        self.yaml_tree.yaml_add_eol_comment(
            "yaml-language-server: $schema=../_global/ibek.defs.schema.json"
        )

        print("\nWriting YAML output to %s ..." % filename)
        with open(filename, "wb") as f:
            yaml.dump(self.yaml_tree, f, transform=add_blank_lines)


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
        # MockArg to override on the command line when an error occurs without
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

    def __str__(self):
        return self.repr

    ############################################################################
    # BELOW - we override methods that are called by builder.py on the builder
    # object's (Mock) arguments.
    ############################################################################

    def __add__(self, other):
        try:
            return self._mock_wraps + other
        except TypeError:
            return "%s + %s" % (self._mock_wraps, other)

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
    """
    Parse the command line arguments
    """
    parser = argparse.ArgumentParser(
        prog="builder2ibek",
        description="A tool for converting builder.py classes to ibek support YAML",
    )
    parser.add_argument("path", help="path to the support module")
    parser.add_argument(
        "yaml",
        help="path to the YAML file to be generated",
        default=None,
        nargs="?",
    )
    parser.add_argument(
        "-o",
        "--overrides",
        action="append",
        help=(
            "override a MockArg argument value in the builder class"
            " using the form 'arg_num:value'"
        ),
    )
    args = parser.parse_args()

    arg_overrides = {}
    for o in args.overrides or []:
        m = arg_values_re.match(o)
        assert len(m.groups()) == 2, "Invalid argument format %s" % o
        value = m.group(2)
        if re.match(is_int_re, value):
            value = int(value)
        elif re.match(is_float_re, value):
            value = float(value)
        arg_overrides[m.group(1)] = value

    yaml_file = args.yaml or "ibek.support.yaml"

    return args.path, yaml_file, arg_overrides


if __name__ == "__main__":
    support_module_path, filename, arg_value_overrides = parse_args()
    builder2support = Builder2Support(support_module_path, arg_value_overrides)
    # builder2support.dump_subst_file()
    builder2support.make_yaml_tree()
    builder2support.write_yaml_tree(filename)
