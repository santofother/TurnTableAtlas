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
