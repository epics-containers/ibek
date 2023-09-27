#!/bin/env dls-python

"""
Diamond Light Source specific script to convert IOC builder classes from
etc/builder.py into **ibek.support.yaml files.

TO work on this project it is very helpful to be able to run in the vscode
debugger. HOW TO DO THIS:

- Downgrade the Python Extension in vscode to 2021.9.1246542782
- Use the debug launcher called builder2ibek
- change the filename (and other args)that is passed in the debug launcher
  - by editing .vscode/launch.json
"""

import argparse
import inspect
import os
import re
import sys

# import required modules
from pkg_resources import require

require("iocbuilder")
require("dls_dependency_tree")
require("ruamel.yaml")
require("mock")
from ruamel.yaml.scalarstring import PreservedScalarString

from dls_dependency_tree import dependency_tree  # noqa: E402 isort:skip
from iocbuilder import ParseEtcArgs, configure, device  # noqa: E402 isort:skip
from iocbuilder.recordset import RecordsSubstitutionSet  # noqa: E402 isort:skip
from mock import MagicMock  # noqa: E402 isort:skip
from ruamel.yaml import YAML  # noqa: E402 isort:skip
from ruamel.yaml.comments import CommentedMap as ordereddict  # noqa: E402 isort:skip


# regular expressions for extracting information from builder classes
# regular expressions for extracting information from builder classes
class_name_re = re.compile(r"(?:type|class) '(.*)'")
arg_values_re = re.compile(r"(\d*):(.*)")
is_int_re = re.compile(r"[-+]?\d+$")
is_float_re = re.compile(r"[-+]?\d*\.\d+([eE][-+]?\d+)?$")

# this monster regex finds strings between '' or "" (oh boy!)
extract_printed_strings_re = re.compile(r"([\"'])((?:\\\1|(?:(?!\1))[\S\s])*)(?:\1)")
# match substitution fields in print statements e.g. %(name)s or {name:s} etc
macros_re = re.compile(r"(?:(?:{)|(?:%\())([^:\)}]*)(?:(?:(?::.)?})|(?:\).))")
# replace matched fields with jinja2 style macros
macro_to_jinja_re = r"{{\1}}"

MISSING = "TODO - MISSING ARGS: "


class ArgInfo:
    """
    A class to consume builder ArgInfo objects and extract useful information
    to construct an equivalent ibek definition YAML tree.
    """

    description_re = re.compile(r"(.*)\n<(?:type|class)")
    name_re = re.compile(r"iocbuilder\.modules\.(?:.*)\.(.*)")
    arg_num = 1

    def __init__(self, name, unique_name, description, overrides):
        """
        Unique name is the argument that uniquely identifies
        """
        # unique name for the builder class
        self.unique_name = unique_name
        # value overrides for arguments
        self.overrides = overrides

        # list of ordereddict args to be used in the YAML
        self.yaml_args = []
        # the root of the definition in yaml that holds above yaml_args
        self.yaml_defs = ordereddict()
        # set of args and values to use for instantiating a builder object
        self.builder_args = {}
        # list of all the arg names only (across multiple add_arg_info)
        self.all_args = []

        # The arginfo we will consume when calling add_arg_info
        self.arginfo = None

        if description:
            desc = description.strip()
        else:
            desc = "TODO:ADD DESCRIPTION"

        print(name)
        self.yaml_defs["name"] = self.name_re.findall(name)[0]
        self.yaml_defs["description"] = PreservedScalarString(desc)
        self.yaml_defs["args"] = self.yaml_args

    def add_arg_info(self, arginfo):
        """
        Consume an ArgInfo object
        """
        self.arginfo = arginfo
        # we reset builder args for each new ArgInfo - this is because
        # we call once for builder object __init__ and once for each
        # database substitution template. For each we want to record the
        # args for that particular item.
        self.builder_args = {}
        self._interpret()

    def _interpret(self):
        # iterate over all args in the ArgInfo, generating Args in the YAML
        # and builder object args
        all_names = (
            self.arginfo.required_names
            + self.arginfo.default_names
            + self.arginfo.optional_names
        )

        for arg_name in all_names:
            details = self.arginfo.descriptions[arg_name]

            # extract the type and default value
            if arg_name in self.arginfo.default_names:
                index = self.arginfo.default_names.index(arg_name)
                default = self.arginfo.default_values[index]
            else:
                default = None

            typ, default = self.make_arg(arg_name, details, default)

            # extract the name

            # extract the description
            matches = self.description_re.findall(details.desc)
            if len(matches) > 0:
                description_str = matches[0]
            else:
                description_str = "TODO: ADD DESCRIPTION"

            if arg_name not in self.all_args:
                new_yaml_arg = ordereddict()
                new_yaml_arg["type"] = typ
                new_yaml_arg["name"] = arg_name
                new_yaml_arg["description"] = PreservedScalarString(description_str)
                if default:
                    new_yaml_arg["default"] = default
                if typ == "enum":
                    new_yaml_arg["values"] = {
                        str(label): None for label in details.labels
                    }

                self.yaml_args.append(new_yaml_arg)
                self.all_args.append(arg_name)

    def make_arg(self, name, details, default=None):
        """
        Work out the type and default value for an argument.
        Create a builder object arg entry with best guess for a value.
        Support overriding of the guessed values from the command line.
        """

        if name == self.unique_name:
            typ = "id"
            if default == "":
                default = None
            value = default or "ID_" + str(ArgInfo.arg_num)
        elif details.typ == str:
            typ = "str"
            if default == "":
                default = None
            value = default or name + "_STR"
        elif details.typ == int:
            typ = "int"
            if default == "":
                default = 0
            value = default or 1
        elif details.typ == bool:
            typ = "bool"
            value = default or False
        elif details.typ == float:
            typ = "float"
            value = default or 1.0
        elif "iocbuilder.modules" in str(details.typ):
            typ = "object"
            value = MagicMock()
        else:
            typ = "UNKNOWN TODO TODO"

        if hasattr(details, "labels") and typ != "bool":
            value = default or details.labels[0]
            typ = "enum"

        # special case because CS in pmac comes in as even though it is an int
        # TODO needs more investigation
        if name == "CS":
            typ = "int"
            value = MagicMock()

        if name not in self.builder_args:
            if ArgInfo.arg_num in self.overrides:
                value = self.overrides[ArgInfo.arg_num]

            self.builder_args[name] = value

            if isinstance(value, MagicMock):
                value = "Object" + str(ArgInfo.arg_num)
            print(
                "    ARG {:3} {:20} {:<20} {}".format(ArgInfo.arg_num, name, value, typ)
            )

            ArgInfo.arg_num += 1

        return typ, default


class Builder2Support:
    arg_value_overrides = {}

    def __init__(self, support_module_path, arg_value_overrides):
        self.support_module_path = support_module_path
        Builder2Support.arg_value_overrides = arg_value_overrides
        self.yaml_tree = ordereddict()
        self.builder_module, self.builder_classes = self._configure()
        self.dbds = set()
        self.libs = set()

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
            A tuple containing ArgInfo object that describes the arguments
            plus the instantiated builder object.
        """
        print("\nObject %s :" % builder_class.__name__)

        arg_info = ArgInfo(
            name,
            getattr(builder_class, "UniqueName", "name"),
            getattr(builder_class, "__doc__"),
            self.arg_value_overrides,
        )

        for a_cls in (builder_class,) + builder_class.Dependencies:
            if hasattr(a_cls, "ArgInfo"):
                arg_info.add_arg_info(a_cls.ArgInfo)
            if hasattr(a_cls, "LibFileList"):
                self.libs |= set(a_cls.LibFileList)
            if hasattr(a_cls, "DbdFileList"):
                self.dbds |= set(a_cls.DbdFileList)

        builder_object = builder_class(**arg_info.builder_args)

        return arg_info, builder_object

    def _extract_substitutions(self, arginfo):
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

            print("\nDB Template %s :" % template)

            if hasattr(first_substitution, "ArgInfo"):
                arginfo.add_arg_info(first_substitution.ArgInfo)
                # the DB Arg entries in the YAML are Dictionary entries with no value
                no_values = {k: None for k in arginfo.builder_args}
            elif hasattr(first_substitution, "Arguments"):
                no_values = {k: None for k in first_substitution.Arguments}
            else:
                no_values = {"TODO": "No args for this template"}

            database.insert(3, "args", no_values)

        if len(databases) > 0:
            arginfo.yaml_defs["databases"] = databases

    def _make_init_script(self, builder_object, func_name, script, arginfo, when=None):
        """
        Find the source code for a builder class method and create an object
        graph representing as script entries in the ibek YAML file.
        """
        func = getattr(builder_object, func_name, None)
        if func:
            # prepare the YAML for the script entry
            script_item = ordereddict()
            if when:
                script_item["when"] = when

            # extract the print statements from the functions in the source code
            func_text = inspect.getsource(func)
            print_strings = func_text.split("print")[1:]

            command_args = []

            commands = ""
            for print_string in print_strings:
                matches = extract_printed_strings_re.findall(print_string)
                if matches:
                    command_args += macros_re.findall(matches[0][1])
                    line = macros_re.sub(macro_to_jinja_re, matches[0][1])
                    commands += line + "\n"
            if commands:
                script_text = PreservedScalarString(commands)
                missing = set(command_args) - set(arginfo.all_args)
                comment = MISSING + ", ".join(missing) if missing else None

                script_item.insert(3, "value", script_text, comment=comment)

            script.append(script_item)

    def parse_initialise_functions(self, builder_object, arginfo):
        """
        Extract the code from the builder class Initialise() method
        to insert into the ibek YAML script object graph.

        Also extract the code from the builder class PostIocInitialise()
        and InitialiseOnce() methods.

        """
        pre_init = []
        post_init = []
        self._make_init_script(
            builder_object, "InitialiseOnce", pre_init, arginfo, when="first"
        )
        self._make_init_script(builder_object, "Initialise", pre_init, arginfo)
        self._make_init_script(builder_object, "PostIocInitialise", post_init, arginfo)

        if len(pre_init) > 0:
            arginfo.yaml_defs["pre_init"] = pre_init
        if len(post_init) > 0:
            arginfo.yaml_defs["post_init"] = post_init

    def make_yaml_tree(self):
        """
        Main entry point: generate the ibek YAML object graph from
        builder classes.
        """
        self.yaml_tree["module"] = self.builder_module.Name()
        self.yaml_tree["defs"] = []

        for name, builder_class in self.builder_classes.items():
            # make an instance of the builder class and an ArgInfo that
            # describes all its arguments
            arginfo, builder_object = self._make_builder_object(name, builder_class)

            # Go and find all the arguments for all the database templates
            # and insert them plus DB file names into the YAML
            self._extract_substitutions(arginfo)

            # Extract all initialise functions and make script entries
            # for them
            self.parse_initialise_functions(builder_object, arginfo)

            self.yaml_tree["defs"].append(arginfo.yaml_defs)

    def write_yaml_tree(self, filename):
        """
        Convert the yaml object graph into a YAML file
        """

        def tidy_up(yaml):
            # add blank lines between major fields
            for field in [
                "- name:",
                "  databases:",
                "  pre_init:",
                "  post_init:",
                "module",
                "defs",
                "  - type:",
            ]:
                yaml = re.sub(r"(\n%s)" % field, "\n\\g<1>", yaml)

            return yaml

        yaml = YAML()

        yaml.default_flow_style = False

        # add support yaml schema
        self.yaml_tree.yaml_add_eol_comment(
            "yaml-language-server: $schema=https://github.com/epics-"
            "containers/ibek/releases/download/1.2.0/ibek.support.schema.json"
        )

        print("\nWriting YAML output to %s ..." % filename)
        with open(filename, "wb") as f:
            yaml.dump(self.yaml_tree, f, transform=tidy_up)


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
        help="path to the YAML file to be generated (default: ibek.support.yaml)",
        default="ibek.support.yaml",
        nargs="?",
    )
    parser.add_argument(
        "-o",
        "--overrides",
        help=(
            "override a MockArg argument value in the builder class"
            " using the form 'arg_num:value'"
        ),
    )
    args = parser.parse_args()

    arg_overrides = {}
    if args.overrides:
        for o in args.overrides.split(" "):
            m = arg_values_re.match(o)
            assert len(m.groups()) == 2, "Invalid argument format %s" % o
            value = m.group(2)
            if re.match(is_int_re, value):
                value = int(value)
            elif re.match(is_float_re, value):
                value = float(value)
            arg_overrides[int(m.group(1))] = value

    yaml_file = args.yaml

    return args.path, yaml_file, arg_overrides


if __name__ == "__main__":
    support_module_path, filename, arg_value_overrides = parse_args()

    etc_folder = support_module_path + "/etc"
    if not os.path.exists(etc_folder):
        raise ValueError("The support module path must contain an etc folder")

    builder2support = Builder2Support(support_module_path, arg_value_overrides)
    # builder2support.dump_subst_file()
    builder2support.make_yaml_tree()
    if len(builder2support.yaml_tree["defs"]) > 0:
        builder2support.write_yaml_tree(filename)
    else:
        print("\nNo definitions - no YAML file needed for %s" % support_module_path)

    print("\nYou will require the following to make the Generic IOC Dockerfile:\n")
    print("DBD files: " + ", ".join(builder2support.dbds))
    print("LIB files: " + ", ".join(builder2support.libs))
    print("\n")
