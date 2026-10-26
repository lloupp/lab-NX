#version 460
layout(binding = 0) uniform sampler2D uTex;
layout(location = 0) in vec2 vUV;
layout(location = 1) in vec4 vFog;
layout(location = 2) in vec3 vRGB0;
layout(location = 3) in vec3 vRGB1;
layout(location = 4) in vec3 vRGB2;
layout(location = 0) out vec4 outColor;
void main() {
    /* GoldenEye's FOGTEX RGB3 combiner:
     *   cycle 0: mix(INPUT_1, TEXEL0, INPUT_2)
     *   cycle 1: COMBINED * INPUT_3
     * followed by per-vertex fog (vFog.a factor, vFog.rgb colour). */
    vec4 tex = texture(uTex, vUV);
    vec3 c1 = clamp(vRGB0, 0.0, 1.0);
    vec3 c2 = clamp(vRGB1, 0.0, 1.0);
    vec3 c3 = clamp(vRGB2, 0.0, 1.0);
    vec3 rgb = mix(c1, tex.rgb, c2) * c3;
    float fogA = clamp(vFog.a, 0.0, 1.0);
    rgb = mix(rgb, vFog.rgb, fogA);
    outColor = vec4(rgb, 1.0);
}
