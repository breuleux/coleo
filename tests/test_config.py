import pytest

from coleo import ConfigFile, config


def test_format_json(tmpdir):
    cfg = tmpdir.join("config.json")
    cfg.write('{"apple": 15, "banana": 30}')
    f = ConfigFile(cfg.strpath)
    assert f.read() == {"apple": 15, "banana": 30}
    f.write({"coconut": 60})
    assert cfg.read() == '{"coconut": 60}'


def test_format_yaml(tmpdir):
    cfg = tmpdir.join("config.yaml")
    cfg.write("apple: 15\nbanana: 30")
    f = ConfigFile(cfg.strpath)
    assert f.read() == {"apple": 15, "banana": 30}
    f.write({"coconut": 60})
    assert cfg.read() == "coconut: 60\n"


def test_format_toml(tmpdir):
    cfg = tmpdir.join("config.toml")
    cfg.write("apple = 15\nbanana = 30")
    f = ConfigFile(cfg.strpath)
    assert f.read() == {"apple": 15, "banana": 30}
    f.write({"coconut": 60})
    assert cfg.read() == "coconut = 60\n"


def test_default(tmpdir):
    cfg = tmpdir.join("config.toml")
    f = ConfigFile(cfg.strpath)
    with pytest.raises(FileNotFoundError):
        f.read()
    assert f.read(123) == 123


def test_config(tmpdir):
    assert config("[1, 2, 3]") == [1, 2, 3]
    assert config('{"a": 1, "b": 2}') == {"a": 1, "b": 2}
    assert config('"hello!"') == "hello!"

    cfg = tmpdir.join("config.yaml")
    cfg.write("apple: 15\nbanana: 30")
    assert config(cfg.strpath) == {"apple": 15, "banana": 30}
