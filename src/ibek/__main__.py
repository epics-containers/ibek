from argparse import ArgumentParser

from . import __version__

__all__ = ["change_linter_to_ruff"]


def change_linter_to_ruff(args=None):
    parser = ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=__version__)
    args = parser.parse_args(args)


# test with: python -m ibek
if __name__ == "__change_linter_to_ruff__":
    change_linter_to_ruff()
