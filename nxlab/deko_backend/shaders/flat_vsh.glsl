#version 460
layout(location = 0) in vec4 inPos;
layout(location = 4) in vec4 inInput0;
layout(location = 0) out vec4 vInput0;
void main() {
    gl_Position = inPos;
    vInput0 = inInput0;
}
