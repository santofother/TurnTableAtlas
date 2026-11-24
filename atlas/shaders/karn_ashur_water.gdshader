// Karn Ashur's lake and the water running on its aqueducts (KarnAshur.cs, card W5): deep green-blue, slow ripples for
// the sun's glint, a little sky at grazing angles.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }
float waves(vec2 p) { return vn(p + vec2(TIME * 0.4, TIME * 0.25)) * 0.6 + vn(p * 2.3 - vec2(TIME * 0.55, -TIME * 0.35)) * 0.4; }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec2 p = wpos.xz * 220.0;
    float e = 0.05, w0 = waves(p);
    vec3 n = normalize(vec3(-(waves(p + vec2(e, 0.0)) - w0) / e * 0.05, 1.0, -(waves(p + vec2(0.0, e)) - w0) / e * 0.05));
    vec3 nv = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
    float fres = pow(1.0 - clamp(dot(nv, VIEW), 0.0, 1.0), 4.0);
    vec3 deep = pow(vec3(0.09, 0.25, 0.29), vec3(2.2));
    vec3 sky = pow(vec3(0.55, 0.66, 0.72), vec3(2.2));
    ALBEDO = mix(deep, sky, fres * 0.6) * cloud_shadow(wpos);
    ROUGHNESS = 0.1;
    SPECULAR = 0.6;
    NORMAL = nv;
}
