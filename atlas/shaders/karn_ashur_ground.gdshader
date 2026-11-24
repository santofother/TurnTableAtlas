// Karn Ashur's hero patch (KarnAshur.cs, card W5): the basin's ground at the Known World relief's scale. Normals come
// from the patch's own height texture per pixel, as in relief.gdshader. Colour: dark High Dunes rock with warm strata,
// snow on the high northern wall, green on the valley floor and the talus, and the ground layout painted by
// KarnAshurSite.PaintLayout (R water, G field id, B paving, A road). Towards its edge the patch fades into the baked
// map, so it meets the relief without a seam.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D height_tex : filter_linear, repeat_disable;            // patch heights (blend units), row 0 north
uniform sampler2D layout_lin : filter_linear_mipmap, repeat_disable;     // the layout, for water, paving and roads
uniform sampler2D layout_near : filter_nearest_mipmap, repeat_disable;   // the same texture: field ids must not blend
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;  // the baked map
uniform vec2 patch_min;      // world xz of the patch's north-west corner
uniform vec2 patch_size;
uniform vec2 world_min;      // world xz of the map's north-west corner
uniform vec2 world_size;
uniform vec2 centre;         // the basin centre, world xz
uniform float fine_half = 1.35;
uniform vec2 texel = vec2(0.0009765625);
uniform float metres_per_unit = 1072.9;
uniform float floor_m = 2900.0;
uniform float blend_in = 1.7;
uniform float blend_out = 2.7;

varying vec3 wpos;

float hash1(float n) { return fract(sin(n * 12.9898) * 43758.5453); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }
vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }

vec3 crop(float id) {
    float k = mod(id, 7.0);
    vec3 c = k < 1.0 ? vec3(0.38, 0.55, 0.17) : k < 2.0 ? vec3(0.58, 0.62, 0.21) : k < 3.0 ? vec3(0.78, 0.64, 0.27)
           : k < 4.0 ? vec3(0.44, 0.48, 0.20) : k < 5.0 ? vec3(0.28, 0.45, 0.15) : k < 6.0 ? vec3(0.70, 0.55, 0.25)
           : vec3(0.50, 0.58, 0.22);
    return lin(c) * (0.86 + 0.28 * hash1(id));
}

float land(vec2 uv) { return textureLod(height_tex, uv, 0.0).r; }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec2 puv = (wpos.xz - patch_min) / patch_size;
    float hx = land(puv + vec2(texel.x, 0.0)) - land(puv - vec2(texel.x, 0.0));
    float hz = land(puv + vec2(0.0, texel.y)) - land(puv - vec2(0.0, texel.y));
    vec3 n = normalize(vec3(-hx / (2.0 * texel.x * patch_size.x), 1.0, -hz / (2.0 * texel.y * patch_size.y)));
    float hm = wpos.y * metres_per_unit;
    // rock detail: small bumps everywhere, stronger on the steep faces
    float steep = 1.0 - smoothstep(0.25, 0.6, n.y);
    vec2 q = wpos.xz * 38.0;
    float b0 = vn(q), bx = vn(q + vec2(0.07, 0.0)), bz = vn(q + vec2(0.0, 0.07));
    n = normalize(n + vec3(bx - b0, 0.0, bz - b0) / 0.07 * (0.03 + 0.1 * steep) * (1.0 - smoothstep(blend_in, blend_out, length(wpos.xz - centre))));
    float r = length(wpos.xz - centre);
    float g1 = vn(wpos.xz * 45.0), g2 = vn(wpos.xz * 190.0), g3 = vn(wpos.xz * 9.0);

    // rock: dark massif with warm sandstone bands, darker in the steepest faces
    float strata = 0.5 + 0.5 * sin(hm * 0.011 + g3 * 6.0 + g1 * 2.0);
    vec3 rock = mix(lin(vec3(0.33, 0.26, 0.21)), lin(vec3(0.60, 0.44, 0.30)), clamp(0.25 + strata * 0.4 + g2 * 0.3 + (g3 - 0.5) * 0.4, 0.0, 1.0));
    rock *= mix(1.0, 0.78, smoothstep(0.12, 0.03, n.y));
    rock *= mix(1.0, mix(0.72, 1.1, vn(vec2((wpos.x - wpos.z) * 42.0, wpos.y * 2.5))), steep);   // streaks down the walls
    // green floor and talus, scrub higher up
    float veg = (1.0 - smoothstep(floor_m + 120.0, floor_m + 420.0 + 250.0 * g3, hm)) * smoothstep(0.18, 0.55, n.y + 0.25 * g2);
    veg *= 1.0 - smoothstep(1.2, 1.5, r);                   // inside the basin only
    vec3 meadow = lin(vec3(0.36, 0.47, 0.19)) * (0.86 + 0.28 * g1);
    vec3 scrub = lin(vec3(0.24, 0.30, 0.14)) * (0.8 + 0.4 * g2);
    vec3 col = mix(rock, mix(scrub, meadow, smoothstep(floor_m + 260.0, floor_m + 60.0, hm)), veg);
    // snow on the high wall: thick on ledges, streaked on the faces
    float line = 4300.0 + 200.0 * g3 - 140.0 * g1;
    float snow = smoothstep(line, line + 220.0, hm) * smoothstep(0.02, 0.2, n.y + 0.12 * g2 - 0.06);
    col = mix(col, lin(vec3(0.93, 0.94, 0.96)), snow);

    // the ground layout on the valley floor
    float water = 0.0;
    vec2 luv = (wpos.xz - centre + fine_half) / (2.0 * fine_half);
    if (luv.x > 0.0 && luv.y > 0.0 && luv.x < 1.0 && luv.y < 1.0) {
        vec4 L = texture(layout_lin, luv);
        float field = floor(texture(layout_near, luv).g * 255.0 + 0.5);
        float low = 1.0 - smoothstep(floor_m + 110.0, floor_m + 200.0, hm);   // crops and roads stay on the valley floor
        if (low < 0.5) field = 0.0;
        if (field > 0.5 && field < 200.5) {
            vec3 c = crop(field);
            float a = hash1(field + 3.0) * 3.14159;
            float f = dot(wpos.xz, vec2(cos(a), sin(a))) * 2600.0;
            c *= 1.0 + 0.12 * sin(f) * (1.0 - smoothstep(0.8, 2.5, fwidth(f)));
            col = c;
        } else if (field > 200.5) {
            col = lin(vec3(0.19, 0.31, 0.12)) * (0.75 + 0.5 * vn(wpos.xz * 1100.0));
        }
        vec3 pave = lin(vec3(0.69, 0.56, 0.40)) * (0.88 + 0.2 * g2 + 0.1 * vn(wpos.xz * 900.0));
        vec3 road = lin(vec3(0.80, 0.70, 0.54)) * (0.92 + 0.12 * g2);
        col = mix(col, pave, L.b);
        col = mix(col, road, L.a * max(low, step(r, 0.0) + smoothstep(1.2, 1.3, r)));
        water = L.r;
        col = mix(col, lin(vec3(0.13, 0.30, 0.33)), water);
    }

    // into the baked map near the edge
    vec3 baked = texture(albedo_tex, (wpos.xz - world_min) / world_size).rgb;
    col = mix(col, baked * mix(0.85, 1.05, g2), smoothstep(blend_in, blend_out, r));
    col *= mix(0.95, 1.04, vn(wpos.xz * 3.0) * 0.6 + vn(wpos.xz * 11.0) * 0.4);

    ROUGHNESS = mix(mix(0.92, 0.5, cloud_wet), 0.12, water);
    SPECULAR = mix(0.25, 0.55, water);
    col *= mix(1.0, 0.72, cloud_wet * (1.0 - water));
    ALBEDO = col * cloud_shadow(wpos);
    NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
}
