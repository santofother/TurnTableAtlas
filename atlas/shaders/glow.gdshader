// Billboard glow sprites for night lights (MultiMesh). INSTANCE_CUSTOM: x = kind (0 window, 1 lamp, 2 torch,
// 3 lighthouse), y = light-up order (windows), z = strength.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;

uniform float window_level = 0.0;
uniform float lamp_level = 0.0;
uniform vec3 tint : source_color = vec3(1.0, 0.6, 0.25);
varying float vis;

void vertex() {
    float kind = INSTANCE_CUSTOM.x;
    float on = kind < 0.5 ? step(INSTANCE_CUSTOM.y, window_level) : lamp_level;
    float flick = kind > 1.5 ? 0.85 + 0.15 * sin(TIME * 13.0 + float(INSTANCE_ID) * 1.7) : 1.0;
    vis = on * INSTANCE_CUSTOM.z * flick;
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
    MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0, 0, 0), vec4(0, length(MODEL_MATRIX[1].xyz), 0, 0), vec4(0, 0, length(MODEL_MATRIX[2].xyz), 0), vec4(0, 0, 0, 1));
}

void fragment() {
    float r = length(UV - vec2(0.5)) * 2.0;
    float a = pow(clamp(1.0 - r, 0.0, 1.0), 2.2) * vis;
    ALBEDO = tint * a * 2.5;
    if (a < 0.002) discard;
}
