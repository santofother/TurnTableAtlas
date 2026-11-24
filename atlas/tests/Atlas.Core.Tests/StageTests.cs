using System;
using System.IO;
using System.Linq;
using Atlas.Core;
using Xunit;

namespace Atlas.Core.Tests
{
    /// <summary>The scene stage behind the villa's chapter events: walking the street graph, leading, mounting, tweens.</summary>
    public class StageTests
    {
        // an L-shaped street: (0,0) -> (20,0) -> (20,20), nodes 1 m apart, at a 1:3 model scale
        static Stage Make()
        {
            var nodes = Enumerable.Range(0, 21).Select(i => new[] { (double)i, 0, 0 })
                .Concat(Enumerable.Range(1, 20).Select(j => new[] { 20.0, j, 0 })).ToArray();
            var edges = Enumerable.Range(0, nodes.Length - 1).Select(i => new[] { (double)i, i + 1, 0.5 }).ToArray();
            return new Stage(new StreetGraph(new StreetGraphData { Nodes = nodes, Edges = edges }), 3.0);
        }

        static void Run(Stage s, double seconds) { for (double t = 0; t < seconds; t += 0.05) s.Step(0.05); }

        [Fact]
        public void WalkToFollowsTheStreetsAndArrives()
        {
            var s = Make();
            s.Cast("a", "citizen", (1, 1, 1), new Vec3(0, 0, 0), 0);
            s.WalkTo("a", new Vec3(20, 20, 0), 1.5);            // 40 model m round the corner = 120 real m at 1.5 m/s
            Run(s, 40);
            Assert.False(s.Idle("a"));
            Run(s, 41);
            Assert.True(s.Idle("a"));
            Assert.True((s["a"].Pos - new Vec3(20, 20, 0)).Length2D < 1e-6);
            Assert.Equal(Math.PI / 2, s["a"].Heading, 6);       // last leg runs north
        }

        [Fact]
        public void LedHorseKeepsItsGapBehindTheGroom()
        {
            var s = Make();
            s.Cast("groom", "citizen", (1, 1, 1), new Vec3(4, 0, 0), 0);
            s.Cast("horse", "horse", (1, 1, 1), new Vec3(3, 0, 0), 0);
            s.Cast("rider", "citizen", (1, 1, 1), new Vec3(0, 0, 0), 0);
            s.Mount("rider", "horse");
            s.Lead("horse", "groom", 1.8);
            s.WalkTo("groom", new Vec3(20, 10, 0), 1.3);
            Run(s, 70);
            Assert.True(s.Idle("groom") && s.Idle("horse"));
            var gap = s.Path(s["horse"].Pos, s["groom"].Pos);
            Assert.InRange(gap, 0.55, 0.65);                     // 1.8 real m = 0.6 model m, along the trail
            Assert.Equal(s["horse"].Pos.X, s["rider"].Pos.X, 9);   // the rider sits on the horse
            Assert.Equal("rider", s["rider"].Kind);
            s.Dismount("rider", 1);
            Assert.Null(s["rider"].Mount);
            Assert.Equal("citizen", s["rider"].Kind);
            Assert.InRange((s["rider"].Pos - s["horse"].Pos).Length2D, 0.3, 0.35);
        }

        [Fact]
        public void TiltAndSinkEaseToTheirTargets()
        {
            var s = Make();
            s.Cast("b", "citizen", (1, 1, 1), new Vec3(0, 0, 0), 0);
            s.Sink("b", 1.95, 1.4);
            s.Tilt("b", 14, 1.0);
            Run(s, 0.5);
            Assert.False(s.Idle("b"));
            Run(s, 1.5);
            Assert.True(s.Idle("b"));
            Assert.Equal(1.95 / 3, s["b"].Sink, 6);
            Assert.Equal(14 * Math.PI / 180, s["b"].Tilt, 6);
        }

        [Fact]
        public void VillaScenesUseOnlyKnownSteps()
        {
            string[] known = { "status", "clock", "cutaway", "camera", "follow", "cast", "walk", "approach", "lead", "release",
                               "mount", "dismount", "face", "tilt", "sink", "kind", "exit", "flare", "end" };
            var defs = EventDef.LoadDir(Path.Combine(Repo.Root, "atlas", "events")).Where(d => d.Id.StartsWith("villa_")).ToList();
            Assert.Equal(4, defs.Count);
            foreach (var d in defs)
            {
                Assert.Equal("end", d.Steps.Last().Do);
                foreach (var st in d.Steps)
                {
                    if (st.Wait != null) { Assert.True(st.Wait == "all_idle" || st.Wait.StartsWith("idle:"), st.Wait); continue; }
                    Assert.Contains(st.Do, known);
                }
            }
        }
    }
}
