// World map (S9 replaces this stub).
using Godot;
namespace Atlas
{
    public partial class WorldMap : CanvasLayer
    {
        public void Build(AtlasRoot root)
        {
            var box = new VBoxContainer();
            AddChild(box);
            foreach (var c in root.Cities) { var id = c.Id; var b = new Button { Text = c.Name }; b.Pressed += () => root.OpenCity(id); box.AddChild(b); }
        }
    }
}
