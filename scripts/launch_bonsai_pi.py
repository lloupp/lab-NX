#!/usr/bin/env python3
"""Start Pi in lab-NX with an isolated, local Bonsai model configuration.

No commercial game data is opened, copied, or uploaded by this launcher.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = Path.home() / ".labnx-bonsai-pi"
PROVIDER = "bonsai-local"


def normalized_api_url(value: str) -> str:
    url = value.rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path not in {"", "/v1"}:
        raise ValueError("Use a URL base OpenAI valida, como http://127.0.0.1:8080/v1")
    return url if parts.path == "/v1" else url + "/v1"


def get_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=6) as response:
        obj = json.load(response)
    if not isinstance(obj, dict):
        raise ValueError("Resposta da API nao e um objeto JSON")
    return obj


def inspect_server(base_url: str, model_id: str) -> int:
    server_url = base_url.removesuffix("/v1")
    health = get_json(server_url + "/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"Servidor Bonsai nao esta pronto: {health}")
    models = get_json(base_url + "/models")
    available = {entry.get("id") for entry in models.get("data", []) if isinstance(entry, dict)}
    if model_id not in available:
        raise RuntimeError(f"Modelo {model_id} ausente na API. Disponiveis: {', '.join(sorted(available))}")
    # The server, not the model's advertised theoretical limit, sets the usable context.
    try:
        props = get_json(server_url + "/props")
        context = int(props.get("default_generation_settings", {}).get("n_ctx", 0))
    except (ValueError, TypeError, HTTPError, URLError, KeyError):
        context = 0
    if context <= 0:
        # Conservative fallback if an older llama-server does not expose /props.
        context = 8192
        print("Aviso: /props indisponivel; usando janela declarada conservadora de 8192 tokens.")
    if context < 2048:
        raise RuntimeError(f"Contexto do servidor insuficiente para Pi: {context} tokens")
    return context


def write_profile(profile: Path, base_url: str, model_id: str, context: int) -> Path:
    profile.mkdir(parents=True, exist_ok=True)
    models_file = profile / "models.json"
    current = json.loads(models_file.read_text(encoding="utf-8")) if models_file.exists() else {}
    if not isinstance(current, dict):
        raise ValueError(f"Arquivo models.json invalido: {models_file}")
    providers = current.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError(f"Campo providers invalido em {models_file}")
    providers[PROVIDER] = {
        "baseUrl": base_url,
        "api": "openai-completions",
        "apiKey": "local",
        "compat": {"supportsDeveloperRole": False, "supportsStore": False},
        "models": [{
            "id": model_id,
            "name": "Bonsai local - lab-NX",
            "reasoning": False,
            "input": ["text"],
            "contextWindow": context,
            "maxTokens": min(4096, max(1024, context // 4)),
            "samplingParams": {"temperature": 0.2, "presence_penalty": 0},
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        }],
    }
    payload = json.dumps(current, indent=2, ensure_ascii=False) + "\n"
    temp = models_file.with_suffix(".json.tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(models_file)
    return models_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa o Pi com o Bonsai local no lab-NX")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--modelo", choices=["4B", "2B"], default="4B")
    parser.add_argument("--perfil", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--verificar", action="store_true", help="Testar API/configuracao sem executar o Pi")
    parser.add_argument("--interativo", action="store_true", help="Abrir Pi sem enviar a missao inicial")
    parser.add_argument("--somente-leitura", action="store_true", help="Desabilitar bash/edit/write")
    args = parser.parse_args(argv)

    try:
        base_url = normalized_api_url(args.base_url)
        model_id = "bonsai-2-" + args.modelo.lower()
        context = inspect_server(base_url, model_id)
        profile = args.perfil.expanduser().resolve()
        config = write_profile(profile, base_url, model_id, context)
    except (OSError, ValueError, RuntimeError, HTTPError, URLError) as exc:
        print(f"Falha no preflight Bonsai: {exc}", file=sys.stderr)
        print("Inicie o Bonsai (bonsai-setup-harness), verifique /health e /v1/models.", file=sys.stderr)
        return 2

    print(f"Bonsai: {model_id} | contexto: {context} | API: {base_url}")
    print(f"Perfil isolado do Pi: {config}")
    pi_exe = shutil.which("pi")
    if args.verificar:
        print("Pi encontrado: " + (pi_exe or "NAO (instale o Pi antes de executar)"))
        return 0 if pi_exe else 3
    if not pi_exe:
        print("Pi nao encontrado no PATH. Instale ou adicione o comando 'pi' ao PATH.", file=sys.stderr)
        return 3

    env = dict(os.environ)
    env["PI_CODING_AGENT_DIR"] = str(profile)
    env["PI_OFFLINE"] = "1"
    env["PI_SKIP_VERSION_CHECK"] = "1"
    tools = "read,grep,find,ls" if args.somente_leitura else "read,bash,edit,write"
    command = [pi_exe, "--provider", PROVIDER, "--model", model_id, "--tools", tools]
    if not args.interativo:
        command += ["@docs/BONSAI_CASTLE_TASK.md", "Execute a missao com evidencias reais e sem dados privados no Git."]
    print("Iniciando Pi em:", ROOT)
    try:
        return subprocess.call(command, cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
