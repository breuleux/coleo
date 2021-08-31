import argparse
import inspect
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

Option = tag.Option
Argument = Option


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
    """Create a catalogue of all ptera variables accessible from the functions.

    The functions are parsed and any global variables they reference are
    followed if they are ptera-tooled.
    """
    results = {}
    _catalogue(set(), results, functions)
    return results


def _find_configurable(catalogue, tag):
    """Return a dict of variables from the catalogue that match the tag."""
    rval = defaultdict(dict)
    for fn, variables in catalogue.items():
        for name, data in variables.items():
            ann = data["annotation"]
            if match_tag(tag, ann):
                rval[name][fn] = data
    return rval


class ArgsExpander:
    """Expand arguments given from files into argv.

    An arguments file must be a ConfigFile. Each key must start with "-" or
    "--" to provide the similarly-named argument. The key "#include" triggers
    inclusion of another file.

    Attributes:
        prefix: The character prefix that triggers reading arguments from
            a file.
        default_file: Automatically add arguments from that file if it exists.
    """

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
        """Expand argument files into the argv list.

        An argument file is any argument that starts with the prefix.
        """
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
    """Parse argv using the given argparser.

    This returns a Namespace.

    * If argv is already a Namespace, it is returned unchanged.
    * If argv is None, sys.argv[1:] is used.
    * If expand is not None, it should be an ArgsExpander.
    """
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
        extras=[],
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
        opts = SimpleNamespace(
            positional=False,
            metavar=None,
            negate=None,
            negate_doc=None,
            group=None,
            name=name,
            optname=optname,
            action="store",
            doc=[],
            nargs=False,
            type=typ,
            aliases=[default_opt],
            loc=loc,
        )

        for entry in docs:
            new_entry = []
            for line in entry.split("\n"):
                m = re.match(r"\[([A-Za-z0-9_-]+)(:.*)?\]", line)
                if m:
                    command, arg = m.groups()
                    command = command.lower()
                    arg = arg and arg[1:].strip()
                    if command in ["alias", "aliases"]:
                        opts.aliases.extend(re.split(r"[ ,;]+", arg))
                    elif command in ["option", "options"]:
                        arg = arg or ""
                        opts.aliases = re.split(r"[ ,;]+", arg)
                    elif command == "group":
                        opts.group = arg
                    elif command == "negate":
                        if arg:
                            opts.negate = re.split(r"[ ,;]+", arg)
                        else:
                            opts.negate = [f"--no-{optname}"]
                        opts.aliases = []
                    elif command == "false-options":
                        if arg:
                            opts.negate = re.split(r"[ ,;]+", arg)
                        else:
                            opts.negate = [f"--no-{optname}"]
                    elif command == "false-options-doc":
                        if not opts.negate:
                            opts.negate = [f"--no-{optname}"]
                        opts.negate_doc = arg
                    elif command == "metavar":
                        opts.metavar = arg
                    elif command == "action":
                        opts.action = arg
                    elif command == "remainder":
                        opts.positional = True
                        opts.nargs = argparse.REMAINDER
                    elif command in ["nargs", "positional"]:
                        opts.positional = command == "positional"
                        opts.nargs = arg or None
                        try:
                            opts.nargs = int(opts.nargs)
                        except Exception:
                            pass
                else:
                    new_entry.append(line)
            opts.doc.append("\n".join(new_entry))

        opts.has_default_opt_name = (
            (opts.aliases and opts.aliases[0] == default_opt),
        )

        for x in data.values():
            x["coleo_options"] = opts
        return opts

    def _fill_argparser(self):
        groups = {}

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

            if entry.group:
                if entry.group not in groups:
                    groups[entry.group] = self.argparser.add_argument_group(
                        title=entry.group
                    )
                group = groups[entry.group]
            else:
                group = self.argparser

            if typ is bool:
                if group is self.argparser and entry.negate is not None:
                    group = self.argparser.add_mutually_exclusive_group()

                if aliases:
                    group.add_argument(
                        *aliases,
                        dest=name,
                        action="store_true",
                        help="; ".join(optdoc),
                    )

                if entry.negate:
                    if entry.negate_doc:
                        doc = entry.negate_doc
                    elif aliases:
                        doc = f"Set {aliases[0]} to False"
                    else:
                        doc = "; ".join(optdoc)
                    group.add_argument(
                        *entry.negate,
                        dest=name,
                        action="store_false",
                        help=doc,
                    )
            else:
                if entry.positional:
                    group.add_argument(
                        name,
                        type=self.resolver(typ or None),
                        action=entry.action,
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
                    group.add_argument(
                        *aliases,
                        dest=name,
                        type=self.resolver(typ or None),
                        action=entry.action,
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


def _make_cli_helper(parser, entry, extras, **kwargs):
    if isinstance(entry, dict):
        subparsers = parser.add_subparsers()
        for name, subentry in entry.items():
            if name == "__doc__":
                continue
            elif name == "__main__":
                _make_cli_helper(parser, subentry, extras, **kwargs)
                continue
            subparser = subparsers.add_parser(
                name, help=_getdoc(subentry), argument_default=argparse.SUPPRESS
            )
            _make_cli_helper(subparser, subentry, extras, **kwargs)

    elif inspect.isclass(entry):
        structure = {"__doc__": entry.__doc__}
        for name, entry2 in vars(entry).items():
            if isinstance(entry2, FunctionType):
                entry2 = tooled(entry2)
                setattr(entry, name, entry2)
                structure[name] = entry2
            elif isinstance(entry2, (PteraFunction, dict, type)):
                structure[name] = entry2
        return _make_cli_helper(parser, structure, extras, **kwargs)

    else:
        if isinstance(entry, FunctionType):
            entry = tooled(entry)
        if not isinstance(entry, PteraFunction):
            raise TypeError(
                f"Expected a class, dict a function, not {type(entry)}"
            )
        all_entries = [entry, *extras, getattr(entry, "coleo_extras", [])]
        cfg = Configurator(entry_point=all_entries, argparser=parser, **kwargs)
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
    return _setvars(values, tag=Option)


def make_cli(
    entry,
    *,
    argv=None,
    extras=[],
    tag=Option,
    description=None,
    eval_env=None,
    expand=None,
):
    """Create a coleo CLI from a function, dict or class.

    Arguments:
        entry: A function, dict or class. If a dict or class, each name/method
            must take no arguments (not even self) and will be mapped to a
            subcommand.
        argv: List of command-line arguments. Defaults to sys.argv[1:].
        extras: List of tooled functions that define options and may be called
            by the entry function. This is only necessary if these functions
            cannot be found by following references from the entry function.
        tag: The tag that variables must be annotated with to appear as options.
            This defaults to Option and it is not recommended to change it.
        description: Description of the command.
        eval_env: Environment to evaluate arguments of the form ":symbol". If
            provided, a sequence of options such as `--opt :x` will try to
            resolve `eval_env["x"]`.
        expand: An ArgsExpander to use to fill in all the arguments.

    Returns:
        The tuple (opts, call) such that the command-line application can be
        run by calling `call(opts=opts)`.
    """
    if expand is None or isinstance(expand, str):
        expand = ArgsExpander(prefix=expand or "", default_file=None)

    parser = argparse.ArgumentParser(
        description=description or _getdoc(entry),
        argument_default=argparse.SUPPRESS,
    )
    _make_cli_helper(parser, entry, tag=tag, eval_env=eval_env, extras=extras)
    opts = parse_options(parser, argv=argv, expand=expand)
    cfg, fn = getattr(opts, "#cfg", (None, None))
    if cfg is None:
        parser.print_help()
        sys.exit(1)

    def thunk(opts=opts, args=()):
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
            return result

    return opts, thunk


def run_cli(entry, args=(), **kwargs):
    """Run a coleo CLI from a function, dict or class and return the result.

    Arguments:
        entry: A function, dict or class. If a dict or class, each name/method
            must take no arguments (not even self) and will be mapped to a
            subcommand.
        args: Tuple of arguments to provide to the function (default: ()).
        argv: List of command-line arguments. Defaults to sys.argv[1:].
        extras: List of tooled functions that define options and may be called
            by the entry function. This is only necessary if these functions
            cannot be found by following references from the entry function.
        tag: The tag that variables must be annotated with to appear as options.
            This defaults to Option and it is not recommended to change it.
        description: Description of the command.
        eval_env: Environment to evaluate arguments of the form ":symbol". If
            provided, a sequence of options such as `--opt :x` will try to
            resolve `eval_env["x"]`.
        expand: An ArgsExpander to use to fill in all the arguments.

    Returns:
        The return value of the entry function after it was called.
    """
    opts, call = make_cli(entry, **kwargs)
    return call(opts=opts, args=args)


def auto_cli(entry, args=(), **kwargs):  # pragma: no cover
    """Run a coleo CLI from a function, dict or class and print the result.

    Arguments:
        entry: A function, dict or class. If a dict or class, each name/method
            must take no arguments (not even self) and will be mapped to a
            subcommand.
        args: Tuple of arguments to provide to the function (default: ()).
        argv: List of command-line arguments. Defaults to sys.argv[1:].
        extras: List of tooled functions that define options and may be called
            by the entry function. This is only necessary if these functions
            cannot be found by following references from the entry function.
        tag: The tag that variables must be annotated with to appear as options.
            This defaults to Option and it is not recommended to change it.
        description: Description of the command.
        eval_env: Environment to evaluate arguments of the form ":symbol". If
            provided, a sequence of options such as `--opt :x` will try to
            resolve `eval_env["x"]`.
        expand: An ArgsExpander to use to fill in all the arguments.

    Returns:
        The entry function.
    """
    if inspect.isfunction(entry):
        entry = tooled(entry)
    result = run_cli(entry, args, **kwargs)
    if result is not None:
        print(result)
    return entry


def with_extras(*extras):
    def deco(fn):
        if not isinstance(fn, PteraFunction):
            fn = tooled(fn)
        fn.coleo_extras = extras
        return fn

    return deco
