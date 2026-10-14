# SPDX-License-Identifier: Apache-2.0
import json

import pytest

from javs import config


def write(path, text):
    path.write_text(text, encoding="utf-8")


def test_levels_and_default():
    assert config.POLL_INTERVALS_MS == {"tight": 2000, "medium": 5000, "relaxed": 15000}
    assert config.DEFAULT_POLL == "medium"
    assert list(config.POLL_INTERVALS_MS) == ["tight", "medium", "relaxed"]


def test_default_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.default_config_path() == str(tmp_path / "javs" / "config.json")


def test_default_config_path_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config.default_config_path() == str(tmp_path / ".config" / "javs" / "config.json")


def test_default_config_path_ignores_empty_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config.default_config_path() == str(tmp_path / ".config" / "javs" / "config.json")


def test_load_poll_missing_file(tmp_path):
    assert config.load_poll(str(tmp_path / "nope.json")) == "medium"


@pytest.mark.parametrize("level", ["tight", "medium", "relaxed"])
def test_load_poll_valid(tmp_path, level):
    path = tmp_path / "c.json"
    write(path, json.dumps({"poll": level}))
    assert config.load_poll(str(path)) == level


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "",
        "[]",
        "null",
        '"tight"',
        "{}",
        '{"poll": 5}',
        '{"poll": []}',
        '{"poll": null}',
        '{"poll": "bogus"}',
    ],
)
def test_load_poll_falls_back_to_default_and_leaves_file_alone(tmp_path, content):
    path = tmp_path / "c.json"
    write(path, content)
    assert config.load_poll(str(path)) == "medium"
    assert path.read_text(encoding="utf-8") == content


def test_save_poll_creates_directories_and_roundtrips(tmp_path):
    path = tmp_path / "sub" / "dir" / "config.json"
    config.save_poll(str(path), "tight")
    assert config.load_poll(str(path)) == "tight"
    assert json.loads(path.read_text(encoding="utf-8")) == {"poll": "tight"}


def test_save_poll_keeps_other_keys(tmp_path):
    path = tmp_path / "c.json"
    write(path, json.dumps({"poll": "tight", "other": 1}))
    config.save_poll(str(path), "relaxed")
    assert json.loads(path.read_text(encoding="utf-8")) == {"poll": "relaxed", "other": 1}


def test_save_poll_replaces_corrupt_file(tmp_path):
    path = tmp_path / "c.json"
    write(path, "{broken")
    config.save_poll(str(path), "tight")
    assert json.loads(path.read_text(encoding="utf-8")) == {"poll": "tight"}


def test_save_poll_rejects_unknown_level(tmp_path):
    path = tmp_path / "c.json"
    with pytest.raises(ValueError):
        config.save_poll(str(path), "turbo")
    assert not path.exists()


def test_save_poll_leaves_no_temp_files(tmp_path):
    path = tmp_path / "c.json"
    config.save_poll(str(path), "tight")
    assert [p.name for p in tmp_path.iterdir()] == ["c.json"]
