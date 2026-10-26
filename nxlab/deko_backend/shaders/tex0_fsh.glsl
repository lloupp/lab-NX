#version 460
layout(binding = 0) uniform sampler2D uTex0;
layout(location = 0) in vec2 vUV0;
layout(location = 0) out vec4 outColor;
void main() {
    outColor = texture(uTex0, vUV0);
}
