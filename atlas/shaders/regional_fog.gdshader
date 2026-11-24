// Terrain-following fog on the Known World. UV (0, 0) is the northwest map corner.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_never, depth_test_disabled, blend_premul_alpha, fog_disabled, shadows_disabled;

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D height_tex : repeat_disable, filter_linear;
uniform sampler2D noise_tex : repeat_enable, filter_linear_mipmap;
uniform vec3 box_min;
uniform vec3 box_max;
uniform float daylight = 1.0;
uniform float weather_fog;

float footprint(vec2 uv, vec2 center, vec2 radii) {
    return 1.0 - smoothstep(0.48, 1.25, length((uv - center) / radii));
}

float extinction(vec3 p, vec2 uv, vec2 regional) {
    // Skip texture reads outside the four regions, including their drifting edges.
    bool on_edge = uv.x < 0.14 || (uv.y > 0.74 && uv.x > 0.16 && uv.x < 0.78);
    bool in_north = uv.x > 0.285 && uv.x < 0.64 && abs(uv.y - 0.20) < 0.10;
    bool in_east = uv.x > 0.85 && uv.y < 0.41;
    if (!on_edge && !in_north && !in_east) return 0.0;

    vec2 drift = TIME * vec2(1.0, -2.0) / 3600.0;
    float bank = textureLod(noise_tex, p.xz / vec2(105.0, 67.0) - drift, 0.0).r;
    float wisps = textureLod(noise_tex, p.xz / vec2(26.0, 13.0) - drift * 4.0 + vec2(p.y * 0.04), 0.0).r;
    float turbulence = bank - 0.5 + (wisps - 0.5) * 0.42;

    // West of the marked line on Vesperra and below the southern line on Quadria.
    float latitude = 2.0 * uv.y - 1.0;
    float west_front = 0.065 - 0.028 * latitude * latitude + 0.066 * turbulence;
    float west = 1.0 - smoothstep(west_front - 0.021, west_front + 0.025, uv.x);
    float hook = (uv.x - 0.234) / 0.045;
    float south_front = 0.928 - 0.092 * exp(-hook * hook) + 0.010 * sin(uv.x * 31.0) + 0.087 * turbulence;
    float south = smoothstep(0.165, 0.211, uv.x) * (1.0 - smoothstep(0.718, 0.772, uv.x));
    south *= smoothstep(south_front - 0.018, south_front + 0.035, uv.y);

    // Independent fronts drift into the Vaelwood and Thrasia as their density builds.
    vec2 warped_uv = uv + vec2(bank - 0.5, wisps - 0.5) * vec2(0.048, 0.041);
    float north = regional.x * footprint(warped_uv, vec2(0.475, 0.194) + vec2(-0.030, 0.013) * (1.0 - regional.x), vec2(0.107, 0.042));
    float east = regional.y * footprint(warped_uv, vec2(0.941, 0.181) + vec2(0.027, -0.019) * (1.0 - regional.y), vec2(0.049, 0.158));
    float persistent = max(west, south);
    float passing = max(north, east);
    if (max(persistent, passing) < 0.001) return 0.0;

    // Fog hugs the relief and thins over the peaks. Slow wind changes the density inside each band.
    float land = max(0.0, textureLod(height_tex, uv, 0.0).r);
    float above_land = p.y - land;
    float height = mix(4.8, 6.3, persistent) - min(land * 0.3, 1.8) + 1.4 * turbulence;
    if (above_land > height) return 0.0;
    float layer = 1.0 - smoothstep(0.0, height, max(above_land, 0.0));
    return layer * max(persistent * (0.32 + 0.54 * bank + 0.20 * wisps),
        passing * (0.14 + 0.61 * smoothstep(0.28, 0.72, bank + 0.14 * wisps)));
}

void fragment() {
    vec3 ro = CAMERA_POSITION_WORLD;
    vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 rd = normalize(wp - ro);
    vec3 enter = (box_min - ro) / rd;
    vec3 exit = (box_max - ro) / rd;
    vec3 near_face = min(enter, exit);
    vec3 far_face = max(enter, exit);
    float t0 = max(max(max(near_face.x, near_face.y), near_face.z), 0.0);
    float t1 = min(min(far_face.x, far_face.y), far_face.z);
    float depth = texture(depth_tex, SCREEN_UV).r;
    vec4 hit = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
    t1 = min(t1, length(hit.xyz / hit.w));
    if (t1 <= t0) discard;

    // Both regions spend more of the cycle fogging than clear, with different timing.
    vec2 cycle = cos(TAU * (vec2(TIME / 75.0, TIME / 90.0) + vec2(0.08, 0.81)));
    vec2 fronts = smoothstep(vec2(-0.65), vec2(0.55), cycle + weather_fog * 0.55);
    const int steps = 12;
    float dt = (t1 - t0) / float(steps);
    vec2 size = box_max.xz - box_min.xz;
    float optical_depth = 0.0;
    for (int i = 0; i < steps; i++) {
        vec3 p = ro + rd * (t0 + (float(i) + 0.5) * dt);
        vec2 uv = (p.xz - box_min.xz) / size;
        optical_depth += extinction(p, uv, fronts) * dt;
        if (optical_depth > 4.5) break;
    }
    float alpha = 1.0 - exp(-optical_depth);
    if (alpha < 0.004) discard;
    vec3 tint = mix(vec3(0.039, 0.052, 0.077), vec3(0.57, 0.65, 0.70), daylight);
    ALBEDO = tint * alpha;
    ALPHA = alpha;
}
