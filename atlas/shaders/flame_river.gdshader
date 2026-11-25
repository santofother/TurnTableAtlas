// The River Flame on the Known World (FlameValley's reaches and Haven's patch, Basin.cs): its silt-red water moving
// downstream (river_flow.gdshaderinc). UV = (across, downstream) in world units; COLOR.r = 0 / 1 at the two banks.
shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"
#include "res://shaders/river_flow.gdshaderinc"

uniform vec4 silt : source_color = vec4(0.66, 0.29, 0.17, 1.0);
uniform float metres_per_unit = 2682.0;   // the miniature's horizontal scale: the pattern is laid out in metres
varying vec3 wpos;

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec3 alb, nw; float rough;
    float bank = 1.0 - abs(COLOR.r * 2.0 - 1.0);
    river_flow(UV * metres_per_unit, bank, TIME, silt.rgb, wpos.xz * metres_per_unit, alb, nw, rough);
    vec3 nv = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
    float fres = pow(1.0 - clamp(dot(nv, VIEW), 0.0, 1.0), 4.0);
    ALBEDO = mix(alb, vec3(0.32, 0.42, 0.5), fres * 0.12) * cloud_shadow(wpos);
    NORMAL = nv;
    ROUGHNESS = rough;
    SPECULAR = 0.12;
}
