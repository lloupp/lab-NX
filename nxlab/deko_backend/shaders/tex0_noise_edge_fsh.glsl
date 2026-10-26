#version 460
/* RDP AC_DITHER with CVG_X_ALPHA (Fast3D SHADER_OPT_NOISE +
 * SHADER_OPT_TEXTURE_EDGE): dithered discard, the tree-card path from
 * gfx_opengl.cpp:
 *   if (texel.a < random(...)) discard;
 * The surviving texel keeps its alpha for the blend. */
layout(binding = 0) uniform sampler2D uTex0;
layout(std140, binding = 0) uniform NoiseParams {
    int frame_count;
    float noise_scale;
};
layout(location = 0) in vec2 vUV0;
layout(location = 6) in vec2 vClamp0;
layout(location = 0) out vec4 outColor;
vec2 clampUV(vec2 uv, vec2 lim) {
    if (lim.x >= 0.0) uv.x = clamp(uv.x, 0.0, lim.x);
    if (lim.y >= 0.0) uv.y = clamp(uv.y, 0.0, lim.y);
    return uv;
}
float rand_noise() {
    vec3 value = vec3(floor(gl_FragCoord.xy * noise_scale), float(frame_count));
    float r = dot(sin(value), vec3(12.9898, 78.233, 37.719));
    return (fract(sin(r) * 143758.5453) + 1.0) * 0.5;
}
void main() {
    vec4 tex = texture(uTex0, clampUV(vUV0, vClamp0));
    if (tex.a < rand_noise()) discard;
    outColor = vec4(tex.rgb, tex.a);
}
