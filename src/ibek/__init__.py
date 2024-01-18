from importlib.metadata import version

__version__ = version("ibek")
del version

__all__ = ["__version__"]
