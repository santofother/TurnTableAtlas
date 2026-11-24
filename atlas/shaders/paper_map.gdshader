// The painted Caelora Geography map lying flat on its board (WorldMap.cs): paper with a faint grain and a soft
// sheen, lit by the Atlas sun, with cloud shadows and rain darkening from the shared weather.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D map_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1,0)), f.x), mix(hash2(i + vec2(0,1)), hash2(i + vec2(1,1)), f.x), f.y); }

void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }

void fragment() {
    vec3 c = texture(map_tex, UV).rgb;
    float grain = vn(wpos.xz * 9.0) * 0.5 + vn(wpos.xz * 31.0) * 0.5;
    c *= mix(0.95, 1.04, grain);
    ALBEDO = c * cloud_shadow(wpos) * mix(1.0, 0.78, cloud_wet);
    ROUGHNESS = mix(0.82, 0.4, cloud_wet);
    SPECULAR = 0.3;
    // the paper is not perfectly flat: a long, low undulation catches the light
    vec2 g = vec2(vn(wpos.xz * 0.05 + 3.1) - 0.5, vn(wpos.xz * 0.05 + 7.7) - 0.5) * 0.06;
    NORMAL = normalize((VIEW_MATRIX * vec4(normalize(vec3(g.x, 1.0, g.y)), 0.0)).xyz);
}
