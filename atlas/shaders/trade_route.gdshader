// The grain route from the River Flame delta to Karn Ashur (HighDunes.cs): a dashed ribbon that keeps a readable
// width on screen at every zoom (it widens with the camera's distance), ochre-red overland, pale over the sea.
// UV.x = side (-1..1), UV.y = distance along the route (blend units), UV2.x = 1 on the sea leg; NORMAL = direction.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform float cam_dist = 50.0;

varying float along;
varying float sea;
varying float dash_len;

void vertex() {
    along = UV.y;
    sea = UV2.x;
    // width and dash length grow with the camera's distance, in whole octaves so the dashes don't crawl
    float k = exp2(floor(log2(max(cam_dist, 1.0) * 0.5)));
    float width = clamp(cam_dist * 0.0024, 0.003, 1.6);
    dash_len = clamp(k * 0.05, 0.01, 12.0);
    vec3 dir = normalize(NORMAL);
    vec3 side = normalize(cross(vec3(0.0, 1.0, 0.0), dir));
    VERTEX += side * UV.x * width * 0.5;
    VERTEX.y += width * 0.15;
    NORMAL = vec3(0.0, 1.0, 0.0);
}

void fragment() {
    float d = fract(along / dash_len);
    float on = step(0.38, d);
    vec3 land = vec3(0.55, 0.12, 0.06);
    vec3 water = vec3(0.92, 0.88, 0.78);
    ALBEDO = mix(land, water, sea);
    ALPHA = mix(0.95, 0.8, sea) * on;
}
