// Instanced buildings and trees (Atlas.Core.InstanceTable): the prototype's vertex colour says how a face is coloured
// (a = 1: the instance tint x rgb; a = 0: rgb itself; a = 0.5: a window, lit while the instance's order < night_level).
// INSTANCE_CUSTOM = (linear tint rgb, window order). The same painted look as painted.gdshader.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform float night_level = 0.0;
uniform float window_glow = 5.0;
uniform vec3 window_color : source_color = vec3(1.0, 0.62, 0.30);

varying vec3 wpos;
varying vec4 inst;

float hash3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x) {
    vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash3(i), hash3(i + vec3(1,0,0)), f.x), mix(hash3(i + vec3(0,1,0)), hash3(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(hash3(i + vec3(0,0,1)), hash3(i + vec3(1,0,1)), f.x), mix(hash3(i + vec3(0,1,1)), hash3(i + vec3(1,1,1)), f.x), f.y), f.z);
}

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    inst = INSTANCE_CUSTOM;
}

void fragment() {
    float n = mix(0.92, 1.06, smoothstep(0.3, 0.7, vnoise(wpos * 3.0) * 0.6 + vnoise(wpos * 7.0) * 0.4));
    float tinted = step(0.75, COLOR.a);
    vec3 base = mix(COLOR.rgb, inst.rgb * COLOR.rgb, tinted);
    ALBEDO = base * n * cloud_shadow(wpos) * mix(1.0, 0.72, cloud_wet);
    ROUGHNESS = mix(0.8, 0.3, cloud_wet);
    SPECULAR = 0.3;
    float is_window = step(0.25, COLOR.a) * (1.0 - tinted);
    EMISSION = window_color * window_glow * is_window * step(inst.a, night_level);
}
