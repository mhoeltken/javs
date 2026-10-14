# SPDX-License-Identifier: Apache-2.0
import pytest

from javs import core


@pytest.mark.parametrize(
    "name, expected",
    [
        ("surfshark-de-fra", "FRA"),
        ("surfshark-us-lax", "LAX"),
        ("de-ber", "BER"),
        ("surfshark-de-frankfurt", "FRA"),
        ("mullvad", "MUL"),
        ("Work VPN", "WOR"),
        ("ab", "AB"),
        ("surfshark-", "SUR"),
        ("--a--", "A"),
        ("-", "???"),
        ("", "???"),
        ("   ", "???"),
    ],
)
def test_abbreviate(name, expected):
    assert core.abbreviate(name) == expected


def test_sort_vpns_ignores_case():
    assert core.sort_vpns(["b-x", "A-y", "c-z"]) == ["A-y", "b-x", "c-z"]


def test_sort_vpns_returns_new_list():
    names = ["b", "a"]
    assert core.sort_vpns(names) == ["a", "b"]
    assert names == ["b", "a"]


def test_badge_off_by_default():
    assert core.badge_for() == core.Badge("OFF", core.OFF)


def test_badge_connected_shows_abbreviation():
    assert core.badge_for("surfshark-de-fra") == core.Badge("FRA", core.ON)


def test_badge_activating_shows_ellipsis():
    badge = core.badge_for("surfshark-de-fra", activating=True)
    assert badge == core.Badge("…", core.CONNECTING)


def test_badge_busy_without_active_shows_ellipsis():
    assert core.badge_for(busy=True) == core.Badge("…", core.CONNECTING)


def test_badge_busy_with_active_stays_on():
    assert core.badge_for("surfshark-de-fra", busy=True).state == core.ON


def test_badge_error_wins_over_everything():
    badge = core.badge_for("surfshark-de-fra", activating=True, error=True, busy=True)
    assert badge == core.Badge("ERR", core.ERROR)


def test_every_state_has_a_color():
    for state in (core.OFF, core.CONNECTING, core.ON, core.ERROR):
        r, g, b = core.BADGE_COLORS[state]
        assert all(0.0 <= channel <= 1.0 for channel in (r, g, b))
