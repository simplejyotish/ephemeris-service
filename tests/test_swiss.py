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
    # 280.3727895 and the 360001 speed are known-wrong legacy values kept on purpose as a
    # regression canary; the correct tropical Sun at J2000 is 280.36891967534336 (frame="tropical").
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


# Reference values captured from pyswisseph 2.10.3.2 with the legacy call pattern:
# set sid mode (tropical = SIDM_USER, t0=jd, ayan_t0=0), then
# houses_ex(jd, lat, lon, b"P", FLG_SIDEREAL) for asc/mc and houses_ex(.., code, FLG_SIDEREAL) for cusps.
JD_HS = 2447753.5
_HS_REF = {
    "krishnamurti": {
        "asc": 113.36899085647988, "mc": 19.424140034851774,
        "placidus": [113.36899085647988, 138.1701718800671, 167.06536567909265, 199.42414003485177, 232.5640937805691, 264.0967003810668, 293.36899085647985, 318.1701718800671, 347.0653656790926, 19.424140034851774, 52.5640937805691, 84.09670038106685],
        "koch": [113.36899085647988, 141.89934531113508, 170.89457170691654, 199.42414003485177, 235.41167070032972, 265.2638115561338, 293.36899085647985, 321.89934531113505, 350.8945717069165, 19.424140034851774, 55.41167070032969, 85.26381155613385],
        "sripati": [97.71151571954186, 127.71151571954186, 156.39656544566583, 185.0816151717898, 215.0816151717898, 246.3965654456658, 277.71151571954186, 307.71151571954186, 336.3965654456658, 5.081615171789792, 35.08161517178979, 66.39656544566583],
        "equal": [113.36899085647988, 143.36899085647988, 173.36899085647988, 203.36899085647988, 233.36899085647988, 263.36899085647985, 293.36899085647985, 323.36899085647985, 353.36899085647985, 23.368990856479876, 53.368990856479876, 83.36899085647988],
    },
    "lahiri": {
        "asc": 113.27213853026953, "mc": 19.32728770864142,
        "placidus": [113.27213853026953, 138.07331955385675, 166.9685133528823, 199.32728770864142, 232.46724145435874, 263.99984805485644, 293.2721385302695, 318.0733195538567, 346.96851335288227, 19.32728770864142, 52.46724145435875, 83.9998480548565],
        "koch": [113.27213853026953, 141.80249298492473, 170.79771938070618, 199.32728770864142, 235.31481837411937, 265.16695922992346, 293.2721385302695, 321.8024929849247, 350.79771938070616, 19.32728770864142, 55.314818374119334, 85.16695922992349],
        "sripati": [97.61466339333151, 127.61466339333151, 156.29971311945548, 184.98476284557944, 214.98476284557944, 246.29971311945545, 277.6146633933315, 307.6146633933315, 336.2997131194554, 4.984762845579439, 34.98476284557944, 66.29971311945548],
        "equal": [113.27213853026953, 143.27213853026953, 173.27213853026953, 203.27213853026953, 233.27213853026953, 263.2721385302695, 293.2721385302695, 323.2721385302695, 353.2721385302695, 23.272138530269523, 53.27213853026952, 83.27213853026953],
    },
    "tropical": {
        "asc": 136.98422935680756, "mc": 43.03937853517945,
        "placidus": [136.98422935680756, 161.78541038039478, 190.68060417942033, 223.03937853517945, 256.17933228089674, 287.7119388813945, 316.98422935680753, 341.78541038039475, 10.680604179420323, 43.03937853517945, 76.17933228089679, 107.71193888139453],
        "koch": [136.98422935680756, 165.51458381146276, 194.50981020724421, 223.03937853517945, 259.02690920065737, 288.8790500564615, 316.98422935680753, 345.5145838114627, 14.50981020724421, 43.03937853517945, 79.02690920065737, 108.87905005646152],
        "sripati": [121.32675421986954, 151.32675421986954, 180.0118039459935, 208.69685367211747, 238.69685367211747, 270.01180394599345, 301.32675421986954, 331.32675421986954, 0.011803945993472108, 28.69685367211747, 58.69685367211747, 90.0118039459935],
        "equal": [136.98422935680756, 166.98422935680756, 196.98422935680756, 226.98422935680756, 256.98422935680753, 286.98422935680753, 316.98422935680753, 346.98422935680753, 16.984229356807553, 46.98422935680755, 76.98422935680756, 106.98422935680756],
    },
}


@pytest.mark.parametrize("ayanamsha", ["krishnamurti", "lahiri", "tropical"])
@pytest.mark.parametrize("system", ["placidus", "koch", "sripati", "equal"])
def test_houses_system_matches_legacy(system, ayanamsha):
    ref = _HS_REF[ayanamsha]
    cusps, asc, mc = swiss.houses(JD_HS, DELHI[0], DELHI[1], ayanamsha, system)
    assert len(cusps) == 12
    for a, b in zip(cusps, ref[system]):
        assert abs(a - b) < 1e-9
    assert abs(asc - ref["asc"]) < 1e-9
    assert abs(mc - ref["mc"]) < 1e-9


@pytest.mark.parametrize("ayanamsha", ["krishnamurti", "lahiri", "tropical"])
def test_ascendant_independent_of_system(ayanamsha):
    results = [swiss.houses(JD_HS, DELHI[0], DELHI[1], ayanamsha, s)
               for s in ("placidus", "koch", "sripati", "equal")]
    assert len({(r[1], r[2]) for r in results}) == 1


def test_default_system_unchanged():
    assert swiss.houses(JD_HS, DELHI[0], DELHI[1], "lahiri") == \
        swiss.houses(JD_HS, DELHI[0], DELHI[1], "lahiri", "placidus")


def test_houses_unknown_system_raises():
    with pytest.raises(ValueError):
        swiss.houses(JD_HS, DELHI[0], DELHI[1], "lahiri", "bogus")


_HS66 = {
    "asc": 129.28678141763857, "mc": 19.32728770864142,
    "placidus": [129.28678141763857, 143.4893129496913, 164.98887463648867, 199.32728770864142, 251.62426906207182, 285.54269543175803, 309.2867814176385, 323.4893129496913, 344.9888746364886, 19.32728770864142, 71.62426906207179, 105.54269543175803],
    "koch": [129.28678141763857, 152.80571443472434, 176.4869887810646, 199.32728770864142, 265.06218822011135, 286.78477432689994, 309.2867814176385, 332.80571443472434, 356.4869887810646, 19.32728770864142, 85.06218822011138, 106.78477432689996],
    "sripati": [110.96019913280571, 140.9601991328057, 164.30703456313998, 187.65386999347427, 217.65386999347427, 254.30703456313998, 290.96019913280566, 320.96019913280566, 344.30703456313995, 7.653869993474281, 37.65386999347428, 74.30703456314001],
    "equal": [129.28678141763857, 159.28678141763857, 189.28678141763857, 219.28678141763854, 249.28678141763854, 279.2867814176385, 309.2867814176385, 339.2867814176385, 9.28678141763853, 39.28678141763853, 69.28678141763854, 99.28678141763854],
}


@pytest.mark.parametrize("system", ["placidus", "koch", "sripati", "equal"])
def test_houses_high_latitude_66_matches_legacy(system):
    # 66 deg N is the highest whole degree where all four systems still work at this JD.
    cusps, asc, mc = swiss.houses(JD_HS, 66.0, DELHI[1], "lahiri", system)
    for a, b in zip(cusps, _HS66[system]):
        assert abs(a - b) < 1e-9
    assert abs(asc - _HS66["asc"]) < 1e-9 and abs(mc - _HS66["mc"]) < 1e-9


@pytest.mark.parametrize("system", ["placidus", "koch", "sripati", "equal"])
def test_houses_polar_latitude_raises(system):
    with pytest.raises(swe.Error):
        swiss.houses(JD_HS, 80.0, DELHI[1], "lahiri", system)
