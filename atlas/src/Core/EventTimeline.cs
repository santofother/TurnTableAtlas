// Data-driven events (atlas/events/*.json). A timeline is a list of steps run in order. `at` is seconds from
// the start of the current segment; a {"wait": "<condition>"} step blocks until the handler reports the
// condition, then a new segment starts at 0. {"do": "end"} finishes the event.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace Atlas.Core
{
    public sealed class EventStep
    {
        public string Do, Wait;
        public double At;
        public Dictionary<string, JsonElement> Args = new();

        public double Num(string k, double def = 0) => Args.TryGetValue(k, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetDouble() : def;
        public string Str(string k, string def = null) => Args.TryGetValue(k, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : def;
        public List<string> List(string k) => Args.TryGetValue(k, out var v) && v.ValueKind == JsonValueKind.Array
            ? v.EnumerateArray().Select(x => x.GetString()).ToList() : new List<string>();
        public override string ToString() => Wait != null ? $"wait {Wait}" : $"{At:0.#}s {Do}";
    }

    public sealed class EventDef
    {
        public string Id, Label, VenueType, Description;
        public double? ScheduleHour;
        public List<EventStep> Steps = new();

        public static EventDef Parse(string json)
        {
            using var doc = JsonDocument.Parse(json);
            var r = doc.RootElement;
            var d = new EventDef
            {
                Id = r.GetProperty("id").GetString(),
                Label = r.GetProperty("label").GetString(),
                VenueType = r.TryGetProperty("venue_type", out var vt) ? vt.GetString() : null,
                Description = r.TryGetProperty("description", out var de) ? de.GetString() : "",
                ScheduleHour = r.TryGetProperty("schedule_hour", out var sh) && sh.ValueKind == JsonValueKind.Number ? sh.GetDouble() : null,
            };
            foreach (var s in r.GetProperty("steps").EnumerateArray())
            {
                var st = new EventStep();
                foreach (var p in s.EnumerateObject())
                {
                    if (p.Name == "do") st.Do = p.Value.GetString();
                    else if (p.Name == "wait") st.Wait = p.Value.GetString();
                    else if (p.Name == "at") st.At = p.Value.GetDouble();
                    else st.Args[p.Name] = p.Value.Clone();
                }
                d.Steps.Add(st);
            }
            return d;
        }

        public static List<EventDef> LoadDir(string dir) =>
            Directory.Exists(dir) ? Directory.GetFiles(dir, "*.json").OrderBy(f => f).Select(f => Parse(File.ReadAllText(f))).ToList() : new();

        /// <summary>Can this city run the event? (it lists it, and has the venue type it needs)</summary>
        public bool AvailableIn(CityManifest m) => m.Events.Contains(Id) && (VenueType == null || m.VenueOfType(VenueType) != null);
    }

    public interface IEventHandler
    {
        void Run(EventStep step);
        bool Check(string condition);
    }

    public sealed class EventTimeline
    {
        public readonly EventDef Def;
        int _i;
        double _seg;
        public double Elapsed { get; private set; }
        public bool Done { get; private set; }
        public EventStep Current => _i < Def.Steps.Count ? Def.Steps[_i] : null;

        public EventTimeline(EventDef def) { Def = def; }

        public void Step(double dt, IEventHandler h)
        {
            if (Done) return;
            Elapsed += dt;
            _seg += dt;
            int guard = 0;
            while (_i < Def.Steps.Count && guard++ < 64)
            {
                var s = Def.Steps[_i];
                if (s.Wait != null)
                {
                    if (!h.Check(s.Wait)) return;
                    _i++; _seg = 0; continue;
                }
                if (_seg + 1e-9 < s.At) return;
                if (s.Do == "end") { h.Run(s); Done = true; _i = Def.Steps.Count; return; }
                h.Run(s);
                _i++;
            }
            if (_i >= Def.Steps.Count) Done = true;
        }
    }
}
