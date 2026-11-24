// Karn Ashur's waterfalls and the spray at their feet (KarnAshur.cs, card W5). Falls: a ribbon down the cliff, UV.x
// across it and UV.y from the lip (0) to the foot (1), with streaks running down. Mist: a camera-facing puff.
shader_type spatial;
render_mode blend_mix, cull_disabled, unshaded, depth_draw_never, shadows_disabled;

uniform bool mist = false;
uniform float daylight = 1.0;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    if (mist) {
        MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
    }
}

void fragment() {
    float lightk = 0.18 + 0.82 * daylight;
    float seed = fract(NODE_POSITION_WORLD.x * 7.31 + NODE_POSITION_WORLD.z * 3.17) * 50.0;
    if (!mist) {
        float x = UV.x, y = UV.y;
        float s = vn(vec2(x * 9.0 + seed, y * 7.0 - TIME * 1.7)) * 0.6 + vn(vec2(x * 23.0 + seed, y * 16.0 - TIME * 2.9)) * 0.4;
        float edge = smoothstep(0.0, 0.38, x) * smoothstep(1.0, 0.62, x);
        float lip = smoothstep(0.0, 0.04, y);
        ALBEDO = mix(vec3(0.58, 0.70, 0.76), vec3(0.96, 0.98, 1.0), smoothstep(0.3, 0.8, s)) * lightk;
        float gusts = 0.65 + 0.35 * vn(vec2(seed, y * 3.0 - TIME * 0.6));
        ALPHA = edge * lip * gusts * clamp(0.1 + 0.9 * s, 0.0, 1.0) * 0.8;
    } else {
        vec2 d = UV - 0.5;
        float rr = length(d) * 2.0;
        float puff = vn(UV * 3.5 + vec2(seed, -TIME * 0.35)) * 0.6 + vn(UV * 7.0 + vec2(-TIME * 0.2, seed)) * 0.4;
        ALBEDO = vec3(0.90, 0.93, 0.95) * lightk;
        ALPHA = (1.0 - smoothstep(0.0, 1.0, rr)) * (0.2 + 0.4 * puff) * 0.35;
    }
}
