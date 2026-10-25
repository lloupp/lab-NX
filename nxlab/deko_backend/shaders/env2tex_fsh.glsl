#version 460
layout(binding = 0) uniform sampler2D uTex0;
layout(binding = 1) uniform sampler2D uTex1;
layout(location = 0) in vec2 vUV0;
layout(location = 1) in vec2 vUV1;
layout(location = 2) in vec4 vFog;
layout(location = 3) in vec4 vInput0;
layout(location = 4) in vec4 vInput1;
layout(location = 5) in vec4 vInput2;
layout(location = 0) out vec4 outColor;
void main() {
    /* 2-texture combiner seen in the Dam environment:
     *   cycle 0: mix(TEXEL0, TEXEL1, INPUT_1)
     *   cycle 1: COMBINED * INPUT_2
     * followed by per-vertex fog. */
    vec4 t0 = texture(uTex0, vUV0);
    vec4 t1 = texture(uTex1, vUV1);
    vec3 c0 = clamp(vInput0.rgb, 0.0, 1.0);
    vec3 c1 = clamp(vInput1.rgb, 0.0, 1.0);
    vec3 rgb = mix(t0.rgb, t1.rgb, c0) * c1;
    float fogA = clamp(vFog.a, 0.0, 1.0);
    rgb = mix(rgb, vFog.rgb, fogA);
    outColor = vec4(rgb, t0.a);
}
