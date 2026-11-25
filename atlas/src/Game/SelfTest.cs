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
        static readonly string[] Preferred = { "chariot_race", "gladiator_games", "theatre_play", "villa_return" };

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
                    double dawn = Math.Max(6.0, v.M.Sun.SunriseH + 0.75);   // FIX(villa): an autumn package is still dark at 6
                    tod.Hour = dawn; tod.Apply(); double e6 = tod.Elevation; double w6 = tod.WindowLevel;
                    tod.Hour = 12; tod.Apply(); double e12 = tod.Elevation;
                    tod.Hour = 22.5; tod.Apply(); double w22 = tod.WindowLevel;
                    Check(e12 > e6 + 15 && w22 > 0.5 && w6 < w22, $"scrub dawn ({dawn:0.0}h)→noon→night: elevation {e6:0}°→{e12:0}°, windows lit {w22:0.00} at 22:30");
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
                    v.Events.TimeScale = v.M.IsEstate ? 5 : 25;   // FIX(villa): a scene walks at people's pace
                    if (_event != null) v.Events.Trigger(_event);
                    if (v.M.IsMetropolis)   // FIX(karn_ashur): a metropolis has no shows; its houses and trees are instanced
                        Check(v.City.InstanceCount > 50000 && v.City.Instances.CountOf("house") > 30000,
                              $"metropolis: {v.City.InstanceCount} instances ({v.City.Instances.CountOf("house")} houses, {v.City.Instances.CountOf("palm")} palms), no shows ({v.Events.Available.Count})");
                    else if (v.M.IsEstate)   // FIX(villa): an estate's events are its chapter scenes, staged on its anchors
                        Check(v.Events.Available.Count == 4 && v.Events.Running != null && v.M.Anchors.Count >= 10,
                              $"estate scene '{_event}' started ({v.Events.Available.Count} scenes, {v.M.Anchors.Count} staging anchors)");
                    else
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
                    if (v.M.IsEstate)
                    {
                        int walking = v.Life.Crowd.W.Count(w => w.Active);
                        Check(walking >= 3 && walking < 30 && Swarm.FigureScale > 3f, $"estate household: {walking} people about, figures x{Swarm.FigureScale:0.0}");
                        var layers = v.Life.Layers().ToDictionary(l => l.Item1);
                        bool cut = layers.ContainsKey("Roofs") && layers.ContainsKey("Upper floor");
                        if (cut)
                        {
                            layers["Roofs"].Item3(false); layers["Upper floor"].Item3(false);
                            cut = !layers["Roofs"].Item2() && !layers["Upper floor"].Item2();
                            layers["Roofs"].Item3(true); layers["Upper floor"].Item3(true);
                        }
                        Check(cut, "cutaway: roofs and the upper floor lift off");
                        var st = v.Events.Stage;
                        var gate = v.M.Anchors.TryGetValue("gate_stop", out var g) ? Polyline.V(g) : new Vec3(0, 0, 0);
                        double toGate = st["h_landric"] is { } hl ? (hl.Pos - gate).Length2D : 99;
                        Check(st.Actors.Count >= 11 && toGate < 4.0 && st["h_escort"]?.Mount == null && st["escort"]?.Mount == "h_escort",
                              $"Return to the Villa: {st.Actors.Count} actors, Landric's horse {toGate:0.0} m from the gate stop, the escort still mounted");
                    }
                    else if (v.M.IsMetropolis)
                    {
                        int walking = v.Life.Crowd.W.Count(w => w.Active);
                        Check(walking > 100 && Swarm.FigureScale < 1f, $"{walking} people on the metropolis's streets, figures x{Swarm.FigureScale:0.00}");
                        if (v.M.Site?.IsFloodplain == true)   // FIX(haven): a river capital: its pyramids and its red river
                        {
                            int pyramids = v.M.Anchors.Keys.Count(k => k.EndsWith("_pyramid"));
                            bool red = v.City.ByName.TryGetValue("CAP_Sea_Rivers", out var rw) && rw.Mesh is ArrayMesh am
                                       && am.SurfaceGetArrays(0)[(int)Mesh.ArrayType.Color].AsColorArray() is { Length: > 0 } wc && wc[0].G < 0.5f;
                            Check(pyramids == 3 && v.City.Instances.CountOf("marble") >= 18 && red,
                                  $"{v.M.Name}: {pyramids} white-marble pyramids ({v.City.Instances.CountOf("marble")} tiers and stairs), the river drawn silt-red");
                            var bf = v.Life.Barges;   // grain barges down the river, empty ones back up, moving
                            var p0 = bf?.Positions();
                            bf?.Tick(bf.Time + 30);
                            var p1 = bf?.Positions();
                            Check(bf != null && bf.Afloat > 20 && p0.Length == p1.Length && p0.Zip(p1, (a, b) => a.DistanceTo(b)).Count(d => d > 0.5f) > 15,
                                  $"{bf?.Afloat} barges under way on the Flame ({bf?.Count} on two lanes), {v.City.Instances.CountOf("barge_grain")} grain barges moored");
                        }
                        else
                        {
                            var flame = v.M.NightLights.FirstOrDefault(l => l.Kind == "lighthouse");
                            Check(flame != null && flame.Pos[2] > 25, $"the First Flame burns on the summit (z {flame?.Pos[2]:0.0})");
                        }
                    }
                    else
                    {
                        Check(showOn, $"show running: {v.Events.Status}");
                        Check(v.Life.Crowd.W.Count(w => w.Active) > 100, $"{v.Life.Crowd.W.Count(w => w.Active)} people walking");
                        Check(v.Life.Traffic.Ships.Count(s => s.Visible) > 2, $"{v.Life.Traffic.Ships.Count(s => s.Visible)} ships under way");
                    }
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
                    var sunC = map.SunControls;
                    int noon0 = (int)SunArc.Position(map.Tod.Latitude, map.Tod.DayOfYear, 12).Elevation;
                    if (sunC != null) { sunC.Latitude.Value = 10; sunC.ShowPath.ButtonPressed = true; }
                    Check(sunC != null && map.Tod.Latitude == 10 && map.Gizmo.Visible,
                          $"sun controls on the Known World: latitude {map.Tod.Latitude:0}°, noon {noon0}° → {SunArc.Position(10, map.Tod.DayOfYear, 12).Elevation:0}°, sun path shown");
                    map.WeatherControls.KindButton(WeatherKind.Fair).EmitSignal(BaseButton.SignalName.Pressed);
                    Check(map.GetNodeOrNull("Geography") == null && map.GetNodeOrNull("MapTable/GeographyFrame") == null,
                          "the world map uses the Known World relief");
                    Check(map.Shipping.RouteCount == 20 && map.Shipping.VesselCount >= 40,
                          $"{map.Shipping.VesselCount} ships across {map.Shipping.RouteCount} port routes");
                    Check(map.GetNodeOrNull<MeshInstance3D>("RegionalFog")?.MaterialOverride is ShaderMaterial,
                          "the Known World has terrain-following fog");
                    foreach (var m in root.Cities.Where(c => c.IsMetropolis))   // FIX(karn_ashur): the basin from its own package
                    {
                        var bas = map.Basins.FirstOrDefault(b => b.M.Id == m.Id);
                        var pinB = map.Pins.FirstOrDefault(p => p.M.Id == m.Id);
                        float onPatch = bas != null && pinB != null ? Math.Abs(pinB.Position.Y - (bas.HeightAt(bas.S.Cx, bas.S.Cy) ?? -9f)) : 9f;
                        bool flood = bas?.S.Floodplain == true;   // FIX(haven): Haven's patch: the river across its ring, no flame
                        Check(bas != null && bas.InstanceCount > 50000 && bas.RiverRibbons >= (flood ? 3 : 5) && onPatch < 0.002f
                              && map.Kw.Cameras.Any(c => c.Id == Basin.ViewIdFor(bas.S))
                              && (flood ? bas.S.InletPath.Length > 2 && bas.S.OutletPath.Length > 2 : bas.FlamePosition.Y > bas.S.Units(3500)),
                              $"{m.Name} on the Known World: {bas?.InstanceCount} instances, {bas?.RiverRibbons} water ribbons, plinth {bas?.S.Half * 2:0.00} units, " +
                              (flood ? "the river carried across its ring" : $"the First Flame at {bas?.S.Metres(bas.FlamePosition.Y):0} m") + ", pin on its patch");
                    }
                    var fv = map.Valley;   // FIX(haven): the red River Flame and its farmland
                    if (root.Cities.Any(c => c.Site?.IsFloodplain == true))
                        Check(fv != null && fv.R.Reaches.Any(r => r.Id == "trunk_upper") && fv.R.Reaches.Count(r => r.Id.EndsWith("_arm")) == 4 && fv.VillageCount > 400
                              && fv.FieldQuads > 1000 && fv.RiverSegments > 500 && map.Kw.Cameras.Any(c => c.Id == WorldMap.FlameViewId),
                              $"River Flame: {fv?.R.Reaches.Count} red reaches joined to Haven's patch, {fv?.FieldQuads} field quads, {fv?.VillageCount} villages, {fv?.TownCount} market towns (~{fv?.R.Population / 1000}k people)");
                    if (root.Cities.Any(c => c.Site?.IsFloodplain == true))
                        Check(fv?.Barges != null && fv.Barges.Count > 200 && fv.Barges.Afloat > 150,
                              $"River Flame: {fv?.Barges?.Afloat} barges afloat from the foothills to the sea");
                    var hd = map.Dunes;
                    bool graded = hd != null && hd.R.Rivers.All(r => r.BedM.Zip(r.BedM.Skip(1), (a, b) => b <= a + 1e-6).All(x => x));
                    Check(hd != null && graded && hd.R.Rivers.Count >= 4 && hd.VillageCount > 150 && hd.TownCount >= 5 && hd.RouteSegments > 50 && hd.SeaLeg != null
                          && map.Kw.Cameras.Any(c => c.Id == WorldMap.HighDunesViewId),
                          $"High Dunes: {hd?.R.Rivers.Count} rivers graded downhill, {hd?.VillageCount} villages, {hd?.TownCount} market towns (~{hd?.R.Population / 1000}k people), grain route {hd?.RouteSegments} segments");
                    foreach (var m in root.Cities.Where(c => c.IsEstate))   // FIX(villa): an estate stands on the map as its miniature
                    {
                        var est = map.Estates.FirstOrDefault(e => e.M.Id == m.Id);
                        var pinE = map.Pins.FirstOrDefault(p => p.M.Id == m.Id);
                        float onPatch = est != null && pinE != null ? Math.Abs(pinE.Position.Y - (est.HeightAt(est.S.Cx, est.S.Cy) ?? -9f)) : 9f;
                        Check(est != null && est.MiniMeshes > 20 && onPatch < 0.002f && map.Kw.Cameras.Any(c => c.Id == est.ViewId),
                              $"{m.Name} on the Known World: {est?.MiniMeshes} miniature meshes, {est?.S.Half * 2:0.000} units across, pin on its patch");
                    }
                    foreach (var pin0 in map.Pins.Where(p => p.M.IsEstate))
                        Check(!pin0.LabelShown, $"{pin0.M.Name}: name hidden until the camera comes in");
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
