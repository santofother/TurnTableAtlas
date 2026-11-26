// A town miniature's own ground on the Known World (Town.cs): the package's baked terrain albedo laid on the relief,
// handing over to the map's colour and the relief's light towards the square's edge, so the square cannot be seen.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D town_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;   // the relief's heights, for its own shading
uniform vec2 world_min;     // map xz of the albedo's top-left
uniform vec2 world_size;
uniform vec2 centre;        // town centre (x, z)
uniform float half_size;    // half the model's square (blend units)
uniform float blend_from = 0.62;   // the town's own colours inside this share of the half size

varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
    vec2 q = vec2(wpos.x - centre.x, -(wpos.z - centre.y)) / half_size;   // +x east, +y north, in half sizes
    float edge = smoothstep(blend_from, 0.97, max(abs(q.x), abs(q.y)));
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 base = texture(albedo_tex, map_uv).rgb * mix(0.94, 1.05, vn(wpos.xz * 3.0) * 0.6 + vn(wpos.xz * 11.0) * 0.4);
    vec3 town = texture(town_tex, UV).rgb;
    vec3 col = mix(town, base, edge);
    // towards the edge, light the ground as relief.gdshader lights the map
    vec2 texel = 1.0 / vec2(textureSize(height_tex, 0));
    float hx = max(textureLod(height_tex, map_uv + vec2(texel.x, 0.0), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(texel.x, 0.0), 0.0).r, 0.0);
    float hz = max(textureLod(height_tex, map_uv + vec2(0.0, texel.y), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(0.0, texel.y), 0.0).r, 0.0);
    vec3 rn = normalize(vec3(-hx / (2.0 * texel.x * world_size.x), 1.0, -hz / (2.0 * texel.y * world_size.y)));
    vec3 own = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
    NORMAL = normalize((VIEW_MATRIX * vec4(normalize(mix(own, rn, edge)), 0.0)).xyz);
    ALBEDO = col * cloud_shadow(wpos) * mix(1.0, 0.7, cloud_wet);
    ROUGHNESS = mix(0.92, mix(0.9, 0.5, cloud_wet), edge);
    SPECULAR = mix(0.2, 0.25, edge);
}
