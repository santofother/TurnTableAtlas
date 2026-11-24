// One loaded city on its turntable: model, collision, time of day, camera, sun-arc gizmo, night lights,
// and (S8) ambient life + events. Everything comes from the package's city.json.
using System.Linq;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class CityView : Node3D
    {
        public CityManifest M { get; private set; }
        public LoadedCity City { get; private set; }
        public TimeOfDay Tod { get; private set; }
        public TurntableCamera Rig { get; private set; }
        public SunArcGizmo Gizmo { get; private set; }
        public NightLightsView Lights { get; private set; }
        public Life Life { get; private set; }
        public EventRunner Events { get; private set; }
        public WeatherView Weather { get; private set; }
        /// <summary>The weather shared with the world map (AtlasRoot); a private one if unset.</summary>
        public Atlas.Core.Weather SharedWeather;

        public static CityView Create(CityManifest m)
        {
            var v = new CityView { Name = "City_" + m.Id };
            v.M = m;
            v.City = CityLoader.Load(m);
            return v;
        }

        public override void _Ready()
        {
            AddChild(City.Model);
            AddChild(City.Collision);
            Tod = new TimeOfDay { Name = "TimeOfDay" };
            AddChild(Tod);
            Tod.Setup(City.Mats, M.Sun);
            Lights = new NightLightsView { Name = "NightLights" };
            AddChild(Lights);
            Lights.Build(M, City.Mats);
            Gizmo = new SunArcGizmo { Name = "SunArc", Visible = false };
            AddChild(Gizmo);
            Rig = new TurntableCamera { Name = "Rig" };
            AddChild(Rig);
            var ov = M.Landmarks.FirstOrDefault(l => l.Id == "overview") ?? M.Landmarks[0];
            Rig.Snap(Geo.V(ov.Camera.Target), (float)ov.Camera.Yaw, (float)ov.Camera.Pitch, (float)ov.Camera.Dist * 0.85f);
            Life = new Life { Name = "Life" };
            AddChild(Life);
            Life.Build(this);
            Events = new EventRunner { Name = "Events" };
            AddChild(Events);
            Events.Setup(this);
            Weather = new WeatherView { Name = "Weather" };
            AddChild(Weather);
            var mats = City.Mats;
            Weather.Setup(SharedWeather ?? new Atlas.Core.Weather(), Tod,
                M.IsMetropolis   // FIX(karn_ashur): 1:200 with peaks 30 model metres high: the clouds float above them
                    ? new CloudScale { Base = 96, Top = 128, DeckBase = 140, DeckTop = 185, Half = new Vector2(340, 340), Cell = 190, Shape = 34, Detail = 7, NearFade = 8, FlashR = 70 }
                    : new CloudScale { Base = 30, Top = 56, DeckBase = 100, DeckTop = 150, Half = new Vector2(320, 320), Cell = 140, Shape = 24, Detail = 7, NearFade = 4, FlashR = 60 },
                new[] { mats.Painted, mats.Terrain, mats.Water, mats.Instanced }, true, () => Rig.Target,
                () => System.Math.Clamp(System.Math.Abs(Tod.Speed) * 60, 1.0, 20.0));
            Tod.Changed += OnTimeChanged;
            Tod.Apply();
            Gizmo.Rebuild(Tod);
        }

        void OnTimeChanged()
        {
            Lights.SetLevel((float)Tod.LampLevel);
            Gizmo.UpdateNow(Tod);
            Life?.SetHour(Tod.Hour);
        }

        public void Jump(string landmarkId)
        {
            var lm = M.Landmarks.FirstOrDefault(l => l.Id == landmarkId);
            if (lm != null) Rig.FlyTo(lm.Camera);
        }

        public override void _UnhandledInput(InputEvent e)
        {
            if (e is InputEventMouseButton mb && mb.DoubleClick && mb.ButtonIndex == MouseButton.Left)
            {
                var p = Rig.Pick(mb.Position);
                if (p.HasValue) Rig.FocusOn(p.Value);
            }
        }
    }
}
