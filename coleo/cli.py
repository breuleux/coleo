import argparse
import os
import re
import sys
from collections import defaultdict
from contextlib import contextmanager
from itertools import count
from types import FunctionType, SimpleNamespace

from ptera import (
    ABSENT,
    BaseOverlay,
    PteraFunction,
    Tag,
    TagSet,
    match_tag,
    select,
    tag,
    tooled,
)
from ptera.selfless import PreState, PteraNameError

from .config import ConfigFile

Argument = tag.Argument


_count = count()


def _catalogue(seen, results, fn):
    if id(fn) in seen:
        return

    seen.add(id(fn))

    if isinstance(fn, PteraFunction):
        state = fn.state.state if isinstance(fn.state, PreState) else fn.state
        tst = type(state)
        res = tst.__info__
        results[fn] = res
        for name, ann in res.items():
            val = getattr(state, name, ABSENT)
            _catalogue(seen, results, val)

    elif isinstance(fn, (list, tuple)):
        for entry in fn:
            _catalogue(seen, results, entry)


def catalogue(functions):
    results = {}
    _catalogue(set(), results, functions)
    return results


def _find_configurable(catalogue, tag):
    rval = defaultdict(dict)
    for fn, variables in catalogue.items():
        for name, data in variables.items():
            ann = data["annotation"]
            if match_tag(tag, ann):
                rval[name][fn] = data
    return rval


class ArgsExpander:
    def __init__(self, prefix, default_file=None):
        self.prefix = prefix
        self.default_file = default_file
        if default_file:
            assert self.prefix

    def _generate_args_from_dict(self, contents):
        results = []
        for key, value in contents.items():
            if key == "#include":
                if not isinstance(value, (list, tuple)):
                    value = [value]
                for other_filename in value:
                    results.extend(
                        self._generate_args_from_file(other_filename)
                    )

            elif key == "#command":
                results.insert(0, value)

            elif key.startswith("-"):
                results.append(key)
                results.append(str(value))

            elif isinstance(value, bool):
                if value:
                    results.append(f"--{key}")
                else:
                    results.append(f"--no-{key}")

            else:
                results.append(f"--{key}")
                results.append(str(value))
        return results

    def _generate_args_from_file(self, filename):
        contents = ConfigFile(filename).read()
        return self._generate_args_from_dict(contents)

    def expand(self, argv):
        if self.default_file:
            if os.path.exists(self.default_file):
                pfx = self.prefix[0]
                argv.insert(0, f"{pfx}{self.default_file}")

        new_args = []
        for arg in argv:
            if isinstance(arg, dict):
                new_args.extend(self._generate_args_from_dict(arg))
            elif not arg or arg[0] not in self.prefix:
                new_args.append(arg)
            else:
                new_args.extend(self._generate_args_from_file(arg[1:]))
        return new_args

    def __call__(self, argv, *, parser):
        try:
            return self.expand(argv)
        except OSError:
            err = sys.exc_info()[1]
            parser.error(str(err))


def parse_options(parser, *, argv=None, expand=None):
    if isinstance(argv, argparse.Namespace):
        args = argv
    elif isinstance(argv, dict):
        args = argparse.Namespace(**argv)
    else:
        argv = sys.argv[1:] if argv is None else argv
        if expand:
            argv = expand(argv, parser=parser)
        args = parser.parse_args(argv)
    return args


class Configurator:
    def __init__(
        self,
        *,
        argparser,
        entry_point=None,
        tag=Argument,
        description=None,
        eval_env=None,
        expand=None,
    ):
        cg = catalogue(entry_point)
        self.tag = tag
        self.names = _find_configurable(cg, tag)
        self.argparser = argparser
        self._fill_argparser()
        self.eval_env = eval_env
        self.expand = expand

    def _analyze_entry(self, name, data):
        docs = set()
        for fn, entry in data.items():
            if entry["doc"]:
                docs.add(entry["doc"])
            else:
                docs.add(f"Parameter in {fn}")

        loc = None
        if len(data) == 1:
            (sole_data,) = list(data.values())
            loc = sole_data["location"]

        optname = name.replace("_", "-")
        typ = []
        for x in data.values():
            ann = x["annotation"]
            if isinstance(ann, TagSet):
                members = ann.members
            else:
                members = [ann]
            for m in members:
                if not isinstance(m, Tag):
                    typ.append(m)
        if len(typ) != 1:
            typ = None
        else:
            (typ,) = typ

        default_opt = f"--{optname}"
        aliases = [default_opt]
        nargs = False
        positional = False
        metavar = None
        optdoc = []
        for entry in docs:
            new_entry = []
            for line in entry.split("\n"):
                m = re.match(r"\[([A-Za-z0-9_-]+)(:.*)?\]", line)
                if m:
                    command, arg = m.groups()
                    command = command.lower()
                    arg = arg and arg[1:].strip()
                    if command in ["alias", "aliases"]:
                        aliases.extend(re.split(r"[ ,;]+", arg))
                    elif command in ["option", "options"]:
                        aliases = re.split(r"[ ,;]+", arg)
                    elif command == "metavar":
                        metavar = arg
                    elif command == "remainder":
                        positional = True
                        nargs = argparse.REMAINDER
                    elif command in ["nargs", "positional"]:
                        positional = command == "positional"
                        nargs = arg or None
                        try:
                            nargs = int(nargs)
                        except Exception:
                            pass
                else:
                    new_entry.append(line)
            optdoc.append("\n".join(new_entry))

        opts = SimpleNamespace(
            positional=positional,
            metavar=metavar,
            name=name,
            optname=optname,
            doc=optdoc,
            nargs=nargs,
            type=typ,
            aliases=aliases,
            loc=loc,
            has_default_opt_name=(aliases[0] == default_opt),
        )
        for x in data.values():
            x["coleo_options"] = opts
        return opts

    def _fill_argparser(self):
        entries = [
            self._analyze_entry(name, data) for name, data in self.names.items()
        ]

        positional = list(
            sorted(
                (entry for entry in entries if entry.positional),
                key=lambda entry: entry.loc[-1] if entry.loc else -1,
            )
        )
        if len(positional) > 1:
            if any(entry.loc is None for entry in positional):
                raise Exception(
                    "Positional arguments cannot be defined in multiple"
                    " functions."
                )
            loc0 = positional[0].loc[:2]
            if not all(
                entry.loc is not None and entry.loc[:2] == loc0
                for entry in positional
            ):
                raise Exception(
                    "All positional arguments must be defined in the same"
                    " function."
                )

        nonpositional = list(
            sorted(
                (entry for entry in entries if not entry.positional),
                key=lambda entry: entry.name,
            )
        )

        entries = positional + nonpositional

        for entry in entries:
            name = entry.name
            typ = entry.type
            aliases = entry.aliases
            nargs = entry.nargs
            optdoc = entry.doc
            optname = entry.optname

            if typ is bool:
                group = self.argparser.add_mutually_exclusive_group()
                group.add_argument(
                    *aliases,
                    dest=name,
                    action="store_true",
                    help="; ".join(optdoc),
                )
                if entry.has_default_opt_name:
                    group.add_argument(
                        f"--no-{optname}",
                        dest=name,
                        action="store_false",
                        help=f"Set --{optname} to False",
                    )
            else:
                if entry.positional:
                    self.argparser.add_argument(
                        name,
                        type=self.resolver(typ or None),
                        action="store",
                        nargs=nargs,
                        metavar=name.upper(),
                        default=[] if nargs == "*" else None,
                        help="; ".join(optdoc),
                    )
                else:
                    _metavars = {
                        int: "NUM",
                        float: "NUM",
                        argparse.FileType: "FILE",
                    }
                    ttyp = typ if isinstance(typ, type) else type(typ)
                    mv = entry.metavar or _metavars.get(ttyp, "VALUE")
                    nargs_kw = {"nargs": nargs} if nargs else {}
                    self.argparser.add_argument(
                        *aliases,
                        dest=name,
                        type=self.resolver(typ or None),
                        action="store",
                        metavar=mv,
                        help="; ".join(optdoc),
                        **nargs_kw,
                    )

    def resolver(self, typ):
        def resolve(arg):
            if typ is str:
                return arg
            elif re.match(r"^:[A-Za-z_0-9]+:", arg):
                _, modname, code = arg.split(":", 2)
                mod = __import__(modname)
                return eval(code, vars(mod))
            elif arg.startswith(":"):
                if not self.eval_env:
                    raise Exception(f"No environment to evaluate {arg}")
                return eval(arg[1:], self.eval_env)
            else:
                return arg if typ is None else typ(arg)

        resolve.__name__ = getattr(typ, "__name__", str(typ))
        return resolve

    @contextmanager
    def __call__(self, argv=None):
        opts = parse_options(self.argparser, argv=argv, expand=self.expand)
        opts = {k: v for k, v in vars(opts).items() if not k.startswith("#")}
        with _setvars(opts, self.tag):
            yield opts


def _getdoc(obj):
    if isinstance(obj, dict):
        return obj.get("__doc__", None)
    else:
        return getattr(obj, "__doc__", None)


def _auto_cli_helper(parser, entry, **kwargs):
    if isinstance(entry, dict):
        subparsers = parser.add_subparsers()
        for name, subentry in entry.items():
            if name == "__doc__":
                continue
            subparser = subparsers.add_parser(
                name, help=_getdoc(subentry), argument_default=argparse.SUPPRESS
            )
            _auto_cli_helper(subparser, subentry)
    else:
        if isinstance(entry, FunctionType):
            entry = tooled(entry)
        if not isinstance(entry, PteraFunction):
            raise TypeError(f"Expected a dict or a function, not {type(entry)}")
        cfg = Configurator(entry_point=entry, argparser=parser, **kwargs)
        parser.set_defaults(**{"#cfg": (cfg, entry)})


def _setvars(values, tag):
    def _resolver(value):
        return lambda **_: value

    return BaseOverlay(
        {
            select(f"{name}:##X", env={"##X": tag}): {"value": _resolver(value)}
            for name, value in values.items()
        }
    )


def setvars(**values):
    return _setvars(values, tag=Argument)


def auto_cli(
    entry,
    args=(),
    *,
    argv=None,
    entry_point=None,
    tag=Argument,
    description=None,
    eval_env=None,
    expand=None,
    print_result=True,
    return_split=False,
):
    if expand is None or isinstance(expand, str):
        expand = ArgsExpander(prefix=expand or "", default_file=None,)

    parser = argparse.ArgumentParser(
        description=description or _getdoc(entry),
        argument_default=argparse.SUPPRESS,
    )
    _auto_cli_helper(parser, entry, tag=tag, eval_env=eval_env)
    opts = parse_options(parser, argv=argv, expand=expand)
    cfg, fn = getattr(opts, "#cfg", (None, None))
    if cfg is None:
        parser.print_help()
        sys.exit(1)

    def thunk(opts=opts, args=args):
        with cfg(opts):
            try:
                result = fn(*args)
            except PteraNameError as err:
                optinfo = err.info().get("coleo_options", None)
                if optinfo:
                    optname = optinfo.aliases[0]
                    print(
                        f"error: missing value for required argument: {optname}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                else:
                    raise
            if print_result and result is not None:
                print(result)
            return result

    if return_split:
        return opts, thunk
    else:
        return thunk(opts)
