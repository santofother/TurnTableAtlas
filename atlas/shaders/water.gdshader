// Sea: colour by depth (packed into COLOR.r by the exporter), gentle animated ripples. COLOR.g < 1 marks silt-laden
// river water (Haven's River Flame: 1 - silt), drawn red-brown instead of blue; COLOR.b < 0.5 marks it flowing, with UV
// (across, downstream) in model units: the silt, the foam and the wavelets run downstream (river_flow.gdshaderinc).
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"
#include "res://shaders/river_flow.gdshaderinc"

uniform vec3 shallow : source_color = vec3(0.24, 0.64, 0.62);
uniform vec3 mid1 : source_color = vec3(0.12, 0.44, 0.58);
uniform vec3 mid2 : source_color = vec3(0.07, 0.27, 0.52);
uniform vec3 deep : source_color = vec3(0.05, 0.18, 0.42);
uniform vec3 silt_shallow : source_color = vec3(0.74, 0.36, 0.22);   // FIX(haven): the red River Flame
uniform vec3 silt_deep : source_color = vec3(0.52, 0.21, 0.13);
uniform float metres_per_unit = 200.0;   // the model scale (1:200 for Haven): the river's pattern is laid out in metres
varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1,0)), f.x), mix(hash2(i + vec2(0,1)), hash2(i + vec2(1,1)), f.x), f.y); }
float waves(vec2 p) {
    return vn(p * 2.2 + vec2(TIME * 0.18, TIME * 0.11)) * 0.6 + vn(p * 5.1 - vec2(TIME * 0.27, -TIME * 0.2)) * 0.4;
}

void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }

void fragment() {
    float d = clamp(COLOR.r, 0.0, 1.0);
    vec3 c = mix(shallow, mid1, smoothstep(0.0, 0.15, d));
    c = mix(c, mid2, smoothstep(0.15, 0.5, d));
    c = mix(c, deep, smoothstep(0.5, 1.0, d));
    float silt = clamp(1.0 - COLOR.g, 0.0, 1.0);
    vec3 red = mix(silt_shallow, silt_deep, smoothstep(0.0, 0.4, d)) * (0.94 + 0.12 * vn(wpos.xz * 0.6 + vec2(TIME * 0.05, 0.0)));
    c = mix(c, red, silt);
    ALBEDO = c * cloud_shadow(wpos);
    float e = 0.05;
    float h0 = waves(wpos.xz);
    vec3 nw = normalize(vec3(-(waves(wpos.xz + vec2(e, 0.0)) - h0) / e * (0.06 + 0.1 * cloud_wet), 1.0, -(waves(wpos.xz + vec2(0.0, e)) - h0) / e * (0.06 + 0.1 * cloud_wet)));
    NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
    ROUGHNESS = mix(0.14, 0.55, silt);   // FIX(haven): muddy water barely mirrors the sky
    SPECULAR = mix(0.55, 0.12, silt);
    if (silt > 0.5 && COLOR.b < 0.5) {   // the flowing river
        vec3 alb, nw2; float rough;
        river_flow(UV * metres_per_unit, smoothstep(0.04, 0.38, d), TIME, mix(silt_shallow, silt_deep, 0.35), wpos.xz * metres_per_unit, alb, nw2, rough);
        vec3 nv2 = normalize((VIEW_MATRIX * vec4(nw2, 0.0)).xyz);
        float fres = pow(1.0 - clamp(dot(nv2, VIEW), 0.0, 1.0), 4.0);
        ALBEDO = mix(alb, vec3(0.32, 0.42, 0.5), fres * 0.12) * cloud_shadow(wpos);   // a little sky at grazing angles
        NORMAL = nv2;
        ROUGHNESS = rough;
        SPECULAR = 0.12;
    }
}
