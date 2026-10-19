# M2 automatic pipeline

The pipeline is **semi-automated**: local STFS/XEX inspection, private extraction, dependency inventory, and optional ReXGlue invocation when installed.

It does not automatically port a game, generate a working NRO, resolve XAM/Xboxkrnl imports or translate graphics. GitHub Actions uses only synthetic fixtures, never private game binaries.

A first local dry run with the owner's authorized Castle Crashers STFS completed the analysis stages; ReXGlue is not installed in the execution environment. Outputs and game resources are kept outside Git.
