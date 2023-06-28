#!/bin/env dls-python
import re
import sys

class_name_re = re.compile(r"class '.*\.(.*)'")
description_re = re.compile(r"(.*)\n<type")

# use dls-python -i builder2ibek.support.py PATH_TO_SUPPORT_MODULE and then
# use global MODULE to interactively inspect the builder Classes
MODULE = None


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


def main():
    if len(sys.argv) != 2:
        print("Usage: %s <path to support module>" % sys.argv[0])
        sys.exit(1)

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
            this_def["description"] = "TODO TODO TODO add description"
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

    yaml = YAML()
    yaml.default_flow_style = False

    yaml.dump(object_tree, sys.stdout)


if __name__ == "__main__":
    # import required packages with pkg_resources
    from pkg_resources import require

    require("iocbuilder")
    require("dls_dependency_tree")
    require("ruamel.yaml")

    # import required modules
    from dls_dependency_tree import dependency_tree
    from iocbuilder import ParseEtcArgs, configure
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap as ordereddict

    main()
