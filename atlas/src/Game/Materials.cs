// Shader materials that replace the glTF materials by name, plus shared materials for props and glow sprites.
using Godot;

namespace Atlas
{
    public sealed class Materials
    {
        public readonly ShaderMaterial Painted, Terrain, Water, Fire, Glow, Figure, Cloud, Instanced;

        public Materials(string terrainAlbedoPath)
        {
            Painted = Make("res://shaders/painted.gdshader");
            Terrain = Make("res://shaders/terrain.gdshader");
            Water = Make("res://shaders/water.gdshader");
            Fire = Make("res://shaders/fire.gdshader");
            Glow = Make("res://shaders/glow.gdshader");
            Figure = Make("res://shaders/figure.gdshader");
            Cloud = Make("res://shaders/cloud.gdshader");
            Instanced = Make("res://shaders/instanced.gdshader");   // FIX(karn_ashur): instanced houses and trees
            if (terrainAlbedoPath != null && System.IO.File.Exists(terrainAlbedoPath))
            {
                var img = Image.LoadFromFile(terrainAlbedoPath);
                img.GenerateMipmaps();
                Terrain.SetShaderParameter("albedo_tex", ImageTexture.CreateFromImage(img));
            }
        }

        static ShaderMaterial Make(string path)
        {
            var sh = ResourceLoader.Load<Shader>(path);
            return new ShaderMaterial { Shader = sh };
        }

        public Material ForGltf(string name) => name switch
        {
            "CAP_Painted" => Painted,
            "CAP_Terrain" => Terrain,
            "CAP_Water" => Water,
            "CAP_Fire" => Fire,
            _ => Painted,
        };

        public void SetNight(float windowLevel, float lampLevel)
        {
            Painted.SetShaderParameter("night_level", windowLevel);
            Instanced.SetShaderParameter("night_level", windowLevel);
            Figure.SetShaderParameter("night_level", 0.0f);
            Glow.SetShaderParameter("window_level", windowLevel);
            Glow.SetShaderParameter("lamp_level", lampLevel);
            Fire.SetShaderParameter("strength", 2.0f + 6.0f * lampLevel);
        }
    }
}
