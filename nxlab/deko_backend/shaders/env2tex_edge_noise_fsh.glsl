#version 460
/* AC_DITHER (SHADER_OPT_NOISE) variant of the texedge alpha discard. */
layout(binding = 0) uniform sampler2D uTex0;
layout(binding = 1) uniform sampler2D uTex1;
layout(location = 0) in vec2 vUV0;
layout(location = 1) in vec2 vUV1;
layout(location = 2) in vec4 vFog;
layout(location = 3) in vec4 vInput0;
layout(location = 4) in vec4 vInput1;
layout(location = 5) in vec4 vInput2;
layout(location = 6) in vec2 vClamp0;
layout(location = 7) in vec2 vClamp1;
layout(location = 0) out vec4 outColor;
layout(std140, binding = 0) uniform NoiseParams {
    int frame_count;
    float noise_scale;
};

float rand_noise() {
    vec3 value = vec3(floor(gl_FragCoord.xy * noise_scale), float(frame_count));
    float r = dot(sin(value), vec3(12.9898, 78.233, 37.719));
    return (fract(sin(r) * 143758.5453) + 1.0) * 0.5;
}
vec2 clampUV(vec2 uv, vec2 lim) {
    if (lim.x >= 0.0) uv.x = clamp(uv.x, 0.0, lim.x);
    if (lim.y >= 0.0) uv.y = clamp(uv.y, 0.0, lim.y);
    return uv;
}
void main() {
    vec2 uv0 = clampUV(vUV0, vClamp0);
    vec2 uv1 = clampUV(vUV1, vClamp1);
    vec4 t0 = texture(uTex0, uv0);
    vec4 t1 = texture(uTex1, uv1);
    vec3 c0 = clamp(vInput0.rgb, 0.0, 1.0);
    vec3 c1 = clamp(vInput1.rgb, 0.0, 1.0);
    vec3 rgb = mix(t0.rgb, t1.rgb, c0) * c1;
    float fogA = clamp(vFog.a, 0.0, 1.0);
    rgb = mix(rgb, vFog.rgb, fogA);
    float a0 = clamp(vInput0.a, 0.0, 1.0);
    float a1 = clamp(vInput1.a, 0.0, 1.0);
    float alpha = mix(t0.a, t1.a, a0) * a1;
    if (alpha < rand_noise()) discard;
    outColor = vec4(rgb, alpha);
}
