// W1: the war table under the world map, and its carved frame. Procedural walnut: planks along X with per-plank
// tint, long grain streaks and fine pores, all from world position so any box mesh can use it.
// vignette > 0 (the table top): the wood fades into the dark room with distance from the map, like a lamp-lit table.
shader_type spatial;
render_mode cull_back;

uniform vec3 tint : source_color = vec3(0.36, 0.21, 0.12);
uniform vec3 dark : source_color = vec3(0.13, 0.07, 0.04);
uniform float plank = 26.0;        // plank width (world units)
uniform float grain_scale = 1.0;   // >1 = finer grain (the frame is small next to the table)
uniform float roughness_base = 0.55;
uniform float vignette = 0.0;
uniform vec2 centre;               // map centre (world xz)
uniform vec2 half_size = vec2(350.0, 180.0);
uniform vec3 room : source_color = vec3(0.025, 0.017, 0.012);

varying vec3 wpos;
varying vec3 wnrm;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; } return s; }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
    // run the grain along X on top / Z-facing sides, along Z on X-facing sides
    vec2 p = abs(wnrm.x) > 0.7 ? vec2(wpos.z, wpos.y) : (abs(wnrm.y) > 0.7 ? vec2(wpos.x, wpos.z) : vec2(wpos.x, wpos.y));
    p *= grain_scale;
    float row = floor(p.y / plank);
    float seam = smoothstep(0.0, 0.012, abs(fract(p.y / plank) - 0.5) * 2.0 - 0.985) ;   // 1 only on the seam line
    float plank_tint = hash(vec2(row, 7.0));
    vec2 g = vec2(p.x * 0.012 + row * 13.0, p.y * 0.55);
    float streak = fbm(g + vec2(fbm(g * 0.7) * 2.5, 0.0));
    float rings = 0.5 + 0.5 * sin((p.y + fbm(vec2(p.x * 0.01, row)) * 18.0) * 1.7);
    float pores = vnoise(vec2(p.x * 0.6, p.y * 9.0));
    float w = clamp(streak * 0.75 + rings * 0.18 + plank_tint * 0.25 - 0.12, 0.0, 1.0);
    vec3 col = mix(dark, tint, w) * mix(0.82, 1.06, pores);
    col *= 1.0 - seam * 0.55;

    float rough = roughness_base + (1.0 - w) * 0.15 + seam * 0.2;
    if (vignette > 0.0) {
        vec2 d = (wpos.xz - centre) / half_size;
        float r = length(d * vec2(1.0, 0.85));
        float lit = 1.0 - smoothstep(1.05, 1.05 + 2.2 * vignette, r);
        col = mix(room, col, lit * lit);
        rough = mix(1.0, rough, lit);
    }
    ALBEDO = col;
    ROUGHNESS = rough;
    SPECULAR = 0.35;
}
