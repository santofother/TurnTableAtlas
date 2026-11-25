// The red River Flame's moving water: water.gdshader (the city view) and flame_river.gdshader (the Known World).
// `uv` is (signed distance across from the middle, distance downstream) in metres; `bank` runs 0 at the banks to 1 in
// the channel. Silt clouds and long streaks drift downstream, boils turn over in the channel, wavelets ride the current,
// the shallows by the banks run paler with a fringe of foam. Detail finer than a pixel fades out (no shimmer from afar).

float rf_hash(vec2 p) {                       // stable for the long coordinates of the Known World's river
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
float rf_vn(vec2 x) {
    vec2 i = floor(x), f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(rf_hash(i), rf_hash(i + vec2(1.0, 0.0)), f.x), mix(rf_hash(i + vec2(0.0, 1.0)), rf_hash(i + vec2(1.0, 1.0)), f.x), f.y);
}
float rf_fbm(vec2 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { s += a * rf_vn(p); p = p * 2.03 + vec2(17.3, 9.1); a *= 0.5; }
    return s;
}

// wavelets riding the current (metres; the faster near the middle)
float rf_wave(vec2 uv, float t, float bank) {
    float run = t * (11.0 + 9.0 * bank);
    vec2 q = uv - vec2(0.0, run);
    float w = rf_vn(q / vec2(7.0, 12.0)) * 0.6 + rf_vn((q + vec2(41.0, 13.0)) / vec2(3.2, 4.8) - vec2(0.0, t * 0.9)) * 0.4;
    return w;
}

// albedo (linear), a world normal (y up) and roughness for river water of colour `silt` (linear); `xz` is the world
// position (x, z) in metres, to carry the wavelets' slope from the river's frame into the world's
void river_flow(vec2 uv, float bank, float t, vec3 silt, vec2 xz, out vec3 albedo, out vec3 nrm, out float rough) {
    float px = max(length(fwidth(uv)), 1e-4);                 // metres per pixel
    bank = clamp(bank, 0.0, 1.0);
    // big silt clouds, warped into boils, drifting with the current
    vec2 pc = (uv - vec2(0.0, t * (8.0 + 8.0 * bank))) / vec2(170.0, 430.0);
    vec2 warp = vec2(rf_fbm(pc * 0.8 + vec2(3.0, 1.0) + t * 0.004), rf_fbm(pc * 0.8 + vec2(9.0, 4.0) - t * 0.003)) - 0.5;
    float clouds = rf_fbm(pc + warp * 1.6);
    // long streaks of lighter and darker water along the flow
    float sd = 1.0 - smoothstep(10.0, 45.0, px);
    float streak = mix(0.5, rf_vn((uv - vec2(0.0, t * 15.0)) / vec2(26.0, 360.0)) * 0.7 + rf_vn((uv - vec2(0.0, t * 13.0)) / vec2(9.0, 150.0)) * 0.3, sd);
    // colour: the channel deeper and darker, the shallows paler and ochre, clouds and streaks through both
    vec3 rf_deep = silt * vec3(0.72, 0.66, 0.66);   // (not 'deep' / 'shallow': water.gdshader's uniforms have those names)
    vec3 rf_shallow = mix(silt, vec3(0.62, 0.34, 0.17), 0.45) * 1.12;
    vec3 c = mix(rf_shallow, rf_deep, smoothstep(0.0, 0.85, bank));
    c *= 0.80 + 0.42 * clouds;
    c = mix(c, c * vec3(1.22, 1.16, 1.08), smoothstep(0.55, 0.85, streak) * 0.75);
    c = mix(c, c * 0.84, smoothstep(0.45, 0.15, streak) * 0.5);
    // foam: a fringe along the banks, and thin threads of scum drawn out along the current
    float wd = 1.0 - smoothstep(1.5, 7.0, px);
    float foamN = rf_vn((uv - vec2(0.0, t * 9.0)) / vec2(5.0, 18.0));
    float foam = (1.0 - smoothstep(0.0, 0.08, bank)) * smoothstep(0.5, 0.8, foamN) * 0.5;
    float thread = rf_vn((uv + warp * 60.0 - vec2(0.0, t * (10.0 + 8.0 * bank))) / vec2(3.5, 140.0));
    foam += smoothstep(0.78, 0.92, thread) * smoothstep(0.35, 0.7, clouds) * 0.3 * sd;
    c = mix(c, vec3(0.58, 0.40, 0.29), clamp(foam, 0.0, 1.0));
    albedo = c;
    // the wavelets' slope in (across, along), carried into the world through the screen-space derivatives
    float e = 0.9;
    float h0 = rf_wave(uv, t, bank);
    vec2 g = vec2(rf_wave(uv + vec2(e, 0.0), t, bank) - h0, rf_wave(uv + vec2(0.0, e), t, bank) - h0) / e;
    g = g * wd * (0.55 + 0.45 * bank);
    vec2 cg = (vec2(rf_vn(pc * 3.0 + 1.7), rf_vn(pc * 3.0 + 7.3)) - 0.5) * 0.004;   // the boils' broad swell
    g += cg;
    mat2 A = mat2(dFdx(xz), dFdy(xz));
    mat2 C = mat2(dFdx(uv), dFdy(uv));
    float det = determinant(A);
    vec2 gw = abs(det) > 1e-9 ? transpose(C * inverse(A)) * g : vec2(0.0);
    nrm = normalize(vec3(-gw.x * 1.8, 1.0, -gw.y * 1.8));
    rough = mix(0.6, 0.42, bank) + foam * 0.2;            // muddy water: a dull sheen, a few glints off the wavelets
}
