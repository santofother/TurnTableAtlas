// Turntable camera: orbit (left drag), pan (right/middle drag), eased zoom (wheel), auto-rotate (R),
// free-fly (F: WASD + QE, right drag to look), smooth landmark jumps. Never clips into the proxies.
using System;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public partial class TurntableCamera : Node3D
    {
        public Camera3D Cam { get; private set; }
        public bool AutoRotate;
        public bool FreeFly { get; private set; }
        public float MinDist = 2.0f, MaxDist = 170f, MinPitch = 4f, MaxPitch = 89f;
        public Vector3 Target;
        public float Yaw = -90f, Pitch = 35f, Dist = 90f;            // what is shown
        Vector3 _tTarget; float _tYaw, _tPitch, _tDist;             // where it eases to
        bool _orbiting, _panning, _looking;
        Vector3 _flyPos; float _flyYaw, _flyPitch;
        (Vector3 T, float Y, float P, float D) _flyFrom, _flyTo;
        double _flyT = 1.0, _flyDur = 1.6;
        public Rect2 Bounds = new(-60, -60, 120, 120);

        public override void _Ready()
        {
            Cam = new Camera3D { Name = "Camera", Fov = 40f, Near = 0.05f, Far = 2000f, Current = true };
            AddChild(Cam);
            _tTarget = Target; _tYaw = Yaw; _tPitch = Pitch; _tDist = Dist;
        }

        public void Snap(Vector3 target, float yaw, float pitch, float dist)
        {
            Target = _tTarget = target; Yaw = _tYaw = yaw; Pitch = _tPitch = pitch; Dist = _tDist = dist;
            UpdateTransform();
        }

        public void FlyTo(CameraPreset p, double seconds = 1.6)
        {
            if (FreeFly) ToggleFreeFly();
            var to = Geo.V(p.Target);
            float yaw = (float)p.Yaw;
            while (yaw - _tYaw > 180) yaw -= 360;
            while (yaw - _tYaw < -180) yaw += 360;
            _flyFrom = (_tTarget, _tYaw, _tPitch, _tDist);
            _flyTo = (to, yaw, (float)p.Pitch, (float)p.Dist);
            _flyT = 0.0;
            _flyDur = seconds;
        }

        public void ToggleFreeFly()
        {
            FreeFly = !FreeFly;
            if (FreeFly)
            {
                _flyPos = Cam.GlobalPosition;
                _flyYaw = Cam.GlobalRotation.Y; _flyPitch = Cam.GlobalRotation.X;
            }
            else
            {
                // hand back to orbit around the point in front of the camera
                var fwd = -Cam.GlobalBasis.Z;
                _tTarget = _flyPos + fwd * Math.Clamp(_tDist, 6f, 40f);
                _tTarget.Y = Math.Max(0f, _tTarget.Y);
                var off = _flyPos - _tTarget;
                _tDist = off.Length();
                _tPitch = Mathf.RadToDeg(Mathf.Asin(Math.Clamp(off.Y / Math.Max(0.001f, _tDist), -1f, 1f)));
                _tYaw = Mathf.RadToDeg(Mathf.Atan2(-off.Z, off.X));
                Snap(_tTarget, _tYaw, _tPitch, _tDist);
            }
        }

        public override void _UnhandledInput(InputEvent e)
        {
            if (e is InputEventMouseButton mb)
            {
                if (mb.ButtonIndex == MouseButton.WheelUp && mb.Pressed) Zoom(0.88f);
                else if (mb.ButtonIndex == MouseButton.WheelDown && mb.Pressed) Zoom(1.0f / 0.88f);
                else if (mb.ButtonIndex == MouseButton.Left) _orbiting = mb.Pressed;
                else if (mb.ButtonIndex == MouseButton.Right) { _panning = mb.Pressed && !FreeFly; _looking = mb.Pressed && FreeFly; }
                else if (mb.ButtonIndex == MouseButton.Middle) _panning = mb.Pressed;
                if (mb.Pressed) _flyT = 1.0;
            }
            else if (e is InputEventMagnifyGesture mg) Zoom(1f / mg.Factor);
            else if (e is InputEventPanGesture pg) { _tYaw -= pg.Delta.X * 2f; _tPitch = Math.Clamp(_tPitch + pg.Delta.Y * 1.5f, MinPitch, MaxPitch); }
            else if (e is InputEventMouseMotion mm)
            {
                if (FreeFly && (_looking || _orbiting))
                {
                    _flyYaw -= mm.Relative.X * 0.004f;
                    _flyPitch = Math.Clamp(_flyPitch - mm.Relative.Y * 0.004f, -1.5f, 1.5f);
                }
                else if (_orbiting)
                {
                    _tYaw -= mm.Relative.X * 0.3f;
                    _tPitch = Math.Clamp(_tPitch + mm.Relative.Y * 0.22f, MinPitch, MaxPitch);
                }
                else if (_panning)
                {
                    float k = _tDist * 0.0016f;
                    var right = Cam.GlobalBasis.X; right.Y = 0; right = right.Normalized();
                    var fwd = -Cam.GlobalBasis.Z; fwd.Y = 0; fwd = fwd.Normalized();
                    _tTarget += (-right * mm.Relative.X + fwd * mm.Relative.Y) * k;
                    _tTarget.X = Math.Clamp(_tTarget.X, Bounds.Position.X, Bounds.End.X);
                    _tTarget.Z = Math.Clamp(_tTarget.Z, Bounds.Position.Y, Bounds.End.Y);
                }
            }
            else if (e is InputEventKey k && k.Pressed && !k.Echo)
            {
                if (k.Keycode == Key.R) AutoRotate = !AutoRotate;
                if (k.Keycode == Key.F) ToggleFreeFly();
            }
        }

        void Zoom(float f) => _tDist = Math.Clamp(_tDist * f, MinDist, MaxDist);

        public override void _Process(double delta)
        {
            float dt = (float)delta;
            if (FreeFly)
            {
                var move = Vector3.Zero;
                if (Input.IsKeyPressed(Key.W)) move.Z -= 1;
                if (Input.IsKeyPressed(Key.S)) move.Z += 1;
                if (Input.IsKeyPressed(Key.A)) move.X -= 1;
                if (Input.IsKeyPressed(Key.D)) move.X += 1;
                if (Input.IsKeyPressed(Key.E)) move.Y += 1;
                if (Input.IsKeyPressed(Key.Q)) move.Y -= 1;
                float sp = (Input.IsKeyPressed(Key.Shift) ? 24f : 7f) * dt;
                var basis = Basis.FromEuler(new Vector3(_flyPitch, _flyYaw, 0));
                _flyPos += basis * move * sp;
                _flyPos.Y = Math.Max(_flyPos.Y, GroundAt(_flyPos) + 0.25f);
                Cam.GlobalTransform = new Transform3D(basis, _flyPos);
                return;
            }
            if (_flyT < 1.0)
            {
                _flyT = Math.Min(1.0, _flyT + delta / _flyDur);
                float s = (float)(0.5 - 0.5 * Math.Cos(Math.PI * _flyT));
                _tTarget = _flyFrom.T.Lerp(_flyTo.T, s);
                _tYaw = Mathf.Lerp(_flyFrom.Y, _flyTo.Y, s);
                _tPitch = Mathf.Lerp(_flyFrom.P, _flyTo.P, s);
                // dolly out a little mid-flight so long jumps read as a move, not a cut
                _tDist = Mathf.Lerp(_flyFrom.D, _flyTo.D, s) * (1f + 0.35f * Mathf.Sin(Mathf.Pi * s) * Mathf.Clamp(_flyFrom.T.DistanceTo(_flyTo.T) / 40f, 0f, 1f));
            }
            if (AutoRotate) _tYaw += 5f * dt;
            float a = 1f - Mathf.Exp(-dt * 7f);
            Target = Target.Lerp(_tTarget, a);
            Yaw = Mathf.Lerp(Yaw, _tYaw, a);
            Pitch = Mathf.Lerp(Pitch, _tPitch, a);
            Dist = Mathf.Lerp(Dist, _tDist, a);
            UpdateTransform();
        }

        void UpdateTransform()
        {
            if (Cam == null) return;
            var want = Target + Geo.Orbit(Yaw, Pitch, Dist);
            // keep the camera above whatever is under it (terrain, roofs, walls): no clipping into the model.
            // (A target->camera ray would start inside landmark proxy boxes and yank the camera in.)
            want.Y = Math.Max(want.Y, GroundAt(want) + 0.35f);
            Cam.GlobalPosition = want;
            var dir = Target - want;
            if (dir.LengthSquared() > 1e-6f) Cam.LookAt(Target, Mathf.Abs(dir.Normalized().Y) > 0.999f ? Vector3.Forward : Vector3.Up);
        }

        float GroundAt(Vector3 p)
        {
            var space = GetWorld3D()?.DirectSpaceState;
            if (space == null) return -10f;
            var q = PhysicsRayQueryParameters3D.Create(new Vector3(p.X, 200, p.Z), new Vector3(p.X, -20, p.Z), CityLoader.CollisionLayer);
            var hit = space.IntersectRay(q);
            return hit.Count > 0 ? ((Vector3)hit["position"]).Y : -10f;
        }

        /// <summary>Point under the mouse on the city (for double-click focus).</summary>
        public Vector3? Pick(Vector2 screen)
        {
            var from = Cam.ProjectRayOrigin(screen);
            var to = from + Cam.ProjectRayNormal(screen) * 1000f;
            var hit = GetWorld3D().DirectSpaceState.IntersectRay(PhysicsRayQueryParameters3D.Create(from, to, CityLoader.CollisionLayer));
            return hit.Count > 0 ? (Vector3)hit["position"] : null;
        }

        public void FocusOn(Vector3 p) { _tTarget = p; _tDist = Math.Min(_tDist, 18f); }
    }
}
