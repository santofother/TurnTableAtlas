// Karn Ashur's sandstone (KarnAshur.cs, card W5): houses, towers, walls, ziggurats, aqueducts and the temple. Colour
// comes from the vertex or instance colour (linear). Houses (windows on) are unit boxes in a MultiMesh with their size
// in INSTANCE_CUSTOM.xyz and a seed in .w: they get rows of small windows, and after dark some of them are lit. Where
// the windows are too small on screen to draw, the walls take their average shade and glow instead.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform bool windows = false;
uniform float night = 0.0;
uniform float sink = 0.003;        // how far a house reaches below the ground

varying vec3 wpos;
varying vec3 lpos;
varying vec3 lnrm;
varying vec4 inst;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    inst = windows ? INSTANCE_CUSTOM : vec4(1.0, 1.0, 1.0, 0.0);
    lpos = VERTEX * inst.xyz;
    lnrm = NORMAL;
}

void fragment() {
    vec3 col = COLOR.rgb;
    vec3 n = normalize(lnrm);
    col *= 0.9 + 0.12 * vn(wpos.xz * 2400.0 + wpos.y * 900.0) + 0.06 * vn(wpos.xz * 300.0);
    vec3 glow = vec3(0.0);
    if (windows) {
        float up = lpos.y + inst.y * 0.5 - sink;            // height above the ground
        if (n.y > 0.5) col *= 1.08;                         // sunlit flat roofs
        else if (n.y > -0.5) {
            col *= mix(0.8, 1.0, smoothstep(0.0, 0.0025, up));
            vec2 f = vec2(abs(n.x) > 0.5 ? lpos.z : lpos.x, up);
            vec2 cell = f / vec2(0.0019, 0.0021);
            vec2 id = floor(cell), fr = fract(cell);
            float half_w = (abs(n.x) > 0.5 ? inst.z : inst.x) * 0.5;
            float inside = step(abs(f.x) + 0.0008, half_w) * step(0.0018, up) * step(up, inst.y - sink - 0.0012);
            float win = inside * step(0.3, fr.x) * step(fr.x, 0.7) * step(0.3, fr.y) * step(fr.y, 0.78);
            float lit = step(hash2(id + vec2(inst.w * 61.0, n.x * 7.0 + n.z * 13.0)), 0.38);
            float detail = 1.0 - smoothstep(0.35, 0.8, max(fwidth(cell.x), fwidth(cell.y)));
            col *= mix(0.94, 1.0 - 0.5 * win, detail);
            glow = vec3(1.0, 0.6, 0.26) * mix(0.06, win * lit, detail) * night * 2.4;
        }
    }
    ALBEDO = col * mix(1.0, 0.75, cloud_wet) * cloud_shadow(wpos);
    ROUGHNESS = mix(0.9, 0.55, cloud_wet);
    SPECULAR = 0.3;
    EMISSION = glow;
}
