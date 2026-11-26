// A town miniature's own water on the Known World (Town.cs, FIX(S31)): a harbour basin or a river through the town,
// drawn in the map's own sea colour beside the town (water_colour, linear) with the relief's sea ripples and glint,
// so it reads as the same water as the bay. Inland it keeps a deep river green-blue.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform vec3 water_colour = vec3(0.012, 0.06, 0.08);
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;
uniform vec2 world_min;
uniform vec2 world_size;
uniform vec2 centre;        // town centre (x, z)
uniform float half_size;    // half the model's square (blend units)
uniform vec2 reach = vec2(0.45, 0.82);   // the rim (TownSite.Rim) where open water / a river ends
varying vec3 wpos;
varying float river;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }
float waves(vec2 p) { return vn(p + vec2(TIME * 0.05, TIME * 0.03)) * 0.6 + vn(p * 2.3 - vec2(TIME * 0.07, -TIME * 0.05)) * 0.4; }

void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; river = COLOR.r; }

float fbm_rim(vec2 q) { return vn(q * 3.1 + vec2(7.3, 1.9)) * 0.65 + vn(q * 7.7 + vec2(2.2, 5.4)) * 0.35; }
float rim_of(vec2 q) {   // TownSite.Rim
    float r = pow(pow(abs(q.x), 4.0) + pow(abs(q.y), 4.0), 0.25);
    return r + 0.1 * (fbm_rim(q) - 0.5) * min(1.0, r * 2.0);
}

void fragment() {
    // the water ends along the town's rim, dithered into the map's own land under it
    vec2 q = vec2(wpos.x - centre.x, -(wpos.z - centre.y)) / half_size;
    float end = mix(reach.x, reach.y, step(0.5, river));
    float keep = 1.0 - smoothstep(end - 0.08, end + 0.04, rim_of(q) + 0.04 * (vn(wpos.xz * 300.0) - 0.5));
    if (keep < hash2(floor(FRAGCOORD.xy)) * 0.98 + 0.01) discard;
    // over the map's own sea pixels, its own colour; elsewhere the sea colour beside the town
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 c = textureLod(height_tex, map_uv, 0.0).r < 0.0 ? texture(albedo_tex, map_uv).rgb : water_colour;
    vec2 p = wpos.xz * 1.6;
    float e = 0.05, w0 = waves(p);
    float k = 0.035 + 0.06 * cloud_wet;
    vec3 n = normalize(vec3(-(waves(p + vec2(e, 0.0)) - w0) / e * k, 1.0, -(waves(p + vec2(0.0, e)) - w0) / e * k));
    NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
    ALBEDO = c * cloud_shadow(wpos);
    ROUGHNESS = 0.3;
    SPECULAR = 0.5;
}
