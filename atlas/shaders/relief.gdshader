// The Known World relief (WorldMap.cs): KnownWorld.blend's ground baked unlit (albedo_tex, tools/bake_known_world.py)
// on a grid displaced by its elevation (height_tex, blend units at the blend's 15x exaggeration). The sea is the
// flat surface at 0 like the blend's SEA_Surface: its colour (water over seabed) is in the bake, it gets ripples
// and a sun glint here. Normals come from the height texture per pixel, so the relief stays crisp between vertices.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;   // blend units, sea < 0
uniform vec2 size = vec2(685.0, 357.0);                          // world units the mesh spans (x, z)
uniform vec2 texel = vec2(0.000292, 0.00056);
uniform float land_lift = 0.0;                                   // keeps a hair of land above the water line
uniform vec4 hole = vec4(2.0);                                   // uv rect (u0, v0, u1, v1) a hero patch covers (W5)
uniform vec4 hole2 = vec4(2.0);                                  // a second one: an estate's patch (Landric's villa)
uniform vec4 hole3 = vec4(2.0);                                  // a second basin: Haven's patch (FIX(haven))

varying vec3 wpos;
varying float hraw;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1,0)), f.x), mix(hash2(i + vec2(0,1)), hash2(i + vec2(1,1)), f.x), f.y); }

float land(vec2 uv) { return max(textureLod(height_tex, uv, 0.0).r, 0.0); }

void vertex() {
    hraw = textureLod(height_tex, UV, 0.0).r;
    VERTEX.y = hraw > 0.0 ? hraw + land_lift : 0.0;
    // vertices under a hero patch sink out of sight; the patch meets the ones on the rect's edge exactly
    if (UV.x > hole.x && UV.x < hole.z && UV.y > hole.y && UV.y < hole.w) VERTEX.y = -1.0;
    if (UV.x > hole2.x && UV.x < hole2.z && UV.y > hole2.y && UV.y < hole2.w) VERTEX.y = -1.0;
    if (UV.x > hole3.x && UV.x < hole3.z && UV.y > hole3.y && UV.y < hole3.w) VERTEX.y = -1.0;
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    float h = textureLod(height_tex, UV, 0.0).r;
    vec3 c = texture(albedo_tex, UV).rgb;
    vec3 n;
    if (h > 0.0) {
        // slope from the height texture (central differences, world units)
        float hx = land(UV + vec2(texel.x, 0.0)) - land(UV - vec2(texel.x, 0.0));
        float hz = land(UV + vec2(0.0, texel.y)) - land(UV - vec2(0.0, texel.y));
        n = normalize(vec3(-hx / (2.0 * texel.x * size.x), 1.0, -hz / (2.0 * texel.y * size.y)));
        // a little ground grain for close-ups
        c *= mix(0.94, 1.05, vn(wpos.xz * 3.0) * 0.6 + vn(wpos.xz * 11.0) * 0.4);
        ROUGHNESS = mix(0.9, 0.5, cloud_wet);
        SPECULAR = 0.25;
        // FIX(S30): tidal pools and reed beds in the broken lowlands west of Corivessa Bay.
        vec2 marsh_xy = vec2(wpos.x, -wpos.z) - vec2(129.4, 162.3);
        float shore = 1.0 - smoothstep(0.58, 1.0, length(marsh_xy / vec2(7.2, 2.9)));
        if (shore > 0.0) {
            float lowland = shore * (1.0 - smoothstep(0.14, 0.40, h));
            vec2 p = marsh_xy * vec2(2.7, 6.4);
            float channels = vn(p + 2.3 * vn(p * 0.38)) + 0.18 * vn(p * 3.7);
            float wet = lowland * smoothstep(0.56, 0.65, channels);
            c = mix(c, vec3(0.17, 0.18, 0.073), lowland * 0.46);
            c = mix(c, vec3(0.080, 0.155, 0.146), wet * 0.85);
            ROUGHNESS = mix(ROUGHNESS, 0.32, wet);
            SPECULAR = mix(SPECULAR, 0.55, wet);
        }
        c *= mix(1.0, 0.7, cloud_wet);
    } else {
        // sea surface: slow ripples for the glint
        vec2 p = wpos.xz * 1.6;
        float e = 0.05;
        float w0 = vn(p + vec2(TIME * 0.05, TIME * 0.03)) * 0.6 + vn(p * 2.3 - vec2(TIME * 0.07, -TIME * 0.05)) * 0.4;
        float wx = vn(p + vec2(e, 0.0) + vec2(TIME * 0.05, TIME * 0.03)) * 0.6 + vn((p + vec2(e, 0.0)) * 2.3 - vec2(TIME * 0.07, -TIME * 0.05)) * 0.4;
        float wz = vn(p + vec2(0.0, e) + vec2(TIME * 0.05, TIME * 0.03)) * 0.6 + vn((p + vec2(0.0, e)) * 2.3 - vec2(TIME * 0.07, -TIME * 0.05)) * 0.4;
        float k = 0.035 + 0.06 * cloud_wet;
        n = normalize(vec3(-(wx - w0) / e * k, 1.0, -(wz - w0) / e * k));
        ROUGHNESS = 0.3;
        SPECULAR = 0.5;
    }
    ALBEDO = c * cloud_shadow(wpos);
    NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
}
