import json

import pytest

from coleo import (
    ABSENT,
    ArgsExpander,
    Argument,
    ConflictError,
    auto_cli,
    catalogue,
    default,
    setvars,
    tag,
    tooled,
)

from .common import one_test_per_assert


@tooled
def lager(x, y):
    z: Argument & tag.Bargument & int
    return x + y + z


@tooled
def stout(v):
    # Double you,
    # Double me
    w: Argument & int = default(1)
    # This is your cue
    # [metavar: CUE]
    q: Argument & int = 2
    a = lager(v, w)
    b = lager(v, q)
    return a, b


@tooled
def thing():
    arg: Argument & str
    return arg


@tooled
def thingy():
    arg: Argument
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
            "Argument": {"annotation": ABSENT, "doc": None},
            "tag": {"annotation": ABSENT, "doc": None},
            "int": {"annotation": ABSENT, "doc": None},
            "x": {"annotation": ABSENT, "doc": None},
            "y": {"annotation": ABSENT, "doc": None},
            "z": {
                "annotation": tag.Argument & tag.Bargument & int,
                "doc": None,
            },
        },
    }

    assert _catalogue(stout) == {
        **_catalogue(lager),
        stout: {
            "Argument": {"annotation": ABSENT, "doc": None},
            "int": {"annotation": ABSENT, "doc": None},
            "w": {
                "annotation": tag.Argument & int,
                "doc": "Double you,\nDouble me",
            },
            "q": {
                "annotation": tag.Argument & int,
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
        auto_cli(
            lager, ("a", "b"), argv="--z=:foo".split(), eval_env={"foo": "c"},
        )
        == "abc"
    )
    assert auto_cli(lager, (3, 2), argv="--z=:math:cos(0)".split(),) == 6
    assert auto_cli(stout, (3,), argv="--z=3".split()) == (7, 8)
    assert auto_cli(stout, (3,), argv="--z=3 --w=10".split()) == (16, 8)
    assert auto_cli(stout, (3,), tag=tag.Bargument, argv="--z=3".split()) == (
        7,
        8,
    )

    assert auto_cli(thingy, (), argv=["--arg", "1"]) == "1"
    assert auto_cli(thingy, (), argv=["--arg", "xyz"]) == "xyz"
    assert (
        auto_cli(thingy, (), eval_env={"foo": "bar"}, argv=["--arg", ":foo"],)
        == "bar"
    )
    assert auto_cli(
        thingy, (), eval_env={"foo": [1, 2, 3]}, argv=["--arg", ":foo"],
    ) == [1, 2, 3]

    assert (
        auto_cli(
            thing, (), eval_env={"foo": [1, 2, 3]}, argv=["--arg", ":foo"],
        )
        == ":foo"
    )


def test_cli_split():
    opts, thunk = auto_cli(stout, (3,), argv="--z=3".split(), return_split=True)
    opts = {k: v for k, v in vars(opts).items() if not k.startswith("#")}
    assert opts == {"z": 3}
    assert thunk() == (7, 8)
    assert thunk(opts={"z": 4}) == (8, 9)
    assert thunk(args=(4,)) == (8, 9)
    assert thunk({"z": 4}, (4,)) == (9, 10)


def test_no_env():
    with pytest.raises(Exception):
        auto_cli(
            lager, ("a", "b"), argv="--z=:foo".split(),
        )


def test_unknown_argument():
    with pytest.raises(SystemExit) as exc:
        auto_cli(stout, (3,), argv="--x=4".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        auto_cli(stout, (3,), tag=tag.Bargument, argv="--z=3 --w=10".split())
    assert exc.value.code == 2


def test_conflict():
    with pytest.raises(ConflictError):
        auto_cli(stout, (3,), argv="--z=3 --q=10".split())


def test_required_argument():
    with pytest.raises(SystemExit):
        auto_cli(lager, (3, 4), argv=[])


def test_missing_global():
    def wish():
        return love

    with pytest.raises(NameError):
        auto_cli(wish, (), argv=[])


def patriotism():
    # Whether to wave the flag or not
    # [aliases: -f --yay]
    flag: tag.Argument & bool = default(True)
    # [options: -n]
    times: tag.Argument & int = default(1)
    if flag:
        return "wave" * times
    else:
        return "don't wave"


def test_types():
    assert auto_cli(patriotism, (), argv=[]) == "wave"
    assert auto_cli(patriotism, (), argv="-f".split()) == "wave"
    assert auto_cli(patriotism, (), argv="--flag".split()) == "wave"
    assert auto_cli(patriotism, (), argv="--no-flag".split()) == "don't wave"
    assert (
        auto_cli(patriotism, (), argv="--flag -n 3".split(),) == "wavewavewave"
    )
    with pytest.raises(SystemExit) as exc:
        auto_cli(patriotism, (), argv="--flag=1".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        auto_cli(patriotism, (), argv="--flag --times=3".split())
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        auto_cli(patriotism, (), argv="-n ohno".split())
    assert exc.value.code == 2


def test_config_file(tmpdir):
    cfg1 = tmpdir.join("config1.json")
    cfg1.write(json.dumps({"z": 3, "w": 10}))

    assert auto_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)

    assert auto_cli(stout, (3,), argv=[f"@{cfg1.strpath}"], expand="@",) == (
        16,
        8,
    )

    assert auto_cli(stout, (3,), argv=[f"&{cfg1.strpath}"], expand="@&",) == (
        16,
        8,
    )

    cfg2 = tmpdir.join("config2.json")
    with pytest.raises(SystemExit) as exc:
        auto_cli(
            stout, (3,), argv=f"@{cfg2.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2

    cfg3 = tmpdir.join("config3.json")
    cfg3.write(json.dumps({"#include": cfg1.strpath, "w": 10}))
    assert auto_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg3),
    ) == (16, 8)

    assert auto_cli(stout, (3,), argv=[{"#include": cfg1.strpath}],) == (16, 8)


def test_config_toml(tmpdir):
    cfg1 = tmpdir.join("config1.toml")
    cfg1.write("z = 3\nw = 10\n")

    assert auto_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)


def test_config_cfg(tmpdir):
    cfg1 = tmpdir.join("config1.cfg")
    cfg1.write("[default]\nz = 3\nw = 10\n")

    assert auto_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)

    cfg2 = tmpdir.join("config2.cfg")
    cfg2.write("[ohno]\nz = 3\nw = 10\n")

    with pytest.raises(SystemExit) as exc:
        auto_cli(
            stout, (3,), argv=f"@{cfg2.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2


def test_config_yaml(tmpdir):
    cfg1 = tmpdir.join("config1.yaml")
    cfg1.write("z: 3\nw: 10\n")

    assert auto_cli(
        stout, (3,), argv=[], expand=ArgsExpander("@", default_file=cfg1),
    ) == (16, 8)


def test_config_unknown(tmpdir):
    cfg1 = tmpdir.join("config1.whatisthis")
    cfg1.write("z: 3\nw: 10\n")

    with pytest.raises(SystemExit) as exc:
        auto_cli(
            stout, (3,), argv=f"@{cfg1.strpath}".split(), expand="@",
        )
    assert exc.value.code == 2


def test_config_dict():
    assert auto_cli(stout, (3,), argv=[{"z": 3, "w": 10}],) == (16, 8)

    assert (
        auto_cli(patriotism, (), argv=[{"flag": True, "-n": 2}],) == "wavewave"
    )

    assert auto_cli(patriotism, (), argv=[{"flag": False}],) == "don't wave"


def test_bad_entry():
    with pytest.raises(TypeError):
        auto_cli([patriotism], (), argv="--flag")


def test_subcommands():
    assert (
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="thingy --arg xyz".split(),
        )
        == "xyz"
    )

    assert (
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="patriotism --flag".split(),
        )
        == "wave"
    )

    assert (
        auto_cli(
            {"thingy": thingy, "patri": {"otism": patriotism}},
            (),
            argv="patri otism --flag".split(),
        )
        == "wave"
    )

    assert (
        auto_cli(
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
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv="thingy --flag".split(),
        )
    assert exc.value.code == 2

    assert (
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=["patriotism", {"flag": True}],
        )
        == "wave"
    )

    # Test with no arguments
    with pytest.raises(SystemExit) as exc:
        assert (
            auto_cli({"thingy": thingy, "patriotism": patriotism}, (), argv="",)
            == "xyz"
        )
    assert exc.value.code == 1


def test_config_subcommands(tmpdir):
    cfg1 = tmpdir.join("config1.json")
    cfg1.write(json.dumps({"flag": True}))

    assert (
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"patriotism @{cfg1.strpath}".split(),
            expand="@",
        )
        == "wave"
    )

    cfg2 = tmpdir.join("config2.json")
    with pytest.raises(SystemExit) as exc:
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"patriotism @{cfg2.strpath}".split(),
            expand="@",
        )
    assert exc.value.code == 2

    cfg3 = tmpdir.join("config1.json")
    cfg3.write(json.dumps({"#command": "patriotism", "flag": True}))
    assert (
        auto_cli(
            {"thingy": thingy, "patriotism": patriotism},
            (),
            argv=f"@{cfg3.strpath}".split(),
            expand="@",
        )
        == "wave"
    )


@tooled
def groot():
    # Name to groot
    # [positional]
    name: tag.Argument
    return f"Grootings, {name}!"


@tooled
def translate():
    # Translation vector
    # [positional: 2]
    vector: tag.Argument & int
    return vector


@tooled
def reverso():
    # Things to reverse
    # [positional: *]
    things: tag.Argument
    things.reverse()
    return things


def test_positional():
    assert auto_cli(groot, (), argv=["Marcel"]) == "Grootings, Marcel!"

    with pytest.raises(SystemExit):
        auto_cli(groot, (), argv=[])

    assert auto_cli(translate, (), argv=["4", "7"]) == [4, 7]

    with pytest.raises(SystemExit):
        auto_cli(translate, (), argv=["4"])

    with pytest.raises(SystemExit):
        auto_cli(translate, (), argv=["4", "7", "8"])

    assert auto_cli(reverso, (), argv=list("goomba")) == list("abmoog")
    assert auto_cli(reverso, (), argv=[]) == []


@tooled
def multipos():
    # [positional]
    one: tag.Argument
    # [positional]
    two: tag.Argument
    return two, one


def test_multiple_positional():
    assert auto_cli(multipos, (), argv=["hello", "there"]) == ("there", "hello")


@tooled
def scattered_multipos():
    # [positional]
    three: tag.Argument
    return multipos()


@tooled
def scattered_multipos2():
    # [positional]
    two: tag.Argument
    return multipos()


def test_multiple_positional_bad():
    with pytest.raises(Exception):
        auto_cli(scattered_multipos, (), argv=["hello", "there"])
    with pytest.raises(Exception):
        auto_cli(scattered_multipos2, (), argv=["hello", "there"])


@tooled
def leftovers():
    # [positional]
    one: tag.Argument
    # [remainder]
    nomnom: tag.Argument
    return nomnom


def test_leftovers():
    assert auto_cli(leftovers, (), argv=["hello", "there"]) == ["there"]
    assert auto_cli(leftovers, (), argv="book".split()) == []
    assert auto_cli(leftovers, (), argv="my --pear --orange".split()) == [
        "--pear",
        "--orange",
    ]


@tooled
def ice_cream():
    # [nargs: 2]
    duo: tag.Argument & int

    # [nargs: *]
    tang: tag.Argument & int

    return duo, tang


def test_nargs():
    assert auto_cli(ice_cream, (), argv="--duo 1 2 --tang".split()) == (
        [1, 2],
        [],
    )
    assert auto_cli(ice_cream, (), argv="--tang --duo 1 2".split()) == (
        [1, 2],
        [],
    )
    assert auto_cli(ice_cream, (), argv="--duo 1 2 --tang 3 4 5".split()) == (
        [1, 2],
        [3, 4, 5],
    )


def test_setvars():
    with setvars(z=3, w=10):
        assert stout(3) == (16, 8)
