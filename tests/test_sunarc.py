"""Sun-arc maths: known values, an independent horizon-frame derivation, and the shared case table
(tests/sunarc_cases.json) that the C# port (atlas/tests) checks against too."""
import json
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generator"))
import sunarc  # noqa: E402

CASES = os.path.join(ROOT, "tests", "sunarc_cases.json")


def independent(lat, doy, hour):
    """Horizon frame from the equatorial vector (E, N, U); not the plan's atan2 form."""
    phi, dec = math.radians(lat), math.radians(sunarc.declination_deg(doy))
    H = math.radians(15 * (hour - 12))
    E = -math.cos(dec) * math.sin(H)
    N = math.sin(dec) * math.cos(phi) - math.cos(dec) * math.cos(H) * math.sin(phi)
    U = math.sin(dec) * math.sin(phi) + math.cos(dec) * math.cos(H) * math.cos(phi)
    return math.degrees(math.asin(U)), math.degrees(math.atan2(E, N)) % 360


def make_cases():
    out = []
    for lat in (0.0, 23.44, 31.0, 38.0, 52.0, -33.9):
        for doy in (1, 81, 172, 266, 355):
            rise, sset = sunarc.sunrise_sunset(lat, doy)
            for hour in (5.5, 8.0, 12.0, 15.25, 19.0):
                for off in (0.0, 30.0):
                    el, az = sunarc.sun_position(lat, doy, hour, off)
                    d = sunarc.sun_direction(lat, doy, hour, off)
                    out.append({'lat': lat, 'doy': doy, 'hour': hour, 'north_offset': off, 'elevation': round(el, 6),
                                'azimuth': round(az, 6), 'dir': [round(v, 6) for v in d],
                                'sunrise': None if rise is None else round(rise, 6),
                                'sunset': None if sset is None else round(sset, 6),
                                'daylight': round(sunarc.daylight(el), 6), 'dusk': round(sunarc.dusk(el), 6),
                                'window_level': round(sunarc.window_level(el, hour), 6)})
    return out


class SunArcTests(unittest.TestCase):
    def test_equinox_noon_elevation_is_90_minus_latitude(self):
        for lat in (0, 20, 38, 60):
            el, az = sunarc.sun_position(lat, 81, 12.0)
            self.assertAlmostEqual(el, 90 - lat, places=6)
            if lat > 0:
                self.assertAlmostEqual(az, 180.0, places=6)

    def test_summer_solstice_noon_at_38n(self):
        el, _ = sunarc.sun_position(38, 172, 12.0)
        self.assertAlmostEqual(el, 90 - 38 + sunarc.declination_deg(172), places=6)
        self.assertGreater(el, 75.0)

    def test_equator_equinox_sunrise_due_east(self):
        el, az = sunarc.sun_position(0, 81, 6.0)
        self.assertAlmostEqual(el, 0.0, places=6)
        self.assertAlmostEqual(az, 90.0, places=6)

    def test_matches_independent_derivation(self):
        for lat in (-40, 0, 12, 38, 55):
            for doy in range(1, 366, 17):
                for hour in (4.0, 7.5, 12.0, 13.7, 18.2, 22.0):
                    el, az = sunarc.sun_position(lat, doy, hour)
                    el2, az2 = independent(lat, doy, hour)
                    self.assertAlmostEqual(el, el2, places=6)
                    if abs(el) < 89.9:
                        self.assertAlmostEqual(math.cos(math.radians(az - az2)), 1.0, places=9)

    def test_north_offset_rotates_azimuth_only(self):
        el0, az0 = sunarc.sun_position(38, 172, 9.0)
        el1, az1 = sunarc.sun_position(38, 172, 9.0, 45.0)
        self.assertAlmostEqual(el0, el1)
        self.assertAlmostEqual((az1 - az0) % 360, 45.0, places=6)

    def test_direction_is_unit_and_points_up_at_noon(self):
        d = sunarc.sun_direction(38, 172, 12.0)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in d)), 1.0, places=9)
        self.assertLess(d[1], 0.0)          # northern summer noon sun is in the south (-Y)
        self.assertGreater(d[2], 0.9)

    def test_sunrise_sunset_symmetric_and_elevation_zero(self):
        rise, sset = sunarc.sunrise_sunset(38, 172)
        self.assertAlmostEqual(rise + sset, 24.0, places=6)
        self.assertAlmostEqual(sunarc.sun_position(38, 172, rise)[0], 0.0, places=4)
        self.assertEqual(sunarc.sunrise_sunset(80, 355), (None, None))      # polar night
        self.assertEqual(sunarc.sunrise_sunset(80, 172), (0.0, 24.0))       # midnight sun

    def test_daylight_and_night_level_ranges(self):
        self.assertEqual(sunarc.daylight(-20), 0.0)
        self.assertEqual(sunarc.daylight(30), 1.0)
        self.assertEqual(sunarc.night_level(30), 0.0)
        self.assertAlmostEqual(sunarc.night_level(-20), 0.9)
        self.assertLess(sunarc.night_level(-20), 0.99)       # 'Col' alpha 1.0 (not a window) must never light

    def test_window_level_goes_down_after_midnight(self):
        self.assertAlmostEqual(sunarc.window_level(-20, 21.0), 0.9)
        self.assertLess(sunarc.window_level(-20, 2.5), 0.4)
        self.assertEqual(sunarc.window_level(40, 12.0), 0.0)
        self.assertAlmostEqual(sunarc.lateness(19.0), 0.0)
        self.assertAlmostEqual(sunarc.lateness(3.0), 1.0)

    def test_shared_case_table_is_current(self):
        cases = make_cases()
        if os.environ.get("REGEN_SUN_CASES") or not os.path.exists(CASES):
            with open(CASES, "w") as f:
                json.dump(cases, f, indent=0)
        with open(CASES) as f:
            stored = json.load(f)
        self.assertEqual(len(stored), len(cases))
        for a, b in zip(stored, cases):
            self.assertAlmostEqual(a['elevation'], b['elevation'], places=5)
            self.assertAlmostEqual(a['azimuth'], b['azimuth'], places=5)


if __name__ == "__main__":
    unittest.main()
