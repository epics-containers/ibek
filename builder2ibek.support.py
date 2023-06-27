#!/bin/env dls-python
import re
import sys

class_name_re = re.compile(r"class '.*\.(.*)'")
description_re = re.compile(r"(.*)\n<type")


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

    release_file = sys.argv[1] + "/configure/RELEASE"

    MODULE_TREE = ordereddict()

    Configure()
    ImportFunctions()

    # load builder modules for a single support module ADCore
    tree = dependency_tree(None, release_file)

    for leaf in tree.leaves:
        ModuleVersion(leaf.name, leaf.version)

    m = ModuleVersion(tree.name, tree.version)
    MODULE_TREE["module"] = tree.name
    defs = MODULE_TREE["defs"] = []

    for builder_class in m.ClassesList:
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

    yaml.dump(MODULE_TREE, sys.stdout)


if __name__ == "__main__":
    # import required packages with pkg_resources
    from pkg_resources import require

    require("iocbuilder")
    require("dls_dependency_tree")
    require("ruamel.yaml")

    # import required modules
    from dls_dependency_tree import dependency_tree
    from iocbuilder.configure import Configure
    from iocbuilder.libversion import ModuleVersion
    from iocbuilder.mydbstatic import ImportFunctions
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap as ordereddict

    main()
