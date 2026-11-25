// An estate's hero patch on the Known World (Estate.cs): the package's own baked terrain on the plinth, autumn
// meadow, vineyard strips and copses on the hills round it, fading into the baked map's colour towards the patch's edge.
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;
#include "res://shaders/cloud_shadow.gdshaderinc"

uniform sampler2D estate_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;   // the relief's heights, for its own shading
uniform vec2 world_min;     // map xz of the albedo's top-left
uniform vec2 world_size;
uniform vec2 centre;        // estate centre (x, z)
uniform float half_size;    // half the plinth (blend units)
uniform float hills_r;      // the estate's own colours out to here
uniform float blend_out;    // the map's colour from here
uniform float night = 0.0;

varying vec3 wpos;

float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vn(vec2 x) { vec2 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1, 0)), f.x), mix(hash2(i + vec2(0, 1)), hash2(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p) { return vn(p) * 0.55 + vn(p * 2.1 + 3.1) * 0.3 + vn(p * 4.3 + 7.7) * 0.15; }

void vertex() {
    wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }

void fragment() {
    vec2 l = vec2(wpos.x - centre.x, -(wpos.z - centre.y));          // +x east, +y north
    vec2 q = l / half_size;                                           // plinth halves
    vec2 map_uv = (wpos.xz - world_min) / world_size;
    vec3 base = texture(albedo_tex, map_uv).rgb;
    vec3 col;
    // the estate's land round the plinth: meadow, vineyard parcels (rows fade out with distance), copses
    float r = length(l);
    float n = fbm(q * 1.3);
    vec3 meadow = mix(lin(vec3(0.50, 0.49, 0.24)), lin(vec3(0.64, 0.56, 0.29)), smoothstep(0.3, 0.75, fbm(q * 3.0 + 9.0)));
    vec2 cell = floor(q * 2.2 + vec2(0.3, 0.7) + 0.55 * vec2(fbm(q * 0.9) - 0.5, fbm(q * 0.9 + 5.3) - 0.5));
    float parcel = step(0.45, hash2(cell * 1.37 + 2.0));
    float ang = (hash2(cell) > 0.5 ? 0.15 : 1.62) + 0.1 * hash2(cell + 5.0);
    vec2 dir = vec2(cos(ang), sin(ang));
    float rp = dot(q, dir) * 46.0;
    float rows = smoothstep(0.35, 0.65, abs(fract(rp) - 0.5) * 2.0);
    rows = mix(rows, 0.55, smoothstep(0.25, 0.6, fwidth(rp)));
    vec3 leaf = mix(lin(vec3(0.84, 0.62, 0.20)), lin(vec3(0.76, 0.34, 0.13)), step(0.5, hash2(cell + 9.0)));
    vec3 vine = mix(lin(vec3(0.45, 0.34, 0.22)), leaf, rows);
    col = mix(meadow, vine, parcel);
    float wood = smoothstep(0.64, 0.72, fbm(q * 2.6 + 4.0));
    col = mix(col, mix(lin(vec3(0.62, 0.34, 0.12)), lin(vec3(0.32, 0.36, 0.17)), vn(q * 9.0)), wood * 0.75);
    // the road south towards Calderra
    float road = (1.0 - smoothstep(0.015, 0.04, abs(q.x - (-0.05 + 0.18 * (q.y + 1.0) * (q.y + 1.0) * -0.25)))) * step(q.y, -1.0);
    col = mix(col, lin(vec3(0.70, 0.58, 0.42)), road);
    // on the plinth: the package's own baked albedo, with a soft rim
    vec2 tq = clamp(q, -1.0, 1.0);
    vec3 est = texture(estate_tex, vec2(tq.x + 1.0, 1.0 - tq.y) * 0.5).rgb;
    float rim = max(abs(q.x), abs(q.y));
    col = mix(est, col, smoothstep(1.0, 1.1, rim));
    // the land hands over to the map's own colour, a little warmed, then to the map itself
    vec3 warm = mix(base, base * vec3(1.05, 0.98, 0.86), 0.6);
    col = mix(col, warm, smoothstep(1.8 * half_size, 2.8 * half_size, r));
    col = mix(col, base, smoothstep(2.8 * half_size, blend_out, r));
    // away from the villa, light the ground exactly as relief.gdshader does, so the patch cannot be seen
    float far = smoothstep(1.8 * half_size, hills_r, r);
    vec2 texel = 1.0 / vec2(textureSize(height_tex, 0));
    float hx = max(textureLod(height_tex, map_uv + vec2(texel.x, 0.0), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(texel.x, 0.0), 0.0).r, 0.0);
    float hz = max(textureLod(height_tex, map_uv + vec2(0.0, texel.y), 0.0).r, 0.0) - max(textureLod(height_tex, map_uv - vec2(0.0, texel.y), 0.0).r, 0.0);
    vec3 rn = normalize(vec3(-hx / (2.0 * texel.x * world_size.x), 1.0, -hz / (2.0 * texel.y * world_size.y)));
    vec3 vn_world = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
    NORMAL = normalize((VIEW_MATRIX * vec4(normalize(mix(vn_world, rn, far)), 0.0)).xyz);
    col *= mix(1.0, mix(0.94, 1.05, vn(wpos.xz * 3.0) * 0.6 + vn(wpos.xz * 11.0) * 0.4), far);
    col *= mix(1.0, mix(1.0, 0.7, cloud_wet), far);
    ALBEDO = col * cloud_shadow(wpos);
    ROUGHNESS = mix(0.92, mix(0.9, 0.5, cloud_wet), far);
    SPECULAR = mix(0.2, 0.25, far);
    // the patch reaches the coast: where the map is sea, draw it as the relief does
    if (textureLod(height_tex, map_uv, 0.0).r <= 0.0) {
        ALBEDO = base * cloud_shadow(wpos);
        NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
        ROUGHNESS = 0.3;
        SPECULAR = 0.5;
    }
}
