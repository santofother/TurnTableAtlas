// Cloud shadows and wet ground for surfaces under the volumetric cloud layer (clouds.gdshader). CloudLayer.cs sets
// these on every material that includes this file. The shadow follows the same weather map as the clouds,
// projected along the sun direction from the middle of the cloud layer.
uniform sampler2D cloud_weather : repeat_enable, filter_linear_mipmap;
uniform float cloud_cover = 0.0;
uniform float cloud_cell = 60.0;
uniform vec2 cloud_wind = vec2(0.0);
uniform vec3 cloud_sun = vec3(0.0, 1.0, 0.0);
uniform float cloud_mid = 30.0;
uniform float cloud_shadow_k = 0.0;   // 0 = no cloud shadows
uniform float cloud_wet = 0.0;        // 0 dry .. 1 soaked

float cloud_shadow(vec3 wp) {
    if (cloud_shadow_k <= 0.0) return 1.0;
    vec3 s = normalize(cloud_sun);
    vec2 p = wp.xz + s.xz / max(s.y, 0.2) * (cloud_mid - wp.y);
    float w = texture(cloud_weather, (p - cloud_wind) / cloud_cell).r;
    float t = mix(0.80, 0.24, cloud_cover);
    return 1.0 - cloud_shadow_k * smoothstep(t - 0.03, t + 0.16, w);
}
