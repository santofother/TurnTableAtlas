using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    public class LifeTests
    {
        static CityManifest Fc => CityManifest.Load(Path.Combine(Repo.Cities, "fantasy_capital", "city.json"));

        [Fact]
        public void PlacedBoatDocksDepartsAndReturns()
        {
            var voyage = new BoatVoyage(new ShipPlacement
            {
                HeadingDeg = 90,
                Voyage = new BoatVoyageData
                {
                    Points = new[] { new[] { 0d, 0d }, new[] { 3d, 0d }, new[] { 3d, 4d }, new[] { 0d, 0d } },
                    Speed = 1,
                    DwellS = 60,
                    PhaseS = 10,
                },
            });

            Assert.Equal(0, voyage.At(49).Pos.Length2D);
            Assert.Equal(System.Math.PI / 2, voyage.At(50).Heading, 6);
            Assert.True(voyage.At(55).Pos.Length2D > 3);
            Assert.Equal(0, voyage.At(voyage.Period - 10).Pos.Length2D);
            Assert.Equal(0, voyage.At(voyage.Period + 49).Pos.Length2D);
        }

        [Fact]
        public void WalkersStayOnTheGraphAndThinOutAtNight()
        {
            var m = Fc;
            var c = new Crowd(new StreetGraph(m.StreetGraph), 800, 2);
            for (int i = 0; i < 600; i++) c.Step(0.05, Crowd.DensityAt(12));
            Assert.Equal(800, c.W.Count);
            Assert.All(c.W, w => Assert.Contains(c.G.Adj[w.From], e => e.To == w.To));
            Assert.True(Crowd.DensityAt(12) > 0.6 && Crowd.DensityAt(2) < 0.1);
            c.Step(0.05, Crowd.DensityAt(2));
            Assert.InRange(c.W.Count(w => w.Active), 20, 120);
        }

        [Fact]
        public void StreamsReachTheVenueAndVanish()
        {
            var m = Fc;
            var g = new StreetGraph(m.StreetGraph);
            var c = new Crowd(g, 0, 3);
            var v = m.Venue("colosseum");
            var targets = v.Entrances.Select(e => g.Nearest(e[0], e[1])).Distinct().ToList();
            int sid = c.AddStream(targets, 120, 5);
            Assert.Equal(120, c.StreamRemaining(sid));
            for (int i = 0; i < 20 * 600; i++) c.Step(0.05, 0);
            Assert.True(c.StreamRemaining(sid) < 6, $"{c.StreamRemaining(sid)} still walking after 10 min");
        }

        [Fact]
        public void ShipsArriveDwellAndLeaveOnWater()
        {
            var m = Fc;
            var t = new ShipTraffic(m, 7);
            var ext = m.Extent;
            var seen = new HashSet<int>();
            bool sawDwell = false;
            var lastPos = new Dictionary<int, Vec3>();
            for (int i = 0; i < 4000; i++)
            {
                t.Step(0.1);
                foreach (var s in t.Ships.Where(s => s.Visible))
                {
                    seen.Add(s.Id);
                    Assert.InRange(s.Pos.X, ext[0] - 0.5, ext[2] + 0.5);
                    Assert.InRange(s.Pos.Y, ext[1] - 0.5, ext[3] + 0.5);
                    if (lastPos.TryGetValue(s.Id, out var lp) && (s.Pos - lp).Length2D < 1e-6 && s.Lane?.Def.Id == "harbour_in") sawDwell = true;
                    lastPos[s.Id] = s.Pos;
                }
            }
            Assert.True(seen.Count > 10);
            Assert.True(sawDwell, "no ship waited at the end of harbour_in");
            Assert.True(t.Ships.Count < 40, "ships are not being retired");
        }

        [Fact]
        public void RaceRunsTheLapsAndEveryoneFinishes()
        {
            var v = Fc.Venue("hippodrome");
            var r = new Race(v, 6, 3, 1.9);
            Assert.Equal(6, r.Riders.Count);
            double maxR = v.LaneRadii.Max() + 0.2;
            for (int i = 0; i < 24 * 200 && !r.Finished; i++)
            {
                r.Step(1.0 / 24);
                foreach (var x in r.Riders) Assert.InRange(x.R, 0.4, maxR);
            }
            Assert.True(r.Finished, "race never finished");
            Assert.Equal(Enumerable.Range(1, 6), r.Riders.Select(x => x.Place).OrderBy(p => p));
            Assert.InRange(r.Time, 3 * r.Tr.Lap / 2.2, 3 * r.Tr.Lap / 1.4 + 10);
        }

        [Fact]
        public void ArenaFightersStayOnTheFloor()
        {
            var v = Fc.Venue("colosseum");
            var a = new Arena(v, 5, 3, 10);
            var c = new Vec3(v.Center[0], v.Center[1], 0);
            for (int i = 0; i < 24 * 60; i++)
            {
                a.Step(1.0 / 24);
                foreach (var f in a.F.Where(f => f.Visible)) Assert.True((f.Pos - c).Length2D < 4.0, $"fighter at {f.Pos}");
            }
            Assert.Equal(16, a.F.Count);
            Assert.All(a.F.Where(f => f.Beast), b => Assert.True(b.Visible));
        }

        sealed class Recorder : IEventHandler
        {
            public readonly List<string> Ran = new();
            public readonly HashSet<string> Conditions = new();
            public void Run(EventStep s) => Ran.Add(s.Do);
            public bool Check(string c) => Conditions.Contains(c);
        }

        [Fact]
        public void TimelineRunsStepsInOrderAndWaits()
        {
            var def = EventDef.Parse(@"{""id"":""x"",""label"":""X"",""steps"":[{""at"":0,""do"":""a""},{""at"":2,""do"":""b""},
                {""wait"":""go""},{""at"":1,""do"":""c""},{""at"":3,""do"":""end""}]}");
            var tl = new EventTimeline(def);
            var h = new Recorder();
            tl.Step(0.5, h); Assert.Equal(new[] { "a" }, h.Ran);
            tl.Step(2.0, h); Assert.Equal(new[] { "a", "b" }, h.Ran);
            for (int i = 0; i < 10; i++) tl.Step(1.0, h);
            Assert.Equal(new[] { "a", "b" }, h.Ran);
            h.Conditions.Add("go");
            tl.Step(0.1, h); tl.Step(1.0, h);
            Assert.Equal(new[] { "a", "b", "c" }, h.Ran);
            Assert.False(tl.Done);
            tl.Step(2.5, h);
            Assert.True(tl.Done);
            Assert.Equal("end", h.Ran.Last());
        }

        [Fact]
        public void ShippedEventsParseAndFitTheCity()
        {
            // FIX(villa): the villa's chapter scenes (villa_*) live beside the five city events
            var defs = EventDef.LoadDir(Path.Combine(Repo.Root, "atlas", "events")).Where(d => !d.Id.StartsWith("villa_")).ToList();
            Assert.Equal(5, defs.Count);
            var m = Fc;
            Assert.All(defs, d => Assert.True(d.AvailableIn(m), d.Id + " not available"));
            Assert.All(defs, d => Assert.Equal("end", d.Steps.Last().Do));
        }
    }
}
