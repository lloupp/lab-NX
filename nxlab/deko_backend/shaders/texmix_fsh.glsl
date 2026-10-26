#version 460
layout(binding = 0) uniform sampler2D uTex0;
layout(binding = 1) uniform sampler2D uTex1;
layout(location = 0) in vec2 vUV0;
layout(location = 1) in vec2 vUV1;
layout(location = 0) out vec4 outColor;
void main() {
    outColor = mix(texture(uTex0, vUV0), texture(uTex1, vUV1), 0.5);
}
