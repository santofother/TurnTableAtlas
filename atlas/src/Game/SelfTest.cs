// --selftest: drives the app like the plan's Phase 4 acceptance check and prints [Selftest] PASS/FAIL lines.
// Open a city, scrub dawn to night, change the latitude and see the arc change, fly to a landmark, press
// Chariot Race (run 25x faster), watch city and world shipping, then reopen the city.
using System;
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public static class SelfTest
    {
        static int _step;
        static string _city;
        static Vector3 _expectCam;
        static (MeshInstance3D Node, Vector3 Position) _localBoat;
        static Vector3[] _mapBoats;
        static int _fails;
        static string _event, _venueType, _landmark;
        static readonly string[] Preferred = { "chariot_race", "gladiator_games", "theatre_play" };

        static T Find<T>(Node n) where T : Node
        {
            foreach (var c in n.GetChildren())
            {
                if (c is T t) return t;
                var r = Find<T>(c);
                if (r != null) return r;
            }
            return null;
        }

        static void Check(bool ok, string what)
        {
            GD.Print(ok ? $"[Selftest] ok   {what}" : $"[Selftest] SELFTEST FAIL {what}");
            if (!ok) _fails++;
        }

        public static void Tick(AtlasRoot root, double t)
        {
            var v = root.City;
            switch (_step)
            {
                case 0 when t > 0.5:
                    Check(v != null && v.City.MeshCount > 20, $"city open with {v?.City.MeshCount} meshes, {v?.City.Triangles / 1000}k tris");
                    _city = v?.M.Id;
                    var placement = v?.M.Boats.FirstOrDefault(s => s.Voyage != null);
                    if (placement != null)
                    {
                        var boat = v.City.ByName[placement.Object];
                        _localBoat = (boat, boat.Position);
                    }
                    _step++; break;
                case 1 when t > 0.6:
                {
                    var tod = v.Tod;
                    tod.Hour = 6; tod.Apply(); double e6 = tod.Elevation; double w6 = tod.WindowLevel;
                    tod.Hour = 12; tod.Apply(); double e12 = tod.Elevation;
                    tod.Hour = 22.5; tod.Apply(); double w22 = tod.WindowLevel;
                    Check(e12 > e6 + 15 && w22 > 0.5 && w6 < w22, $"scrub dawn→noon→night: elevation {e6:0}°→{e12:0}°, windows lit {w22:0.00} at 22:30");
                    tod.Hour = 12; tod.Latitude = 60; tod.DayOfYear = 355; tod.Apply(); double hi = tod.Elevation;
                    tod.Latitude = 10; tod.Apply(); double lo = tod.Elevation;
                    var arc60 = SunArc.Arc(60, 355, 0).Count; var arc10 = SunArc.Arc(10, 355, 0).Count;
                    v.Gizmo.Rebuild(tod);
                    Check(lo > hi + 40 && arc10 > arc60, $"latitude changes the arc: noon {hi:0}° at 60°N vs {lo:0}° at 10°N in winter; arc points {arc60} vs {arc10}");
                    tod.ResetSun(v.M.Sun); tod.Hour = 15; tod.Apply();
                    var lm = v.M.Landmarks.FirstOrDefault(l => l.Id != "overview") ?? v.M.Landmarks[0];
                    _landmark = lm.Id;
                    _expectCam = Geo.V(lm.Camera.Target) + Geo.Orbit((float)lm.Camera.Yaw, (float)lm.Camera.Pitch, (float)lm.Camera.Dist);
                    v.Jump(_landmark);
                    _step++; break;
                }
                case 2 when t > 3.2:
                {
                    float d = v.Rig.Cam.GlobalPosition.DistanceTo(_expectCam);
                    Check(d < 6f, $"flew to the {_landmark} landmark (camera {d:0.0} m from preset)");
                    _event = Preferred.FirstOrDefault(e => v.Events.Available.Any(a => a.Id == e)) ?? v.Events.Available.FirstOrDefault()?.Id;
                    _venueType = _event switch { "chariot_race" => "circus", "gladiator_games" => "arena", "theatre_play" => "theatre", _ => null };
                    v.Events.TimeScale = 25;
                    if (_event != null) v.Events.Trigger(_event);
                    Check(_event != null && v.Events.Running != null, $"event '{_event}' triggered ({v.Events.Available.Count} available here)");
                    _step++; break;
                }
                case 3 when t > 6.2:
                {
                    var ven = _venueType != null ? v.M.VenueOfType(_venueType) : null;
                    if (ven != null)
                    {
                        double fill = v.Life.Seats[ven.Id].Fill;
                        Check(fill > 0.85, $"{ven.Label} filled to {fill:0.00}");
                    }
                    bool showOn = _event switch { "chariot_race" => v.Events.Race != null && v.Events.Race.Time > 1, "gladiator_games" => v.Events.Arena != null,
                                                  "theatre_play" => v.Events.Play != null, _ => v.Events.Running != null };
                    Check(showOn, $"show running: {v.Events.Status}");
                    Check(v.Life.Crowd.W.Count(w => w.Active) > 100, $"{v.Life.Crowd.W.Count(w => w.Active)} people walking");
                    Check(v.Life.Traffic.Ships.Count(s => s.Visible) > 2, $"{v.Life.Traffic.Ships.Count(s => s.Visible)} ships under way");
                    if (_localBoat.Node != null)
                        Check(_localBoat.Node.Position.DistanceTo(_localBoat.Position) > 0.5f,
                              "a placed rowboat travels through the harbour");
                    var panel = Find<WeatherPanel>(root);
                    panel?.KindButton(WeatherKind.Rain).EmitSignal(BaseButton.SignalName.Pressed);
                    Check(panel != null && root.Weather.Kind == WeatherKind.Rain && root.Weather.Target.Rain > 0.5,
                          $"weather panel in the city: Rain chosen ({root.Weather.Target.Rain:0.00} rain)");
                    root.ShowMap();
                    _step++; break;
                }
                case 4 when t > 6.8:
                {
                    var map = root.Map;
                    Check(map != null && root.City == null, "back to the world map");
                    Check(map.Pins.Count == root.Cities.Count && map.Weather?.Clouds != null && map.Rig.Cam.Current,
                          $"Known World: {map.Pins.Count} pins, clouds, orbit camera");
                    Check(map.WeatherControls != null && map.WeatherControls.W == root.Weather && root.Weather.Kind == WeatherKind.Rain,
                          $"the map shares the city's weather ({root.Weather.Kind}, cloud {root.Weather.Current.Coverage:0.00})");
                    Check(map.Table != null && map.Table.CandleCount >= 6 && map.Tod.Room != null,   // FIX(W1)
                          $"map table: frame, props, {map.Table?.CandleCount} candles, dark room");
                    map.WeatherControls.KindButton(WeatherKind.Fair).EmitSignal(BaseButton.SignalName.Pressed);
                    Check(map.GetNodeOrNull("Geography") == null && map.GetNodeOrNull("MapTable/GeographyFrame") == null,
                          "the world map uses the Known World relief");
                    Check(map.Shipping.RouteCount == 5 && map.Shipping.VesselCount >= 10,
                          $"{map.Shipping.VesselCount} ships across {map.Shipping.RouteCount} port routes");
                    _mapBoats = map.Shipping.GetChildren().OfType<Node3D>().Select(b => b.Position).ToArray();
                    _step++; break;
                }
                case 5 when t > 7.6:
                {
                    var map = root.Map;
                    var pin = map.Pins.First(p => p.M.Id == _city);
                    var b = map.Kw.BoundsXy;
                    bool inside = pin.Position.X > b[0] && pin.Position.X < b[2] && -pin.Position.Z > b[1] && -pin.Position.Z < b[3] && pin.Position.Y >= 0;
                    Check(WorldMap.ReliefMax is > 6f and < 9f,
                          $"Known World relief from KnownWorld.blend: peak {WorldMap.ReliefMax:0.0} units at {map.Kw.Exaggeration:0}x, {map.Kw.Cameras.Count} blend views");
                    Check(inside, $"{_city} pin on the relief at ({pin.Position.X:0.0}, {pin.Position.Y:0.00}, {pin.Position.Z:0.0})");
                    Check(map.Shipping.GetChildren().OfType<Node3D>().Select((boat, i) =>
                        boat.Position.DistanceTo(_mapBoats[i])).Count(d => d > 0.2f) >= 5,
                        "ships advance along the world map routes");
                    root.OpenCity(_city);
                    _step++; break;
                }
                case 6 when t > 8.4:
                    Check(root.City != null && root.City.M.Id == _city, "reopened the city from the map");
                    GD.Print(_fails == 0 ? "[Selftest] PASS" : $"[Selftest] SELFTEST FAIL ({_fails} checks)");
                    _step++;
                    root.GetTree().Quit(_fails == 0 ? 0 : 1);
                    break;
            }
        }
    }
}
