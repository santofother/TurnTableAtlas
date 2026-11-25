// The River Flame's farmland close up (FlameValley.cs): plots lying along the river, strips of green wheat, clover,
// ripening gold and flax, feeder canals of red Flame water across them every few plots, palm hedges, all in the
// river's own frame (COLOR.gb = the river's direction). COLOR.r is how much is farmland (the desert edge dithers out),
// COLOR.a the distance to the river (units / 2). It fades out with the camera's distance; the albedo carries it beyond.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform float fade_end = 30.0;
uniform vec3 canal = vec3(0.62, 0.28, 0.17);   // sRGB, like the palette
varying vec3 wpos;
varying vec4 col;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    col = COLOR;
}

void fragment() {
    vec2 p = vec2(wpos.x, -wpos.z);                       // blend xy
    vec2 dir = normalize(col.gb * 2.0 - 1.0 + vec2(1e-4));
    vec2 perp = vec2(-dir.y, dir.x);
    float u = dot(p, dir) + 0.02 * (vn(p * 9.0) - 0.5);
    float v = dot(p, perp) + 0.02 * (vn(p * 9.0 + 7.3) - 0.5);
    const float PU = 0.028, PV = 0.02;                    // plots ~450 x 320 m
    vec2 cell = floor(vec2(u / PU, v / PV));
    vec2 f = vec2(u / PU, v / PV) - cell;
    float h0 = hash2(cell);
    float sw = 0.25 + 0.25 * hash2(cell + 3.1);           // strips across the plot
    float strip = floor(f.y / sw);
    float h1 = hash2(cell * 1.7 + strip);
    float k = floor(h0 * 9.0 + (h1 > 0.65 ? 1.0 + floor(h0 * 3.0) : 0.0));
    k = mod(k, 9.0);
    vec3 c = vec3(0.36, 0.53, 0.17);
    c = k < 1.0 ? vec3(0.34, 0.52, 0.16) : k < 2.0 ? vec3(0.44, 0.61, 0.19) : k < 3.0 ? vec3(0.54, 0.64, 0.21) :
        k < 4.0 ? vec3(0.80, 0.70, 0.27) : k < 5.0 ? vec3(0.86, 0.75, 0.32) : k < 6.0 ? vec3(0.70, 0.62, 0.23) :
        k < 7.0 ? vec3(0.31, 0.48, 0.15) : k < 8.0 ? vec3(0.60, 0.66, 0.25) : vec3(0.90, 0.80, 0.40);
    c *= 0.93 + 0.12 * vn(p * 160.0);
    // field edges, palm hedges along the plots' long sides, feeder canals every third plot, a trunk canal along the river
    vec2 e = min(f, 1.0 - f) * vec2(PU, PV);
    c *= e.x < 0.0006 || e.y < 0.0004 ? 0.82 : 1.0;
    float hedge = step(e.y, 0.0012) * step(0.5, hash2(vec2(cell.x, cell.y * 0.37)));
    c = mix(c, vec3(0.20, 0.34, 0.12) * (0.8 + 0.4 * vn(p * 900.0)), hedge);
    float feeder = step(abs(mod(u, PU * 3.0) - PU * 1.5), 0.0011);
    float trunkc = step(abs(col.a * 2.0 - 0.34), 0.0016) + step(abs(col.a * 2.0 - 0.72), 0.0016);
    float water = clamp(feeder + trunkc, 0.0, 1.0);
    c = mix(c, vec3(0.24, 0.38, 0.14), clamp(step(abs(mod(u, PU * 3.0) - PU * 1.5), 0.0024) + step(abs(col.a * 2.0 - 0.34), 0.003) + step(abs(col.a * 2.0 - 0.72), 0.003), 0.0, 1.0) * 0.7);
    c = mix(c, canal, water);
    // date groves near the river
    float grove = (1.0 - smoothstep(0.09, 0.16, col.a * 2.0)) * step(0.45, vn(p * 300.0));
    c = mix(c, vec3(0.21, 0.35, 0.13), grove * 0.85);
    // the farmland's edge dithers into the desert; the whole layer fades out with distance
    float d = distance(CAMERA_POSITION_WORLD, wpos);
    float keep = col.r * (1.0 - smoothstep(fade_end * 0.6, fade_end, d));
    if (keep < hash2(floor(FRAGCOORD.xy)) * 0.98 + 0.01) discard;
    ALBEDO = pow(c, vec3(2.2)) * cloud_shadow(wpos);   // the palette is sRGB
    ROUGHNESS = 0.9;
    SPECULAR = 0.2;
}
