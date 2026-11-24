// Tiny people / props (MultiMesh): vertex colour, tint slots (COLOR.a < 0.75) take INSTANCE_CUSTOM.rgb.
// INSTANCE_CUSTOM.a > 0.5 adds a little bob (walkers / cheering spectators).
shader_type spatial;
render_mode cull_back, diffuse_burley;
uniform float night_level = 0.0;
uniform float bob = 0.004;
varying vec3 tint;
varying float is_tint;

void vertex() {
    tint = INSTANCE_CUSTOM.rgb;
    is_tint = step(COLOR.a, 0.75);
    float ph = float(INSTANCE_ID) * 1.618;
    VERTEX.y += INSTANCE_CUSTOM.a * abs(sin(TIME * 11.0 + ph)) * bob / max(length(MODEL_MATRIX[1].xyz), 0.001);
}

void fragment() {
    ALBEDO = mix(COLOR.rgb, tint, is_tint);
    ROUGHNESS = 0.9;
}
