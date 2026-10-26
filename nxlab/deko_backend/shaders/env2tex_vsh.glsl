#version 460
layout(location = 0) in vec4 inPos;
layout(location = 1) in vec2 inUV0;
layout(location = 2) in vec2 inUV1;
layout(location = 3) in vec4 inFog;
layout(location = 4) in vec4 inInput0;
layout(location = 5) in vec4 inInput1;
layout(location = 6) in vec4 inInput2;
layout(location = 7) in vec2 inClamp0;
layout(location = 8) in vec2 inClamp1;
layout(location = 0) out vec2 vUV0;
layout(location = 1) out vec2 vUV1;
layout(location = 2) out vec4 vFog;
layout(location = 3) out vec4 vInput0;
layout(location = 4) out vec4 vInput1;
layout(location = 5) out vec4 vInput2;
layout(location = 6) out vec2 vClamp0;
layout(location = 7) out vec2 vClamp1;
void main() {
    gl_Position = inPos;
    vUV0 = inUV0;
    vUV1 = inUV1;
    vFog = inFog;
    vInput0 = inInput0;
    vInput1 = inInput1;
    vInput2 = inInput2;
    vClamp0 = inClamp0;
    vClamp1 = inClamp1;
}
