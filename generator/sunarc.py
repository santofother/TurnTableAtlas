"""Shared sun-arc maths. The C# port is atlas/src/Core/SunArc.cs; both are tested against tests/sunarc_cases.json.

Inputs: latitude phi (deg, +north), day of year N (1..365), solar hour h (0..24), north offset (deg).
    declination  d = 23.44 * sin(360/365 * (N - 81))
    hour angle   H = 15 * (h - 12)
    elevation    = asin(sin phi sin d + cos phi cos d cos H)
    azimuth      = atan2(sin H, cos H sin phi - tan d cos phi) + 180   (from north, clockwise) + north offset
World frame (generator/Blender): +X east, +Y north, +Z up. Pure Python, no bpy, so tests run anywhere.
"""
import math


def declination_deg(day_of_year):
    return 23.44 * math.sin(math.radians(360.0 / 365.0 * (day_of_year - 81)))


def sun_position(lat_deg, day_of_year, hour, north_offset_deg=0.0):
    """Return (elevation_deg, azimuth_deg) with azimuth from north, clockwise, in [0, 360)."""
    phi = math.radians(lat_deg)
    dec = math.radians(declination_deg(day_of_year))
    H = math.radians(15.0 * (hour - 12.0))
    s = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H)
    el = math.degrees(math.asin(max(-1.0, min(1.0, s))))
    az = math.degrees(math.atan2(math.sin(H), math.cos(H) * math.sin(phi) - math.tan(dec) * math.cos(phi))) + 180.0
    az = (az + north_offset_deg) % 360.0
    return el, az


def sun_direction(lat_deg, day_of_year, hour, north_offset_deg=0.0):
    """Unit vector from the city toward the sun, in the world frame (+X east, +Y north, +Z up)."""
    el, az = sun_position(lat_deg, day_of_year, hour, north_offset_deg)
    e, a = math.radians(el), math.radians(az)
    return (math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e))


def sunrise_sunset(lat_deg, day_of_year):
    """Solar hours of sunrise and sunset (geometric, elevation 0). (None, None) in polar night; (0, 24) in midnight sun."""
    phi = math.radians(lat_deg)
    dec = math.radians(declination_deg(day_of_year))
    c = -math.tan(phi) * math.tan(dec)
    if c >= 1.0:
        return None, None
    if c <= -1.0:
        return 0.0, 24.0
    h0 = math.degrees(math.acos(c)) / 15.0
    return 12.0 - h0, 12.0 + h0


def daylight(elevation_deg):
    """0 at night .. 1 in full day, smooth through civil twilight (-6 deg .. +8 deg). Shared by both outputs."""
    t = (elevation_deg + 6.0) / 14.0
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def night_level(elevation_deg):
    """Window light-up threshold (0 = none lit .. 0.9 = 90 % lit). Rises through dusk (+4 .. -8 deg)."""
    t = (4.0 - elevation_deg) / 12.0
    t = max(0.0, min(1.0, t))
    return 0.9 * t * t * (3.0 - 2.0 * t)


def lateness(hour):
    """0 in the evening .. 1 in the small hours (about 01:00-04:00): most households have gone to bed."""
    h = (hour - 12.0) % 24.0                   # noon = 0, midnight = 12
    a = max(0.0, min(1.0, (h - 10.5) / 2.5))
    b = max(0.0, min(1.0, (h - 16.0) / 1.5))
    return (a * a * (3 - 2 * a)) * (1.0 - b * b * (3 - 2 * b))


def window_level(elevation_deg, hour):
    """NightLevel for the window shader: lights come on through dusk, most go out after midnight."""
    return night_level(elevation_deg) * (1.0 - 0.6 * lateness(hour))


def dusk(elevation_deg):
    """Golden-hour / twilight weight, peaking with the sun just above the horizon."""
    return math.exp(-((elevation_deg - 2.0) / 7.0) ** 2)
