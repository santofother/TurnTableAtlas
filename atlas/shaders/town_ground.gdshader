// A town miniature's own ground on the Known World (Town.cs): the package's baked terrain albedo laid on the relief.
// Its colours are graded towards the map's own round the town (fields take the region's tones, as Karn Ashur's ring
// takes the desert's), and along a rounded, ragged rim (TownSite.Rim) it hands over to the map's colour and the
// relief's light, well inside the square, so the square cannot be seen.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D town_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;   // the relief's heights, for its own shading
uniform vec2 world_min;     // map xz of the albedo's top-left
uniform vec2 world_size;
uniform vec2 centre;        // town centre (x, z)
uniform float half_size;    // half the model's square (blend units)
uniform float grade_core = 0.3;    // how far the walled town's ground takes the region's colours
uniform float grade_country = 0.95; // how far its countryside does
uniform vec2 hand_over = vec2(0.6, 0.84);   // the rim (TownSite.Rim) over which the map's colour takes over

varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float fbm_rim(vec2 q) { return vn(q * 3.1 + vec2(7.3, 1.9)) * 0.65 + vn(q * 7.7 + vec2(2.2, 5.4)) * 0.35; }

// TownSite.Rim: a rounded square, ragged by noise (q in half sizes)
float rim_of(vec2 q) {
    float r = pow(pow(abs(q.x), 4.0) + pow(abs(q.y), 4.0), 0.25);
    return r + 0.1 * (fbm_rim(q) - 0.5) * min(1.0, r * 2.0);
}

void fragment() {
    vec2 q = vec2(wpos.x - centre.x, -(wpos.z - centre.y)) / half_size;   // +x east, +y north, in half sizes
    float rim = rim_of(q);
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 base = texture(albedo_tex, map_uv).rgb * mix(0.94, 1.05, vn(wpos.xz * 3.0) * 0.6 + vn(wpos.xz * 11.0) * 0.4);
    // the S30 marsh west of Corivessa Bay, exactly as relief.gdshader paints it, so the hand-over cannot be seen
    vec2 marsh_xy = vec2(wpos.x, -wpos.z) - vec2(129.4, 162.3);
    float shore = 1.0 - smoothstep(0.58, 1.0, length(marsh_xy / vec2(7.2, 2.9)));
    if (shore > 0.0) {
        float lowland = shore * (1.0 - smoothstep(0.14, 0.40, textureLod(height_tex, map_uv, 0.0).r));
        vec2 p = marsh_xy * vec2(2.7, 6.4);
        float channels = vn(p + 2.3 * vn(p * 0.38)) + 0.18 * vn(p * 3.7);
        float wet = lowland * smoothstep(0.56, 0.65, channels);
        base = mix(base, vec3(0.17, 0.18, 0.073), lowland * 0.46);
        base = mix(base, vec3(0.080, 0.155, 0.146), wet * 0.85);
    }
    // the town's ground graded towards the region's colour: its own pattern, the map's tones
    vec3 own = texture(town_tex, UV).rgb;
    vec3 own_mean = max(textureLod(town_tex, vec2(0.5), 14.0).rgb, vec3(0.02));
    vec3 region = textureLod(albedo_tex, map_uv, 3.0).rgb;
    vec3 graded = clamp(own * region / own_mean, 0.0, 1.0);
    vec3 col = mix(own, graded, mix(grade_core, grade_country, smoothstep(0.22, 0.55, rim)));
    float edge = smoothstep(hand_over.x, hand_over.y, rim);
    col = mix(col, base, edge);
    // towards the edge, light the ground as relief.gdshader lights the map
    vec2 texel = 1.0 / vec2(textureSize(height_tex, 0));
    float hx = max(textureLod(height_tex, map_uv + vec2(texel.x, 0.0), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(texel.x, 0.0), 0.0).r, 0.0);
    float hz = max(textureLod(height_tex, map_uv + vec2(0.0, texel.y), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(0.0, texel.y), 0.0).r, 0.0);
    vec3 rn = normalize(vec3(-hx / (2.0 * texel.x * world_size.x), 1.0, -hz / (2.0 * texel.y * world_size.y)));
    vec3 own_n = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
    NORMAL = normalize((VIEW_MATRIX * vec4(normalize(mix(own_n, rn, edge)), 0.0)).xyz);
    ALBEDO = col * cloud_shadow(wpos) * mix(1.0, 0.7, cloud_wet);
    ROUGHNESS = mix(0.92, mix(0.9, 0.5, cloud_wet), edge);
    SPECULAR = mix(0.2, 0.25, edge);
}
