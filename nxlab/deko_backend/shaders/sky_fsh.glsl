#version 460
/* GoldenEye's cloud-sky combiner from src/game/sky.c:
 *   gDPSetCombineLERP(SHADE, ENVIRONMENT, TEXEL0, ENVIRONMENT, ...)
 * i.e. (SHADE - ENVIRONMENT) * TEXEL0 + ENVIRONMENT, which is
 * mix(ENVIRONMENT, SHADE, TEXEL0). Fast3D maps SHADE to the first shader
 * input and ENVIRONMENT to the second. The 64x64 cloud tile modulates the
 * vertex shade over the environment (fog) colour, so the raw texture must
 * not be shown directly: that leaves the cloud tile's flat blue background
 * untouched (the "flat blue sky"). */
layout(binding = 0) uniform sampler2D uTex0;
layout(location = 0) in vec2 vUV0;
layout(location = 3) in vec4 vInput0;   /* SHADE */
layout(location = 4) in vec4 vInput1;   /* ENVIRONMENT */
layout(location = 6) in vec2 vClamp0;
layout(location = 0) out vec4 outColor;
vec2 clampUV(vec2 uv, vec2 lim) {
    if (lim.x >= 0.0) uv.x = clamp(uv.x, 0.0, lim.x);
    if (lim.y >= 0.0) uv.y = clamp(uv.y, 0.0, lim.y);
    return uv;
}
void main() {
    vec3 tex = texture(uTex0, clampUV(vUV0, vClamp0)).rgb;
    vec3 shade = clamp(vInput0.rgb, 0.0, 1.0);
    vec3 env = clamp(vInput1.rgb, 0.0, 1.0);
    outColor = vec4(mix(env, shade, tex), 1.0);
}
