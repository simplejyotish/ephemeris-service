"""Thin wrapper over pyswisseph. Pure astronomy; no interpretation."""
from __future__ import annotations

import os
import threading
from typing import Literal, Sequence

import swisseph as swe

PLANETS: tuple[str, ...] = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                            "Saturn", "MeanNode", "TrueNode")
AYANAMSHAS: tuple[str, ...] = ("krishnamurti", "lahiri")

_PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "MeanNode": swe.MEAN_NODE, "TrueNode": swe.TRUE_NODE,
}
_SID_MODES = {"krishnamurti": swe.SIDM_KRISHNAMURTI, "lahiri": swe.SIDM_LAHIRI}

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


def _sid_mode(ayanamsha: str) -> int:
    try:
        return _SID_MODES[ayanamsha]
    except KeyError:
        raise ValueError(f"unknown ayanamsha: {ayanamsha!r}") from None


def _planet_id(name: str) -> int:
    try:
        return _PLANET_IDS[name]
    except KeyError:
        raise ValueError(f"unknown planet: {name!r}") from None


def positions(jds: Sequence[float], planets: Sequence[str],
              ayanamsha: str) -> list[dict[str, tuple[float, float]]]:
    mode = _sid_mode(ayanamsha)
    ids = [(p, _planet_id(p)) for p in planets]
    out: list[dict[str, tuple[float, float]]] = []
    with _LOCK:
        swe.set_sid_mode(mode)
        for jd in jds:
            row = {}
            for name, pid in ids:
                values, _ = swe.calc_ut(jd, pid, _BASE_FLAGS)
                row[name] = (values[0], values[3])
            out.append(row)
    return out


def ayanamsha_value(jd: float, ayanamsha: str) -> float:
    mode = _sid_mode(ayanamsha)
    with _LOCK:
        swe.set_sid_mode(mode)
        return swe.get_ayanamsa_ut(jd)


def houses(jd: float, lat: float, lon: float,
           ayanamsha: str) -> tuple[list[float], float, float]:
    mode = _sid_mode(ayanamsha)
    with _LOCK:
        swe.set_sid_mode(mode)
        cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
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
