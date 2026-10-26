#version 460
layout(location = 0) in vec4 inPos;
layout(location = 1) in vec2 inUV;
layout(location = 2) in vec4 inFog;
layout(location = 3) in vec3 inRGB0;
layout(location = 4) in vec3 inRGB1;
layout(location = 5) in vec3 inRGB2;
layout(location = 0) out vec2 vUV;
layout(location = 1) out vec4 vFog;
layout(location = 2) out vec3 vRGB0;
layout(location = 3) out vec3 vRGB1;
layout(location = 4) out vec3 vRGB2;
void main() {
    gl_Position = inPos;
    vUV = inUV;
    vFog = inFog;
    vRGB0 = inRGB0;
    vRGB1 = inRGB1;
    vRGB2 = inRGB2;
}
