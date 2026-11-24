// --selftest: drives the app like the plan's Phase 4 acceptance check and prints [Selftest] PASS/FAIL lines.
// Open a city, scrub dawn to night, change the latitude and see the arc change, fly to a landmark, press
// Chariot Race (run 25x faster) and see the stands fill and the race start, go back to the map, reopen.
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
        static int _fails;

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
                    var lm = v.M.Landmarks.First(l => l.Id == "hippodrome");
                    _expectCam = Geo.V(lm.Camera.Target) + Geo.Orbit((float)lm.Camera.Yaw, (float)lm.Camera.Pitch, (float)lm.Camera.Dist);
                    v.Jump("hippodrome");
                    _step++; break;
                }
                case 2 when t > 3.2:
                {
                    float d = v.Rig.Cam.GlobalPosition.DistanceTo(_expectCam);
                    Check(d < 6f, $"flew to the hippodrome landmark (camera {d:0.0} m from preset)");
                    v.Events.TimeScale = 25;
                    v.Events.Trigger("chariot_race");
                    Check(v.Events.Running != null, "Chariot Race triggered");
                    _step++; break;
                }
                case 3 when t > 6.2:
                {
                    var hip = v.M.VenueOfType("circus");
                    double fill = v.Life.Seats[hip.Id].Fill;
                    Check(fill > 0.9, $"hippodrome filled to {fill:0.00}");
                    Check(v.Events.Race != null && v.Events.Race.Time > 1, $"race running: {v.Events.Status}");
                    Check(v.Life.Crowd.W.Count(w => w.Active) > 100, $"{v.Life.Crowd.W.Count(w => w.Active)} people walking");
                    Check(v.Life.Traffic.Ships.Count(s => s.Visible) > 2, $"{v.Life.Traffic.Ships.Count(s => s.Visible)} ships under way");
                    root.ShowMap();
                    _step++; break;
                }
                case 4 when t > 6.8:
                    Check(root.Map != null && root.City == null, "back to the world map");
                    root.OpenCity(_city);
                    _step++; break;
                case 5 when t > 7.6:
                    Check(root.City != null && root.City.M.Id == _city, "reopened the city from the map");
                    GD.Print(_fails == 0 ? "[Selftest] PASS" : $"[Selftest] SELFTEST FAIL ({_fails} checks)");
                    _step++;
                    root.GetTree().Quit(_fails == 0 ? 0 : 1);
                    break;
            }
        }
    }
}
