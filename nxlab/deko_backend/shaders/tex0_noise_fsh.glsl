#version 460
/* RDP AC_DITHER alpha compare (Fast3D SHADER_OPT_NOISE) for the one-texture
 * fallback profiles. Mirrors gfx_opengl.cpp:
 *   texel.a *= floor(clamp(random + texel.a, 0.0, 1.0));
 * random() is the same hash across frac(gl_FragCoord.xy * noise_scale) and
 * the frame counter, so the dither pattern matches the GL reference. */
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
    float alpha = tex.a * floor(clamp(rand_noise() + tex.a, 0.0, 1.0));
    outColor = vec4(tex.rgb, alpha);
}
