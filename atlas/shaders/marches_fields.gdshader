// The Valdoran marches' farmland (ValdoranMarches.cs, FIX(S31)): each plot is the map's own colour under it, tinted
// strip by strip for its crops (green wheat, ripening gold, pale fallow), with a darker furrow between strips. Its
// edges are ragged and dithered into the land round it, and the layer fades out with distance, so the plots read as
// farmland painted into the map rather than shapes laid on it. COLOR.rgb seeds the plot; UV runs 0..1 across it.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec2 world_min;
uniform vec2 world_size;
uniform float fade_end = 55.0;
varying vec3 wpos;
varying vec4 seed;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    seed = COLOR;
}

void fragment() {
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 base = texture(albedo_tex, map_uv).rgb;
    // strips across the plot, a little wavy
    // the plot is several holdings across, each ploughed in strips of its own crops
    float n = 10.0 + floor(seed.g * 8.0);
    float bands = 2.0 + floor(seed.b * 3.0);
    float band = floor(UV.y * bands + 0.3 * (vn(UV * vec2(5.0, 2.0) + seed.r * 13.0) - 0.5));
    float u = UV.x * n + 0.35 * (vn(UV * vec2(2.0, 6.0) + seed.b * 17.0) - 0.5) + band * 0.37;
    float h = hash2(vec2(floor(u), seed.r * 91.0 + band * 7.0));
    vec3 tint = h < 0.32 ? vec3(0.66, 0.98, 0.50)      // green wheat
              : h < 0.56 ? vec3(1.10, 0.98, 0.56)      // ripening gold
              : h < 0.78 ? vec3(0.80, 0.98, 0.62)      // clover
              : vec3(1.0, 0.88, 0.76);                 // fallow
    vec3 c = base * tint * (0.95 + 0.08 * vn(wpos.xz * 60.0));
    float fu = fract(u);
    float fb = fract(UV.y * bands);
    c *= (fu < 0.06 || fu > 0.94 || fb < 0.02 || fb > 0.98) ? 0.82 : 1.0;
    // ragged edges, dithered into the land; the whole layer fades out with distance
    vec2 e = min(UV, 1.0 - UV) * 2.0;
    float inside = smoothstep(0.0, 0.5, min(e.x, e.y) + 0.3 * (vn(wpos.xz * 45.0) - 0.5));
    float d = distance(CAMERA_POSITION_WORLD, wpos);
    float keep = inside * (1.0 - smoothstep(fade_end * 0.6, fade_end, d));
    if (keep < hash2(floor(FRAGCOORD.xy)) * 0.98 + 0.01) discard;
    ALBEDO = c * cloud_shadow(wpos) * mix(1.0, 0.7, cloud_wet);
    ROUGHNESS = 0.9;
    SPECULAR = 0.2;
}
