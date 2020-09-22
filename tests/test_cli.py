import json

import pytest

from coleo import (
    ABSENT,
    ArgsExpander,
    ConflictError,
    Option,
    catalogue,
    default,
    make_cli,
    run_cli,
    setvars,
    tag,
    tooled,
    with_extras,
)

from .common import one_test_per_assert


@tooled
def lager(x, y):
    z: Option & tag.Boption & int
    return x + y + z


@tooled
def stout(v):
    # Double you,
    # Double me
    w: Option & int = default(1)
    # This is your cue
    # [metavar: CUE]
    q: Option & int = 2
    a = lager(v, w)
    b = lager(v, q)
    return a, b


@tooled
def thing():
    arg: Option & str
    return arg


@tooled
def thingy():
    # [group: puorg]
    arg: Option
    return arg


def test_catalogue():
    def _catalogue(root):
        cat = catalogue(root)
        return {
            fn: {
                k: {"annotation": v["annotation"], "doc": v["doc"]}
                for k, v in fvars.items()
            }
            for fn, fvars in cat.items()
        }

    assert _catalogue(lager) == {
        lager: {
            "Option": {"annotation": ABSENT, "doc": None},
            "tag": {"annotation": ABSENT, "doc": None},
            "int": {"annotation": ABSENT, "doc": None},
            "x": {"annotation": ABSENT, "doc": None},
            "y": {"annotation": ABSENT, "doc": None},
            "z": {"annotation": tag.Option & tag.Boption & int, "doc": None},
        },
    }

    assert _catalogue(stout) == {
        **_catalogue(lager),
        stout: {
            "Option": {"annotation": ABSENT, "doc": None},
            "int": {"annotation": ABSENT, "doc": None},
            "w": {
                "annotation": tag.Option & int,
                "doc": "Double you,\nDouble me",
            },
            "q": {
                "annotation": tag.Option & int,
                "doc": "This is your cue\n[metavar: CUE]",
            },
            "a": {"annotation": ABSENT, "doc": None},
            "b": {"annotation": ABSENT, "doc": None},
            "default": {"annotation": ABSENT, "doc": None},
            "lager": {"annotation": ABSENT, "doc": None},
            "v": {"annotation": ABSENT, "doc": None},
        },
    }

    assert catalogue([lager, stout]) == catalogue(stout)


@one_test_per_assert
def test_cli():
    assert (
        run_cli(
            lager, ("a", "b"), argv="--z=:foo".split(), eval_env={"foo": "c"},
        )
        == "abc"
    )
    assert run_cli(lager, (3, 2), argv="--z=:math:cos(0)".split(),) == 6
    assert run_cli(stout, (3,), argv="--z=3".split()) == (7, 8)
    assert run_cli(stout, (3,), argv="--z=3 --w=10".split()) == (16, 8)
    assert run_cli(stout, (3,), tag=tag.Boption, argv="--z=3".split()) == (
        7,
        8,
    )

    assert run_cli(thingy, (), argv=["--arg", "1"]) == "1"
    assert run_cli(thingy, (), argv=["--arg", "xyz"]) == "xyz"
    assert (
        run_cli(thingy, (), eval_env={"foo": "bar"}, argv=["--arg", ":foo"],)
        == "bar"
    )
    assert run_cli(
        thingy, (), eval_env={"foo": [1, 2, 3]}, argv=["--arg", ":foo"],
    ) == [1, 2, 3]

    assert (
        run_cli(thing, (), eval_env={"foo": [1, 2, 3]}, argv=["--arg", ":foo"],)
        == ":foo"
    )


def test_make_cli():
    opts, thunk = make_cli(stout, (3,), argv="--z=3".split(), return_split=True)
    opts = {k: v for k, v in vars(opts).items() if not k.startswith("#")}
    assert opts == {"z": 3}
    assert thunk() == (7, 8)
    assert thunk(opts={"z": 4}) == (8, 9)
    assert thunk(args=(4,)) == (8, 9)
    assert thunk({"z": 4}, (4,)) == (9, 10)


def test_no_env():
    with pytest.raises(Exception):
        run_cli(
            lager, ("a", "b"), argv="--z=:foo".split(),
        )


def test_unknown_argument():
    with pytest.raises(SystemExit) as exc:
        run_cli(stout, (3,), argv="--x=4".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        run_cli(stout, (3,), tag=tag.Boption, argv="--z=3 --w=10".split())
    assert exc.value.code == 2


def test_conflict():
    with pytest.raises(ConflictError):
        run_cli(stout, (3,), argv="--z=3 --q=10".split())


def test_required_argument():
    with pytest.raises(SystemExit):
        run_cli(lager, (3, 4), argv=[])


def test_missing_global():
    def wish():
        return love

    with pytest.raises(NameError):
        run_cli(wish, (), argv=[])


def patriotism():
    # Whether to wave the flag or not
    # [false-options]
    # [aliases: -f --yay]
    flag: Option & bool = default(True)
    # [options: -n]
    times: Option & int = default(1)
    if flag:
        return "wave" * times
    else:
        return "don't wave"


def test_types():
    assert run_cli(patriotism, (), argv=[]) == "wave"
    assert run_cli(patriotism, (), argv="-f".split()) == "wave"
    assert run_cli(patriotism, (), argv="--flag".split()) == "wave"
    assert run_cli(patriotism, (), argv="--no-flag".split()) == "don't wave"
    assert (
        run_cli(patriotism, (), argv="--flag -n 3".split(),) == "wavewavewave"
    )
    with pytest.raises(SystemExit) as exc:
        run_cli(patriotism, (), argv="--flag=1".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        run_cli(patriotism, (), argv="--flag --times=3".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        run_cli(patriotism, (), argv="-n ohno".split())
    assert exc.value.code == 2


def test_config_file(tmpdir):
    cfg1 = tmpdir.join("config1.json")
    cfg1.write(json.dumps({"z": 3, "w": 10}))

    assert run_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)

    assert run_cli(stout, (3,), argv=[f"@{cfg1.strpath}"], expand="@",) == (
        16,
        8,
    )

    assert run_cli(stout, (3,), argv=[f"&{cfg1.strpath}"], expand="@&",) == (
        16,
        8,
    )

    cfg2 = tmpdir.join("config2.json")
    with pytest.raises(SystemExit) as exc:
        run_cli(
            stout, (3,), argv=f"@{cfg2.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2

    cfg3 = tmpdir.join("config3.json")
    cfg3.write(json.dumps({"#include": cfg1.strpath, "w": 10}))
    assert run_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg3),
    ) == (16, 8)

    assert run_cli(stout, (3,), argv=[{"#include": cfg1.strpath}],) == (16, 8)


def test_config_toml(tmpdir):
    cfg1 = tmpdir.join("config1.toml")
    cfg1.write("z = 3\nw = 10\n")

    assert run_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)


def test_config_cfg(tmpdir):
    cfg1 = tmpdir.join("config1.cfg")
    cfg1.write("[default]\nz = 3\nw = 10\n")

    assert run_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)

    cfg2 = tmpdir.join("config2.cfg")
    cfg2.write("[ohno]\nz = 3\nw = 10\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(
            stout, (3,), argv=f"@{cfg2.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2


def test_config_yaml(tmpdir):
    cfg1 = tmpdir.join("config1.yaml")
    cfg1.write("z: 3\nw: 10\n")

    assert run_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)


def test_config_unknown(tmpdir):
    cfg1 = tmpdir.join("config1.whatisthis")
    cfg1.write("z: 3\nw: 10\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(
            stout, (3,), argv=f"@{cfg1.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2


def test_config_dict():
    assert run_cli(stout, (3,), argv=[{"z": 3, "w": 10}],) == (16, 8)

    assert (
        run_cli(patriotism, (), argv=[{"flag": True, "-n": 2}],) == "wavewave"
    )

    assert run_cli(patriotism, (), argv=[{"flag": False}],) == "don't wave"


def test_bad_entry():
    with pytest.raises(TypeError):
        run_cli([patriotism], (), argv="--flag")


def test_subcommands():
    assert (
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="thingy --arg xyz".split(),
        )
        == "xyz"
    )

    assert (
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="patriotism --flag".split(),
        )
        == "wave"
    )

    assert (
        run_cli(
            {"thingy": thingy, "patri": {"otism": patriotism}},
            (),
            argv="patri otism --flag".split(),
        )
        == "wave"
    )

    assert (
        run_cli(
            {
                "thingy": thingy,
                "patri": {
                    "__doc__": "Vaccines certainly don't cause",
                    "otism": patriotism,
                },
            },
            (),
            argv="patri otism --flag".split(),
        )
        == "wave"
    )

    with pytest.raises(SystemExit) as exc:
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="thingy --flag".split(),
        )
    assert exc.value.code == 2

    assert (
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=["patriotism", {"flag": True}],
        )
        == "wave"
    )

    # Test with no arguments
    with pytest.raises(SystemExit) as exc:
        assert (
            run_cli({"thingy": thingy, "patriotism": patriotism}, (), argv="",)
            == "xyz"
        )
    assert exc.value.code == 1


def test_config_subcommands(tmpdir):
    cfg1 = tmpdir.join("config1.json")
    cfg1.write(json.dumps({"flag": True}))

    assert (
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"patriotism @{cfg1.strpath}".split(),
            expand="@",
        )
        == "wave"
    )

    cfg2 = tmpdir.join("config2.json")
    with pytest.raises(SystemExit) as exc:
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"patriotism @{cfg2.strpath}".split(),
            expand="@",
        )
    assert exc.value.code == 2

    cfg3 = tmpdir.join("config1.json")
    cfg3.write(json.dumps({"#command": "patriotism", "flag": True}))
    assert (
        run_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"@{cfg3.strpath}".split(),
            expand="@",
        )
        == "wave"
    )


class farm:
    def build():
        material: Option
        return f"built farm out of {material}"

    class duck:
        def honk():
            repeat: Option & int = default(10)
            return "honk" * repeat

        def eat():
            peas: Option & bool = default(False)
            if peas:
                return "nom nom nom"


def test_subcommands_as_class():
    assert (
        run_cli(farm, argv="build --material wood".split())
        == "built farm out of wood"
    )

    assert run_cli(farm, argv="duck honk --repeat 3".split()) == "honkhonkhonk"


@tooled
def groot():
    # Name to groot
    # [positional]
    name: Option
    return f"Grootings, {name}!"


@tooled
def translate():
    # Translation vector
    # [positional: 2]
    vector: Option & int
    return vector


@tooled
def reverso():
    # Things to reverse
    # [positional: *]
    things: Option
    things.reverse()
    return things


def test_positional():
    assert run_cli(groot, (), argv=["Marcel"]) == "Grootings, Marcel!"

    with pytest.raises(SystemExit):
        run_cli(groot, (), argv=[])

    assert run_cli(translate, (), argv=["4", "7"]) == [4, 7]

    with pytest.raises(SystemExit):
        run_cli(translate, (), argv=["4"])

    with pytest.raises(SystemExit):
        run_cli(translate, (), argv=["4", "7", "8"])

    assert run_cli(reverso, (), argv=list("goomba")) == list("abmoog")
    assert run_cli(reverso, (), argv=[]) == []


@tooled
def multipos():
    # [positional]
    one: Option
    # [positional]
    two: Option
    return two, one


def test_multiple_positional():
    assert run_cli(multipos, (), argv=["hello", "there"]) == ("there", "hello")


@tooled
def scattered_multipos():
    # [positional]
    three: Option
    return multipos()


@tooled
def scattered_multipos2():
    # [positional]
    two: Option
    return multipos()


def test_multiple_positional_bad():
    with pytest.raises(Exception):
        run_cli(scattered_multipos, (), argv=["hello", "there"])
    with pytest.raises(Exception):
        run_cli(scattered_multipos2, (), argv=["hello", "there"])


@tooled
def leftovers():
    # [positional]
    one: Option
    # [remainder]
    nomnom: Option
    return nomnom


def test_leftovers():
    assert run_cli(leftovers, (), argv=["hello", "there"]) == ["there"]
    assert run_cli(leftovers, (), argv="book".split()) == []
    assert run_cli(leftovers, (), argv="my --pear --orange".split()) == [
        "--pear",
        "--orange",
    ]


@tooled
def ice_cream():
    # [nargs: 2]
    duo: Option & int

    # [nargs: *]
    tang: Option & int

    return duo, tang


def test_nargs():
    assert run_cli(ice_cream, (), argv="--duo 1 2 --tang".split()) == (
        [1, 2],
        [],
    )
    assert run_cli(ice_cream, (), argv="--tang --duo 1 2".split()) == (
        [1, 2],
        [],
    )
    assert run_cli(ice_cream, (), argv="--duo 1 2 --tang 3 4 5".split()) == (
        [1, 2],
        [3, 4, 5],
    )


def test_setvars():
    with setvars(z=3, w=10):
        assert stout(3) == (16, 8)


@tooled
def accum():
    # [action: append]
    junk: Option = default([])

    # [action: append]
    # [nargs: +]
    clusters: Option = default([])

    return junk, clusters


def test_append():
    assert run_cli(accum, (), argv=["--junk", "x", "--junk", "y"]) == (
        ["x", "y"],
        [],
    )
    with pytest.raises(SystemExit):
        run_cli(accum, (), argv=["--junk", "x", "y"])

    assert run_cli(
        accum, (), argv=["--clusters", "x", "y", "--clusters", "z"]
    ) == ([], [["x", "y"], ["z"]])
    assert run_cli(
        accum, (), argv=["--clusters", "x", "--junk", "y", "--clusters", "z"]
    ) == (["y"], [["x"], ["z"]])


@tooled
def boo():
    # [negate: --clap]
    # No jeering
    jeer: Option & bool = default(True)

    # [negate]
    # Lack of goodness
    good: Option & bool = default(True)

    # Potato!
    # [false-options: --famine]
    # [false-options-doc: No potato]
    potato: Option & bool = default(None)

    return jeer, good, potato


def test_negate():
    assert run_cli(boo, (), argv=["--clap"]) == (False, True, None)
    with pytest.raises(SystemExit):
        run_cli(boo, (), argv=["--jeer"])

    assert run_cli(boo, (), argv=["--no-good"]) == (True, False, None)
    with pytest.raises(SystemExit):
        run_cli(boo, (), argv=["--good"])

    assert run_cli(boo, (), argv=["--potato"]) == (True, True, True)
    assert run_cli(boo, (), argv=["--famine"]) == (True, True, False)


def spaghetti(funcs):
    rval = []
    for func in funcs:
        func(rval)
    return rval


@tooled
def append_number(rval):
    num: Option & int = default(None)
    if num is not None:
        rval.append(num)


@tooled
def append_bool(rval):
    # [false-options-doc: No boo!]
    boo: Option & bool = default(None)
    if boo is not None:
        rval.append(boo)


@with_extras(append_number, append_bool)
def fettucini(funcs):
    rval = []
    for func in funcs:
        func(rval)
    return rval


def test_extras():
    fns = [append_number, append_bool]
    assert run_cli(
        spaghetti, (fns,), extras=fns, argv="--num 37 --boo".split()
    ) == [37, True]

    assert run_cli(
        spaghetti, (fns,), extras=fns, argv="--boo --num 37".split()
    ) == [37, True]

    assert run_cli(spaghetti, (fns,), extras=fns, argv="--no-boo".split()) == [
        False
    ]

    assert run_cli(fettucini, (fns,), argv="--boo --num 37".split()) == [
        37,
        True,
    ]
