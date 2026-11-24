// Painted sky blending day / golden hour / night (same palette as blender/cinematic/sky.py), sun glow and disc,
// stars and a moon. sun_dir / moon_dir are in Godot's frame.
shader_type sky;

uniform float day = 1.0;
uniform float dusk = 0.0;
uniform float night = 0.0;
uniform vec3 sun_dir = vec3(0.0, 1.0, 0.0);
uniform vec3 moon_dir = vec3(0.0, -1.0, 0.0);

vec3 lin(vec3 c) { return pow(c, vec3(2.2)); }
vec3 ramp_day(float u) {
    vec3 c = mix(lin(vec3(0.80, 0.84, 0.88)), lin(vec3(0.62, 0.74, 0.90)), smoothstep(0.0, 0.05, u));
    c = mix(c, lin(vec3(0.42, 0.60, 0.88)), smoothstep(0.05, 0.30, u));
    return mix(c, lin(vec3(0.22, 0.40, 0.80)), smoothstep(0.30, 1.0, u));
}
vec3 ramp_dusk(float u) {
    vec3 c = mix(lin(vec3(0.99, 0.66, 0.40)), lin(vec3(0.97, 0.58, 0.48)), smoothstep(0.0, 0.05, u));
    c = mix(c, lin(vec3(0.74, 0.50, 0.62)), smoothstep(0.05, 0.14, u));
    c = mix(c, lin(vec3(0.40, 0.38, 0.64)), smoothstep(0.14, 0.30, u));
    c = mix(c, lin(vec3(0.18, 0.21, 0.46)), smoothstep(0.30, 0.60, u));
    return mix(c, lin(vec3(0.09, 0.11, 0.30)), smoothstep(0.60, 1.0, u));
}
vec3 ramp_night(float u) {
    vec3 c = mix(lin(vec3(0.06, 0.08, 0.15)), lin(vec3(0.03, 0.045, 0.10)), smoothstep(0.0, 0.15, u));
    return mix(c, lin(vec3(0.008, 0.012, 0.035)), smoothstep(0.15, 1.0, u));
}
float hash3(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }

void sky() {
    float u = max(EYEDIR.y, 0.0);
    vec3 c = mix(ramp_night(u), ramp_day(u), day);
    c = mix(c, ramp_dusk(u), dusk);
    float sd = max(dot(EYEDIR, normalize(sun_dir)), 0.0);
    float glow = pow(sd, 18.0) + (sd > 0.9993 ? 6.0 : 0.0);
    c += min(glow * (dusk + 0.35 * day), 1.0) * vec3(1.0, 0.62, 0.30);
    if (!AT_CUBEMAP_PASS) {
        vec3 g = floor(EYEDIR * 160.0);
        float star = step(0.9965, hash3(g)) * night * u;
        float md = dot(EYEDIR, normalize(moon_dir));
        float moon = (md > 0.9990 ? 3.0 : 0.0) + pow(max(md, 0.0), 60.0) * 0.25;
        c += (star * 1.5 + moon * night) * vec3(0.9, 0.92, 1.0);
    } else {
        c = max(c, night * vec3(0.035, 0.045, 0.085));
    }
    // below the horizon (past the plinth edge): fade to a darker tone so the diorama reads as an object
    c = mix(c, c * 0.35, smoothstep(0.0, -0.35, EYEDIR.y));
    COLOR = c;
}
