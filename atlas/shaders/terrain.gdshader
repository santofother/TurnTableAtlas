// Terrain: the procedural Blender terrain material baked to terrain_albedo.png (planar UV over the plinth).
shader_type spatial;
render_mode cull_back, diffuse_burley;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1,0)), f.x), mix(hash2(i + vec2(0,1)), hash2(i + vec2(1,1)), f.x), f.y); }

void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }

void fragment() {
    vec3 c = texture(albedo_tex, UV).rgb;
    float n = mix(0.93, 1.06, vn(wpos.xz * 4.0));
    ALBEDO = c * n * cloud_shadow(wpos) * mix(1.0, 0.68, cloud_wet);
    ROUGHNESS = mix(0.92, 0.45, cloud_wet);
    SPECULAR = 0.2;
}
