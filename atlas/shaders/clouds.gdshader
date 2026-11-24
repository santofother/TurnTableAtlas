// Volumetric clouds, raymarched through a box (CloudLayer.cs). One shader for the city view and both world maps.
// Shape: a drifting 2D weather map decides where cloud is (coverage), a height profile gives flat bases and
// towering tops, 3D billow noise breaks the surface up and a finer noise erodes the edges into wisps.
// Light: Beer-Lambert towards the sun with a multiple-scattering floor, a powder term (dark crevices on the lit
// side), a two-lobe Henyey-Greenstein phase (silver lining against the sun), and sky ambient graded by height.
// Below the base, rain shafts when it rains; lightning lights the cloud from inside.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_never, depth_test_disabled, blend_premul_alpha, fog_disabled, shadows_disabled;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D weather_tex : repeat_enable, filter_linear_mipmap;
uniform sampler3D shape_tex : repeat_enable, filter_linear;
uniform sampler3D detail_tex : repeat_enable, filter_linear;

uniform vec2 box_center = vec2(0.0);
uniform vec2 box_half = vec2(150.0);
uniform float ground_y = 0.0;
uniform float base_y = 22.0;
uniform float top_y = 40.0;
uniform float cell = 60.0;            // world units per weather-map tile
uniform float shape_size = 16.0;      // world units per billow-noise tile
uniform float detail_size = 4.0;
uniform vec2 wind = vec2(0.0);        // drift so far, world units (x, z)
uniform vec2 wind_dir = vec2(1.0, 0.0);
uniform float coverage = 0.3;
uniform float tower = 0.6;            // 0 flat stratus .. 1 cumulonimbus
uniform float sigma = 0.6;            // extinction per world unit at density 1
uniform float darkness = 0.0;
uniform float rain = 0.0;
uniform float flash = 0.0;
uniform vec2 flash_xz = vec2(0.0);
uniform float flash_r = 30.0;
uniform vec3 sun_dir = vec3(0.3, 0.8, 0.2);    // towards the light
uniform vec3 sun_col = vec3(2.5);              // linear, already times intensity
uniform vec3 amb_top = vec3(0.55, 0.65, 0.85);
uniform vec3 amb_bot = vec3(0.32, 0.33, 0.38);
uniform float near_fade = 2.0;
uniform float edge = 20.0;
uniform int steps = 56;

float hf_of(float y) { return clamp((y - base_y) / (top_y - base_y), 0.0, 1.0); }
float thr() { return mix(0.80, 0.24, coverage); }

// large-scale cloud strength at p (no 3D noise): >0 inside a cloud column, plus the column's relative top
vec2 column(vec2 xz) {
    vec2 q = xz - wind;
    float w = texture(weather_tex, q / cell).r;
    float v = texture(weather_tex, q / (cell * 2.71) + vec2(0.37, 0.71)).r;
    float t = thr();
    float c = (w - t) / (1.0 - t);
    float top = clamp(mix(0.30, 1.0, tower) * mix(0.55, 1.25, v) * clamp(0.35 + c * 1.6, 0.0, 1.0), 0.08, 1.0);
    return vec2(c, top);
}

float edge_k(vec2 xz) {
    vec2 d = box_half - abs(xz - box_center);
    return smoothstep(0.0, edge, min(d.x, d.y));
}

// density 0..1; lod 0 = full detail, 1 = no detail (light march)
float density(vec3 p, int lod) {
    vec2 col = column(p.xz);
    if (col.x < -0.25) return 0.0;
    float hf = hf_of(p.y);
    float base = smoothstep(0.0, 0.07, hf);
    float topf = 1.0 - smoothstep(col.y * 0.45, col.y, hf);
    vec3 drift = vec3(wind.x, 0.0, wind.y);
    float s = texture(shape_tex, (p - drift) / shape_size).r;
    float field = col.x * 1.3 + (base * topf - 1.0) + (s - 0.5) * 0.9;
    float d = clamp(field * 2.2, 0.0, 1.0);
    if (lod == 0 && d > 0.0) {
        float n = texture(detail_tex, (p - drift * 1.15) / detail_size).r;
        d = clamp(d - (1.0 - n) * 0.45 * (1.0 - d), 0.0, 1.0);
    }
    return d * edge_k(p.xz);
}

float light_depth(vec3 p) {
    float ds = (top_y - base_y) * 0.07;
    float od = 0.0;
    vec3 q = p;
    for (int i = 0; i < 5; i++) {
        q += sun_dir * ds;
        if (q.y > top_y) break;
        od += density(q, 1) * ds;
        ds *= 1.7;
    }
    return od;
}

float hg(float c, float g) { float g2 = g * g; return (1.0 - g2) / pow(1.0 + g2 - 2.0 * g * c, 1.5); }

bool slab(vec3 ro, vec3 rd, vec3 bmin, vec3 bmax, out float t0, out float t1) {
    vec3 inv = 1.0 / rd;
    vec3 a = (bmin - ro) * inv, b = (bmax - ro) * inv;
    vec3 lo = min(a, b), hi = max(a, b);
    t0 = max(max(lo.x, lo.y), lo.z);
    t1 = min(min(hi.x, hi.y), hi.z);
    return t1 > max(t0, 0.0);
}

void fragment() {
    vec3 ro = CAMERA_POSITION_WORLD;
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 rd = normalize(wp - ro);
    float dep = texture(depth_tex, SCREEN_UV).r;
    vec4 vp = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, dep, 1.0);
    float scene = length(vp.xyz / vp.w);

    float low = rain > 0.01 ? ground_y : base_y;
    vec3 bmin = vec3(box_center.x - box_half.x, low, box_center.y - box_half.y);
    vec3 bmax = vec3(box_center.x + box_half.x, top_y, box_center.y + box_half.y);
    float t0, t1;
    if (!slab(ro, rd, bmin, bmax, t0, t1)) discard;
    t0 = max(t0, 0.0);
    t1 = min(t1, scene);
    if (t1 <= t0) discard;

    float span = t1 - t0;
    float dt = max(span / float(steps), (top_y - base_y) / 48.0);
    float jit = fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))));
    float t = t0 + dt * jit;
    float cosv = dot(rd, normalize(sun_dir));
    float phase = mix(hg(cosv, 0.55), hg(cosv, -0.2), 0.35) * 0.8 + 0.2;
    vec3 sun = sun_col * (1.0 - 0.55 * darkness);
    float amb_k = 1.0 - 0.45 * darkness;
    vec3 rain_col = mix(amb_bot, amb_top, 0.3) * 0.75 * amb_k;

    vec3 acc = vec3(0.0);
    float T = 1.0;
    for (int i = 0; i < 256; i++) {
        if (i >= steps * 2 || t > t1 || T < 0.015) break;
        vec3 p = ro + rd * t;
        float nf = smoothstep(0.0, near_fade, t);
        if (p.y >= base_y) {
            float d = density(p, 0) * nf;
            if (d > 0.002) {
                float ext = d * sigma;
                float od = light_depth(p) * sigma;
                float tl = max(exp(-od), 0.65 * exp(-od * 0.25));
                float powder = 1.0 - 0.75 * exp(-ext * 6.0);
                float hf = hf_of(p.y);
                vec3 amb = mix(amb_bot, amb_top, smoothstep(0.0, 1.0, hf)) * amb_k * (0.55 + 0.45 * hf);
                vec3 s = sun * phase * tl * powder + amb;
                if (flash > 0.0) s += vec3(0.75, 0.8, 1.0) * flash * 14.0 * exp(-length(p.xz - flash_xz) / flash_r) * (1.0 - hf * 0.5);
                float ts = exp(-ext * dt);
                acc += T * s * (1.0 - ts);
                T *= ts;
            } else {
                t += dt * 0.6;   // empty air: stride a little further
            }
        } else if (rain > 0.01) {
            // rain shafts: under strong columns, slanting with the wind, streaky
            vec2 slant = wind_dir * (base_y - p.y) * 0.25;
            vec2 col = column(p.xz - slant);
            float r = rain * smoothstep(0.05, 0.45, col.x) * smoothstep(ground_y, ground_y + (base_y - ground_y) * 0.3, p.y + (base_y - ground_y) * 0.2);
            vec2 sq = (p.xz - slant - wind) / (detail_size * 1.5);
            r *= 0.55 + 0.45 * texture(detail_tex, vec3(sq.x, p.y * 0.02, sq.y)).r;
            float ext = r * sigma * 0.06 * nf;
            float ts = exp(-ext * dt);
            acc += T * rain_col * (1.0 - ts);
            T *= ts;
        }
        t += dt;
    }
    float a = 1.0 - T;
    if (a < 0.003) discard;
    ALBEDO = acc;
    ALPHA = a;
}
