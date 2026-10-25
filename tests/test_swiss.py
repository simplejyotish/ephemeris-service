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
        swiss.positions([JD_2000], ["Chiron"], "lahiri")
    with pytest.raises(ValueError):
        swiss.positions([JD_2000], ["Sun"], "bogus")
    with pytest.raises(ValueError):
        swiss.ayanamsha_value(JD_2000, "bogus")
    with pytest.raises(ValueError):
        swiss.houses(JD_2000, 0.0, 0.0, "bogus")


# --- 0.2 additions. Reference numbers captured with the legacy swisseph call
# patterns (pyswisseph 2.10.3.2) in a throwaway script outside both repos.
JD_2023 = 2460000.5
TOL = 1e-9

# (jd, ayanamsha) -> (ayanamsha value, Sun lon, Sun speed, Moon lon, Moon speed)
NEW_AYAN = {
    ("pushya", JD_2000): (22.72709161468802, 257.6456979283351, 1.0193433626754926,
                          200.60055369140122, 12.021094363558213),
    ("pushya", JD_2023): (23.050818772618186, 313.0587071121851, 1.0063401320431022,
                          15.599504095445212, 13.226353907315584),
    ("raman", JD_2000): (22.4107910403265, 257.9619985026966, 1.0193918758618497,
                         200.91685426576274, 12.021142876744571),
    ("raman", JD_2023): (22.73418565029624, 313.375340234507, 1.0062940491118533,
                         15.91613721776716, 13.226307824384335),
    ("fagan", JD_2000): (24.740299994434963, 255.63248954858815, 1.0193918758618497,
                         198.5873453116543, 12.021142876744566),
    ("fagan", JD_2023): (25.063694581527557, 311.04583130327575, 1.0062940490550099,
                         13.586628286535838, 13.22630782432749),
}

# lahiri sidereal (lon, speed, lat) for Uranus, Neptune, Pluto
OUTER = {
    JD_2000: {"Uranus": (290.9560006797972, 0.05030338209110133, -0.6583328776085626),
              "Neptune": (279.339758737621, 0.035529892997351674, 0.23499118274713457),
              "Pluto": (227.60148636071187, 0.03511303107945256, 10.855202461622458)},
    JD_2023: {"Uranus": (21.23396929292088, 0.027892243789098218, -0.33338653073393365),
              "Neptune": (330.22732354521355, 0.036376345723564234, -1.1686517606745328),
              "Pluto": (275.20916676715996, 0.027427502268644478, -2.3397854301290786)},
}


def test_outer_planets_sidereal_match_legacy():
    for jd, expected in OUTER.items():
        row = swiss.positions_ex([jd], list(expected), "lahiri")[0]
        for name, (lon, spd, lat) in expected.items():
            assert abs(row[name].longitude - lon) < TOL
            assert abs(row[name].speed - spd) < TOL
            assert abs(row[name].latitude - lat) < TOL


def test_new_ayanamshas_match_legacy():
    for (name, jd), (ayan, slon, sspd, mlon, mspd) in NEW_AYAN.items():
        assert abs(swiss.ayanamsha_value(jd, name) - ayan) < TOL
        row = swiss.positions([jd], ["Sun", "Moon"], name)[0]
        assert abs(row["Sun"][0] - slon) < TOL and abs(row["Sun"][1] - sspd) < TOL
        assert abs(row["Moon"][0] - mlon) < TOL and abs(row["Moon"][1] - mspd) < TOL


def test_tropical_ayanamsha_is_zero_at_jd_and_matches_legacy():
    # legacy: swe.set_sid_mode(SIDM_USER, jd, 0.0) then get_ayanamsa_ut(jd)
    assert abs(swiss.ayanamsha_value(JD_2000, "tropical") - 2.825368028425146e-08) < TOL
    assert abs(swiss.ayanamsha_value(JD_2023, "tropical") - 3.062086761929095e-08) < TOL
    row = swiss.positions([JD_2000], ["Sun", "Moon"], "tropical")[0]
    # legacy output verbatim, including its odd (360000-offset) speed
    assert abs(row["Sun"][0] - 280.37278951476947) < TOL
    assert abs(row["Sun"][1] - 360001.0193918759) < 1e-6
    assert abs(row["Moon"][0] - 223.32764527783561) < TOL


def test_tropical_equals_no_sidereal_flag():
    # legacy cheshta._true: calc_ut(jd, MARS, FLG_SWIEPH|FLG_SPEED) -> lon, lat, speed
    ref = {JD_2000: (327.9633133185202, -1.067782948274341, 0.7756727772750058),
           JD_2023: (77.555287172016, 2.4541807656389314, 0.37868273962209825)}
    for jd, (lon, lat, spd) in ref.items():
        # ayanamsha must be ignored outside the sidereal frame (even an invalid one)
        p = swiss.positions_ex([jd], ["Mars"], "ignored", "tropical")[0]["Mars"]
        assert abs(p.longitude - lon) < TOL
        assert abs(p.latitude - lat) < TOL
        assert abs(p.speed - spd) < TOL
        raw, _ = swe.calc_ut(jd, swe.MARS, swe.FLG_MOSEPH | swe.FLG_SPEED)
        assert (p.longitude, p.latitude, p.speed) == (raw[0], raw[1], raw[3])


def test_equatorial_declination_matches_legacy():
    # legacy cheshta: calc_ut(jd, SUN, FLG_SWIEPH|FLG_EQUATORIAL) -> (RA, dec)
    ref = {JD_2000: (281.27838624804394, -23.03242536797977),
           JD_2023: (337.881148541722, -9.271167619674333)}
    for jd, (ra, dec) in ref.items():
        p = swiss.positions_ex([jd], ["Sun"], "lahiri", "equatorial")[0]["Sun"]
        assert abs(p.longitude - ra) < TOL
        assert abs(p.latitude - dec) < TOL


def test_latitude_returned():
    # legacy shadbala.wars: swe.calc_ut(jd, SATURN)[0][1] (tropical latitude)
    ref = {JD_2000: -2.444822554620036, JD_2023: -1.2688798312980558}
    for jd, lat in ref.items():
        p = swiss.positions_ex([jd], ["Saturn"], "lahiri", "tropical")[0]["Saturn"]
        assert abs(p.latitude - lat) < TOL
        assert len(swiss.positions_ex([jd], ["Saturn"], "lahiri")[0]["Saturn"]) == 3


def test_unknown_frame_raises():
    with pytest.raises(ValueError):
        swiss.positions_ex([JD_2000], ["Sun"], "lahiri", "galactic")


def test_tropical_and_lahiri_do_not_interfere():
    expected = swiss.positions([JD_2023], ["Sun", "Moon"], "lahiri")
    errors = []

    def lahiri():
        for _ in range(60):
            if swiss.positions([JD_2023], ["Sun", "Moon"], "lahiri") != expected:
                errors.append("lahiri")

    def tropical():
        for _ in range(60):
            v = swiss.ayanamsha_value(JD_2023, "tropical")
            if abs(v - 3.062086761929095e-08) > TOL:
                errors.append(("tropical", v))

    ts = [threading.Thread(target=f) for f in (lahiri, tropical, lahiri, tropical)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
