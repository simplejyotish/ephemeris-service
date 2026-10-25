import threading
from datetime import datetime, timezone

import pytest
import swisseph as swe

from ephemeris_service import swiss

JD_2000 = 2451545.0
JD_DELHI = 2448118.7708333335  # 1990-08-15 12:00 IST in UT
DELHI = (28.6139, 77.2090)


def _jd(y, m, d, h=0.0):
    return swe.julday(y, m, d, h)


def test_ayanamsha_krishnamurti_anchor():
    assert abs(swiss.ayanamsha_value(JD_2000, "krishnamurti") - 23.760240) < 1e-4


def test_positions_sun_2000_01_01():
    out = swiss.positions([JD_2000], ["Sun"], "lahiri")
    lon, speed = out[0]["Sun"]
    assert abs(lon - 256.51569718931427) < 1e-6
    assert abs(speed - 1.0193918758618497) < 1e-6


def test_positions_batch_shape():
    out = swiss.positions([JD_2000, JD_2000 + 1, JD_2000 + 2], ["Sun", "Moon"], "krishnamurti")
    assert len(out) == 3
    assert all(set(d) == {"Sun", "Moon"} for d in out)


def test_houses_placidus_delhi():
    cusps, asc, mc = swiss.houses(JD_DELHI, DELHI[0], DELHI[1], "krishnamurti")
    expected = [198.2770645300793, 227.50916878733992, 258.9649828808148, 292.0246446798525,
                324.3863636541136, 353.3751957280197, 18.27706453007929, 47.50916878733992,
                78.96498288081474, 112.02464467985243, 144.38636365411358, 173.3751957280197]
    assert len(cusps) == 12
    for a, b in zip(cusps, expected):
        assert abs(a - b) < 1e-9
    assert abs(asc - 198.2770645300793) < 1e-9
    assert abs(mc - 112.02464467985243) < 1e-9


def test_rise_set_delhi():
    jd0 = _jd(2024, 3, 20, 0.0)  # 00:00 UT; local day starts 05:30 UT the previous day
    rise = swiss.rise_set(jd0, DELHI[0], DELHI[1], "sunrise")
    sset = swiss.rise_set(jd0, DELHI[0], DELHI[1], "sunset")
    assert rise < sset
    # Delhi sunrise ~06:25 IST (00:55 UT), sunset ~18:30 IST (13:00 UT)
    assert jd0 <= rise < jd0 + 0.1
    assert jd0 + 0.4 < sset < jd0 + 0.7


def test_next_eclipse_known():
    # The first solar eclipse after 2026-01-01 is the 2026-02-17 annular one;
    # start after it to reach the 2026-08-12 total eclipse.
    jd0, kind0 = swiss.next_eclipse(_jd(2026, 1, 1), "solar")
    assert kind0 == "annular" and swe.revjul(jd0)[:3] == (2026, 2, 17)
    jd, kind = swiss.next_eclipse(_jd(2026, 3, 1), "solar")
    y, m, d, _ = swe.revjul(jd)
    assert kind == "total"
    assert (y, m, d) == (2026, 8, 12)


def test_next_eclipse_lunar_types():
    jd, kind = swiss.next_eclipse(_jd(2026, 1, 1), "lunar")
    assert kind in ("total", "partial", "penumbral")


def test_concurrent_ayanamsha_isolated():
    expected = {a: swiss.ayanamsha_value(JD_2000, a) for a in swiss.AYANAMSHAS}
    expected_pos = {a: swiss.positions([JD_2000], ["Moon"], a)[0]["Moon"][0] for a in swiss.AYANAMSHAS}
    errors = []

    def work(i):
        a = swiss.AYANAMSHAS[i % 2]
        for _ in range(20):
            if swiss.ayanamsha_value(JD_2000, a) != expected[a]:
                errors.append(("ayan", a))
            if swiss.positions([JD_2000], ["Moon"], a)[0]["Moon"][0] != expected_pos[a]:
                errors.append(("pos", a))

    ts = [threading.Thread(target=work, args=(i,)) for i in range(50)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors


def test_unknown_planet_and_ayanamsha_raise_valueerror():
    with pytest.raises(ValueError):
        swiss.positions([JD_2000], ["Pluto"], "lahiri")
    with pytest.raises(ValueError):
        swiss.positions([JD_2000], ["Sun"], "fagan")
    with pytest.raises(ValueError):
        swiss.ayanamsha_value(JD_2000, "fagan")
    with pytest.raises(ValueError):
        swiss.houses(JD_2000, 0.0, 0.0, "fagan")
