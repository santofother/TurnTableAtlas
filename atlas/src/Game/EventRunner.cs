// Event system (S8 replaces this stub).
using System;
using System.Collections.Generic;
using Godot;
namespace Atlas
{
    public partial class EventRunner : Node3D
    {
        public record EventInfo(string Id, string Label);
        public List<EventInfo> Available { get; } = new();
        public event Action<string> StatusChanged;
        public void Setup(CityView v) { }
        public void Trigger(string id) { StatusChanged?.Invoke(id); }
    }
}
