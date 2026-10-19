#version 460
// GPU pipeline diagnostic only: generated triangle, NOT GoldenEye N64 geometry.
const vec4 positions[3] = vec4[](
    vec4( 0.0,  0.8, 0.0, 1.0),
    vec4(-0.8, -0.8, 0.0, 1.0),
    vec4( 0.8, -0.8, 0.0, 1.0)
);
const vec4 colors[3] = vec4[](
    vec4(1.0, 0.2, 0.2, 1.0),
    vec4(0.2, 1.0, 0.2, 1.0),
    vec4(0.2, 0.4, 1.0, 1.0)
);
layout(location = 0) out vec4 outColor;
void main() {
    gl_Position = positions[gl_VertexID];
    outColor = colors[gl_VertexID];
}
