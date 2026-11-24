// A metropolis's basin on the Known World (Basin.cs): the package's own painted ground on the plinth, then a ring of
// red rock, sand and desert that hands over to the baked map's colour at the patch's edge.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D basin_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec2 world_min;     // map xz of the albedo's top-left
uniform vec2 world_size;
uniform vec2 centre;        // the settlement (x, z)
uniform float half_size;    // half the plinth (blend units)
uniform float blend_out;    // the map's own colour from here (box distance)
uniform float metres_per_unit = 1072.9;

varying vec3 wpos;
varying vec3 wnrm;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p) { return vn(p) * 0.55 + vn(p * 2.1 + 3.1) * 0.3 + vn(p * 4.3 + 7.7) * 0.15; }
vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
    vec2 l = vec2(wpos.x - centre.x, -(wpos.z - centre.y));          // +x east, +y north
    vec2 q = l / half_size;                                           // plinth halves
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 base = texture(albedo_tex, map_uv).rgb;
    float m = wpos.y * metres_per_unit;                               // true metres
    float slope = 1.0 - clamp(wnrm.y, 0.0, 1.0);
    // the ring: desert and sand at the feet, red rock on the steep and the high ground, snow on the highest
    float n = fbm(l * 9.0);
    vec3 desert = mix(lin(vec3(0.80, 0.62, 0.42)), lin(vec3(0.72, 0.54, 0.37)), smoothstep(0.35, 0.65, n));
    vec3 sand = mix(lin(vec3(0.92, 0.67, 0.38)), lin(vec3(0.84, 0.56, 0.30)), 0.5 + 0.5 * sin(dot(l, vec2(0.78, 0.62)) * 420.0 + 6.0 * n));
    vec3 rock = mix(lin(vec3(0.66, 0.36, 0.24)), lin(vec3(0.78, 0.50, 0.34)), 0.5 + 0.5 * sin(m / 70.0 + 5.0 * n));
    vec3 col = mix(desert, sand, smoothstep(700.0, 900.0, m) * (1.0 - smoothstep(1300.0, 1700.0, m)) * 0.7);
    col = mix(col, rock, max(smoothstep(0.25, 0.55, slope), smoothstep(1300.0, 1900.0, m)));
    col = mix(col, lin(vec3(0.95, 0.96, 0.98)), smoothstep(2950.0, 3150.0, m + 150.0 * (n - 0.5)));
    // on the plinth: the package's own painted ground
    vec2 tq = clamp(q, -1.0, 1.0);
    vec3 own = texture(basin_tex, vec2(tq.x + 1.0, 1.0 - tq.y) * 0.5).rgb;
    float rim = pow(pow(abs(q.x), 4.0) + pow(abs(q.y), 4.0), 0.25);       // the same rounded footprint as BasinSite
    col = mix(own, col, smoothstep(0.86 + 0.05 * (n - 0.5), 1.0, rim));
    // the ring hands over to the map's own colour, a little warmed, then to the map itself
    float box = pow(pow(abs(l.x), 4.0) + pow(abs(l.y), 4.0), 0.25);
    vec3 warm = mix(base, base * vec3(1.06, 0.97, 0.86), 0.6);
    float ring_in = half_size * 1.02, ring_mid = mix(ring_in, blend_out, 0.35);   // keep the edges in order at any scale
    col = mix(col, mix(col, warm, 0.55), smoothstep(ring_in, ring_mid, box));
    col = mix(col, base, smoothstep(ring_mid, blend_out, box));
    ALBEDO = col * cloud_shadow(wpos);
    ROUGHNESS = 0.92;
    SPECULAR = 0.2;
}
