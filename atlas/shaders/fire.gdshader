shader_type spatial;
render_mode unshaded, cull_disabled;
uniform float strength = 4.0;
void fragment() {
    float f = 0.85 + 0.15 * sin(TIME * 17.0 + FRAGCOORD.x * 0.01) * sin(TIME * 7.3);
    ALBEDO = vec3(1.0, 0.45, 0.1) * strength * f;
}
