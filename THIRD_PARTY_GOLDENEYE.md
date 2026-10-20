# GoldenEye engine build provenance

The complete-engine build fetches or archives `jkdansereau/goldeneye-pc-port` at
`fda76b69837e6c5aae436e0d3e798989e49b06d2`. The upstream source tree, its license
notices and copyright headers remain in the external build workspace. This
repository carries a platform adaptation patch, not a vendored game tree.
Upstream includes third-party components with their own notices; compilation
or redistribution does not remove their applicable terms.

Switch SDK components and portlibs are supplied separately by devkitPro/libnx,
SDL and Mesa/nouveau. Their original notices remain in those distributions.
The build workflow uploads a build manifest, not the full-engine binary.
No retail ROM, converted sidecars, firmware or keys are distributed here.
