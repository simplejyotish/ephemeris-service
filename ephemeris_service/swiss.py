"""Thin wrapper over pyswisseph. Pure astronomy; no interpretation."""
from __future__ import annotations

import os
import threading
from typing import Literal, NamedTuple, Sequence

import swisseph as swe

PLANETS: tuple[str, ...] = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                            "Saturn", "MeanNode", "TrueNode", "Uranus", "Neptune", "Pluto")
AYANAMSHAS: tuple[str, ...] = ("krishnamurti", "lahiri", "pushya", "raman", "fagan", "tropical")
Frame = Literal["sidereal", "tropical", "equatorial"]

_PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "MeanNode": swe.MEAN_NODE, "TrueNode": swe.TRUE_NODE,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
}
_SID_MODES = {
    "krishnamurti": swe.SIDM_KRISHNAMURTI, "lahiri": swe.SIDM_LAHIRI,
    "pushya": swe.SIDM_TRUE_PUSHYA, "raman": swe.SIDM_RAMAN,
    "fagan": swe.SIDM_FAGAN_BRADLEY,
}
# "tropical" is a user-defined ayanamsha of exactly 0 pinned at the JD being computed
# (SIDM_USER, t0=jd, ayan_t0=0). This reproduces the legacy app exactly, quirks included:
# in sidereal mode the returned speed carries a 360000 deg/day offset (about 360001 for
# the Sun) and the longitude is about 0.0039 deg off true tropical at J2000 (no nutation).
# For genuine tropical longitudes and speeds use frame="tropical", not this ayanamsha.
_TROPICAL = "tropical"

_BASE_FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
_EPHE_MODE = "moshier"

# swe.set_sid_mode is process-global state; hold this across set-then-calculate.
_LOCK = threading.Lock()


def configure_ephe_path(path: str | None) -> None:
    """Point Swiss Ephemeris at data files. If given and present, use SWIEPH."""
    global _BASE_FLAGS, _EPHE_MODE
    if path and os.path.isdir(path):
        swe.set_ephe_path(path)
        _BASE_FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        _EPHE_MODE = "swieph"


def ephe_mode() -> str:
    return _EPHE_MODE


def swe_version() -> str:
    return swe.version


def _check_ayanamsha(ayanamsha: str) -> None:
    if ayanamsha != _TROPICAL and ayanamsha not in _SID_MODES:
        raise ValueError(f"unknown ayanamsha: {ayanamsha!r}")


def _apply_sid_mode(ayanamsha: str, jd: float) -> None:
    """Set the process-global sidereal mode. Caller must hold _LOCK."""
    if ayanamsha == _TROPICAL:
        swe.set_sid_mode(swe.SIDM_USER, jd, 0.0)
    else:
        swe.set_sid_mode(_SID_MODES[ayanamsha])


def _planet_id(name: str) -> int:
    try:
        return _PLANET_IDS[name]
    except KeyError:
        raise ValueError(f"unknown planet: {name!r}") from None


class Position(NamedTuple):
    longitude: float  # right ascension in the equatorial frame
    latitude: float   # declination in the equatorial frame
    speed: float


def positions_ex(jds: Sequence[float], planets: Sequence[str], ayanamsha: str,
                 frame: Frame = "sidereal") -> list[dict[str, Position]]:
    ids = [(p, _planet_id(p)) for p in planets]
    if frame == "sidereal":
        _check_ayanamsha(ayanamsha)
        flags = _BASE_FLAGS
    elif frame == "tropical":
        flags = _BASE_FLAGS & ~swe.FLG_SIDEREAL
    elif frame == "equatorial":
        flags = (_BASE_FLAGS & ~swe.FLG_SIDEREAL) | swe.FLG_EQUATORIAL
    else:
        raise ValueError(f"unknown frame: {frame!r}")
    out: list[dict[str, Position]] = []
    with _LOCK:
        if frame == "sidereal" and ayanamsha != _TROPICAL:
            _apply_sid_mode(ayanamsha, 0.0)
        for jd in jds:
            if frame == "sidereal" and ayanamsha == _TROPICAL:
                _apply_sid_mode(ayanamsha, jd)
            row = {}
            for name, pid in ids:
                values, _ = swe.calc_ut(jd, pid, flags)
                row[name] = Position(values[0], values[1], values[3])
            out.append(row)
    return out


def positions(jds: Sequence[float], planets: Sequence[str],
              ayanamsha: str) -> list[dict[str, tuple[float, float]]]:
    return [{n: (p.longitude, p.speed) for n, p in row.items()}
            for row in positions_ex(jds, planets, ayanamsha, "sidereal")]


def ayanamsha_value(jd: float, ayanamsha: str) -> float:
    _check_ayanamsha(ayanamsha)
    with _LOCK:
        _apply_sid_mode(ayanamsha, jd)
        return swe.get_ayanamsa_ut(jd)


HouseSystem = Literal["placidus", "koch", "sripati", "equal"]
_HOUSE_CODES = {"placidus": b"P", "koch": b"K", "sripati": b"S", "equal": b"E"}


def houses(jd: float, lat: float, lon: float, ayanamsha: str,
           system: HouseSystem = "placidus") -> tuple[list[float], float, float]:
    """(12 cusps in the requested system, ascendant, midheaven).

    Ascendant and midheaven always come from the Placidus call, as in the legacy app.
    """
    _check_ayanamsha(ayanamsha)
    try:
        code = _HOUSE_CODES[system]
    except KeyError:
        raise ValueError(f"unknown house system: {system!r}") from None
    with _LOCK:
        _apply_sid_mode(ayanamsha, jd)
        cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
        if code != b"P":
            cusps, _ = swe.houses_ex(jd, lat, lon, code, swe.FLG_SIDEREAL)
    return list(cusps), ascmc[0], ascmc[1]


def rise_set(jd_start: float, lat: float, lon: float,
             event: Literal["sunrise", "sunset"]) -> float:
    if event == "sunrise":
        rsmi = swe.CALC_RISE
    elif event == "sunset":
        rsmi = swe.CALC_SET
    else:
        raise ValueError(f"unknown event: {event!r}")
    # swe.Error from swisseph propagates unchanged.
    _, tret = swe.rise_trans(jd_start, swe.SUN, rsmi, (lon, lat, 0.0), 0.0, 0.0,
                             swe.FLG_MOSEPH)
    return tret[0]


def _solar_type(rflags: int) -> str:
    if rflags & swe.ECL_TOTAL:
        return "total"
    if rflags & swe.ECL_ANNULAR_TOTAL:
        return "hybrid"
    if rflags & swe.ECL_ANNULAR:
        return "annular"
    return "partial"


def _lunar_type(rflags: int) -> str:
    if rflags & swe.ECL_TOTAL:
        return "total"
    if rflags & swe.ECL_PARTIAL:
        return "partial"
    return "penumbral"


def next_eclipse(jd_start: float, kind: Literal["solar", "lunar"]) -> tuple[float, str]:
    if kind == "solar":
        rflags, tret = swe.sol_eclipse_when_glob(jd_start, swe.FLG_MOSEPH, 0, False)
        return tret[0], _solar_type(rflags)
    if kind == "lunar":
        rflags, tret = swe.lun_eclipse_when(jd_start, swe.FLG_MOSEPH, 0, False)
        return tret[0], _lunar_type(rflags)
    raise ValueError(f"unknown eclipse kind: {kind!r}")
