shader_type spatial;
render_mode cull_back, diffuse_lambert;
uniform vec3 base : source_color = vec3(0.86, 0.86, 0.9);
void fragment() { ALBEDO = base; ROUGHNESS = 1.0; SPECULAR = 0.0; }
