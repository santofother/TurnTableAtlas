// Ambient life (S8 replaces this stub).
using System;
using System.Collections.Generic;
using Godot;
namespace Atlas
{
    public partial class Life : Node3D
    {
        public void Build(CityView v) { }
        public void SetHour(double h) { }
        public IEnumerable<(string, Func<bool>, Action<bool>)> Layers() { yield break; }
    }
}
