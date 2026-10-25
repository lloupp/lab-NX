#version 460
// GPU buffer diagnostic: vertex data now arrives from a CPU-side buffer.
// This is NOT game geometry; future Fast3D input will use this pathway.
layout(location = 0) in vec4 inPos;
layout(location = 1) in vec3 inRGB;
layout(location = 0) out vec4 outColor;
void main() {
    gl_Position = inPos;
    outColor = vec4(inRGB, 1.0);
}
