// The fires of Karn Ashur (KarnAshur.cs, card W5): the flame on the ziggurat, the First Flame on the great peak and the
// gate braziers. An upright quad that turns to the camera, a flickering tongue of fire, added onto the scene.
shader_type spatial;
render_mode blend_add, cull_disabled, unshaded, depth_draw_never, shadows_disabled;

uniform float strength = 1.0;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(normalize(cross(vec3(0.0, 1.0, 0.0), INV_VIEW_MATRIX[2].xyz)), 0.0),
        vec4(0.0, 1.0, 0.0, 0.0), vec4(normalize(cross(INV_VIEW_MATRIX[0].xyz, vec3(0.0, 1.0, 0.0))), 0.0), MODEL_MATRIX[3]);
}

void fragment() {
    float seed = fract(NODE_POSITION_WORLD.x * 13.7 + NODE_POSITION_WORLD.z * 5.3) * 40.0;
    float y = 1.0 - UV.y;                                   // 0 at the base
    float t = TIME * 2.6 + seed;
    float sway = (vn(vec2(y * 2.5 - t, seed)) - 0.5) * 0.35 * y;
    float x = abs(UV.x - 0.5 - sway) * 2.0;
    float width = mix(0.85, 0.05, pow(y, 0.8)) * (0.85 + 0.3 * vn(vec2(t * 1.3, seed)));
    float body = (1.0 - smoothstep(width * 0.55, width, x)) * smoothstep(0.0, 0.12, y);
    body *= 1.0 - smoothstep(0.55, 1.0, y + 0.25 * vn(vec2(UV.x * 6.0, y * 3.0 - t * 1.6)));
    float core = (1.0 - smoothstep(0.0, width * 0.5, x)) * (1.0 - smoothstep(0.1, 0.55, y));
    ALBEDO = mix(vec3(1.0, 0.36, 0.06), vec3(1.0, 0.86, 0.52), core) * strength * 2.2;
    ALPHA = clamp(body, 0.0, 1.0);
}
