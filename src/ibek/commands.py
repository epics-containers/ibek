import operator

from semantic_version import Version


def semver_compare(base: str, target: str) -> bool:
    """
    Compare two semVer strings similarly to pip's requirements specifier syntax
    """
    ops = {
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        ">": operator.gt,
        "<": operator.lt,
    }
    for op in ops.keys():
        if op in target:
            in_op = op
            target = target.strip(op)
            break

    if ops[in_op](Version.coerce(base), Version.coerce(target)):
        return True
    else:
        return False
