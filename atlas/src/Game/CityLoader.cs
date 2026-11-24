// Loads a city package (cities/<id>/) at runtime: no editor import, so a new city is just a new folder.
using System;
using System.Collections.Generic;
using Atlas.Core;
using Godot;

namespace Atlas
{
    public sealed class LoadedCity
    {
        public CityManifest M;
        public Node3D Model;
        public StaticBody3D Collision;
        public Materials Mats;
        public readonly Dictionary<string, Mesh> ShipMeshes = new();
        public readonly Dictionary<string, MeshInstance3D> ByName = new();
        public int MeshCount, Triangles;
    }

    public static class CityLoader
    {
        public const uint CollisionLayer = 1;

        public static LoadedCity Load(CityManifest m)
        {
            var t0 = Time.GetTicksMsec();
            var city = new LoadedCity { M = m, Mats = new Materials(m.FilePath("terrain_albedo")) };
            city.Model = LoadGlb(m.FilePath("model"));
            city.Model.Name = "CityModel";
            foreach (var mi in AllMeshes(city.Model))
            {
                city.MeshCount++;
                city.ByName[mi.Name] = mi;
                var mesh = mi.Mesh;
                for (int s = 0; s < mesh.GetSurfaceCount(); s++)
                {
                    var src = mesh.SurfaceGetMaterial(s);
                    mi.SetSurfaceOverrideMaterial(s, city.Mats.ForGltf(src?.ResourceName ?? ""));
                    city.Triangles += SurfaceTris(mesh, s);
                }
                mi.CastShadow = mi.Name.ToString().StartsWith("CAP_Sea") ? GeometryInstance3D.ShadowCastingSetting.Off
                                                                          : GeometryInstance3D.ShadowCastingSetting.On;
                var nm = mi.Name.ToString();
                if (nm.StartsWith("CAP_Ship_"))
                {
                    var kind = nm.Substring(nm.LastIndexOf('_') + 1);
                    if (!city.ShipMeshes.ContainsKey(kind)) city.ShipMeshes[kind] = mesh;
                }
            }
            city.Collision = BuildCollision(m.FilePath("proxies"));
            GD.Print($"[Atlas] loaded {m.Id}: {city.MeshCount} meshes, {city.Triangles / 1000}k tris, ships {string.Join(",", city.ShipMeshes.Keys)} in {Time.GetTicksMsec() - t0} ms");
            return city;
        }

        public static Node3D LoadGlb(string path)
        {
            var doc = new GltfDocument();
            var state = new GltfState();
            var err = doc.AppendFromFile(path, state);
            if (err != Error.Ok) throw new Exception($"glTF load failed ({err}): {path}");
            var scene = doc.GenerateScene(state) as Node3D;
            if (scene == null) throw new Exception("glTF produced no scene: " + path);
            ConvertImporterMeshes(scene);
            return scene;
        }

        /// <summary>Runtime glTF may hand back ImporterMeshInstance3D nodes; swap them for MeshInstance3D.</summary>
        static void ConvertImporterMeshes(Node root)
        {
            var list = new List<ImporterMeshInstance3D>();
            Collect(root, list);
            foreach (var imi in list)
            {
                var mi = new MeshInstance3D { Name = imi.Name, Transform = imi.Transform, Mesh = imi.Mesh?.GetMesh() };
                var parent = imi.GetParent();
                int idx = imi.GetIndex();
                parent.RemoveChild(imi);
                parent.AddChild(mi);
                parent.MoveChild(mi, idx);
                foreach (var ch in imi.GetChildren()) { imi.RemoveChild(ch); mi.AddChild(ch); }
                imi.QueueFree();
            }
        }

        static void Collect(Node n, List<ImporterMeshInstance3D> list)
        {
            if (n is ImporterMeshInstance3D imi) list.Add(imi);
            foreach (var c in n.GetChildren()) Collect(c, list);
        }

        public static IEnumerable<MeshInstance3D> AllMeshes(Node n)
        {
            if (n is MeshInstance3D mi && mi.Mesh != null) yield return mi;
            foreach (var c in n.GetChildren())
                foreach (var x in AllMeshes(c)) yield return x;
        }

        static int SurfaceTris(Mesh mesh, int s)
        {
            if (mesh is ArrayMesh am)
            {
                var arr = am.SurfaceGetArrays(s);
                var idx = arr[(int)Mesh.ArrayType.Index];
                if (idx.VariantType != Variant.Type.Nil) return idx.AsInt32Array().Length / 3;
                return am.SurfaceGetArrayLen(s) / 3;
            }
            return 0;
        }

        /// <summary>Transform of a node relative to `root` without needing the scene tree.</summary>
        public static Transform3D LocalToRoot(Node3D n, Node root)
        {
            var t = n.Transform;
            for (var p = n.GetParent(); p != null && p != root; p = p.GetParent())
                if (p is Node3D p3) t = p3.Transform * t;
            return t;
        }

        static StaticBody3D BuildCollision(string path)
        {
            var body = new StaticBody3D { Name = "Collision", CollisionLayer = CollisionLayer, CollisionMask = 0 };
            if (!System.IO.File.Exists(path)) return body;
            var proxies = LoadGlb(path);
            foreach (var mi in AllMeshes(proxies))
            {
                var shape = mi.Mesh.CreateTrimeshShape();
                body.AddChild(new CollisionShape3D { Shape = shape, Transform = LocalToRoot(mi, proxies), Name = mi.Name });
            }
            proxies.Free();
            return body;
        }
    }
}
