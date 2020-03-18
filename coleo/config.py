import json
import os

from ptera import ABSENT

format_registry = {}


def register_extension(*extensions):
    def deco(fn):
        for ext in extensions:
            format_registry[ext] = fn
        return fn

    return deco


@register_extension("json")
def formatter_json():
    return {
        "load": json.load,
        "dump": json.dump,
    }


@register_extension("yaml")
def formatter_yaml():
    try:
        import yaml
    except ModuleNotFoundError:  # pragma: no cover
        raise OSError(
            f"Please install the 'pyyaml' module to read '.yaml' files"
        )
    return {
        "load": yaml.full_load,
        "dump": yaml.dump,
    }


@register_extension("toml")
def formatter_toml():
    try:
        import toml
    except ModuleNotFoundError:  # pragma: no cover
        raise OSError(f"Please install the 'toml' module to read '.toml' files")
    return {
        "load": toml.load,
        "dump": toml.dump,
    }


def _read_cfg(file):
    import configparser

    parser = configparser.ConfigParser()
    s = file.read()
    parser.read_string(s)
    if parser.sections() != ["default"]:
        raise OSError(
            "A cfg/ini file containing options must only contain"
            " the [default] section"
        )
    return dict(parser["default"])


@register_extension("cfg", "ini")
def formatter_cfg():
    return {
        "load": _read_cfg,
    }


class ConfigFile:
    def __init__(self, filename, registry=format_registry):
        self.filename = os.path.expanduser(filename)
        ext = filename.split(".")[-1]
        fmt = registry.get(ext, None)
        if fmt is None:
            raise OSError(f"Cannot read file format: '{ext}'")
        self.format = fmt()

    def read(self, default=ABSENT):
        try:
            with open(self.filename) as f:
                return self.format["load"](f)
        except FileNotFoundError:
            if default is ABSENT:
                raise
            return default

    def write(self, contents):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as f:
            return self.format["dump"](contents, f)


def config(filename):
    if any(filename.startswith(c) for c in '{["'):
        return json.loads(filename)
    else:
        return ConfigFile(filename).read()
