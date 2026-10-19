# Bonsai 4B as a Local Advisor

**Bonsai is suggestion-only.** The deterministic supervisor retains authority over all execution and milestone status. The model never receives game binaries or raw logs and cannot run commands.

## Setup with an existing local GGUF

Run llama.cpp in OpenAI-compatible server mode (use the binary matching your Bonsai GGUF):

    llama-server -m /absolute/path/to/bonsai-4b.gguf -c 4096 --host 127.0.0.1 --port 8080 --alias bonsai-4b

Not all Bonsai binaries use identical quantization: check the matching model and runtime, especially older ternary g128 vs newer g64 files. See https://github.com/PrismML-Eng/Bonsai-demo . Small 4B Bonsai models are text-only and do not provide native tools wiring.

## Automatic post-run advisory

After extracting an authorized XBLA archive to a private directory and locating its STFS file:

    python3 -m nxlab.supervisor --input /private/game.stfs --workspace /private/labnx --recipe castle-crashers --codegen --bonsai

The report includes verified steps plus a separate bonsai field (available/unavailable). A model error does not change the deterministic exit code or milestone gates.

## Standalone advisory without rerunning analysis

    python3 -m nxlab.bonsai --report /private/labnx/runs/RUN_ID/report.json --recipe castle-crashers --model bonsai-4b --output /private/labnx/bonsai-advice.json

Use this when the supervisor has already stopped an identical repeat input. Both commands keep reports outside Git.

## Private LAN server (explicit opt-in)

Default endpoint: http://127.0.0.1:8080/v1/chat/completions . To use Bonsai on another trusted PC, specify --bonsai-url http://192.168.1.50:8080/v1/chat/completions --bonsai-allow-lan . Only loopback is allowed by default, and explicit --bonsai-allow-lan only permits private RFC1918 or ULA IPs. Protect the LAN service with firewall/authentication.

## Information boundary

Allowed request data: recipe identifier, platform, stage status, next stage, compression/encryption descriptor, import count, milestone evidence booleans.

Never sent: STFS/XEX, ROM/ISO, keys, hashes, source paths, binary content, raw logs or any commercial game assets.

Only JSON replies with category/action/reason/confidence are accepted, actions come from a fixed non-executable list. Model claims cannot mark PPC, NRO, Eden or Switch stages as passed.

## Future work

Benchmark Bonsai recommendations, add a reviewed Pi/OpenCode escalation option, and only then experiment with sandboxed code changes and test gates. A successful mock server test is **not proof of Bonsai reasoning quality or game execution**.
