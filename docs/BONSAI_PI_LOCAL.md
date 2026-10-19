# Executar lab-NX com Bonsai 4B e Pi Agent

Esta integracao da ao Pi acesso a ferramentas locais para trabalhar no codigo
do lab-NX. E **diferente** do modulo `nxlab.bonsai` existente: o modulo
anterior apenas sugere diagnosticos ao supervisor; este launcher pode editar
e executar comandos sob as permissoes do usuario.

## Pre-requisitos

- Python 3.10+ e `pi` instalado e acessivel no PATH (`pi --version`).
- Servidor Bonsai do repositorio `lloupp/bonsai-setup-harness` instalado.
- Clone local desta branch do lab-NX. Nao coloque ROMs, ISOs, XEX, chaves ou
  dumps comerciais no Git.

Em um PC com 8 GB RAM, inicie com 8192 ou 16384 tokens de contexto, sem visao.
O perfil de 65536 tokens do Bonsai pode causar forte pressao de memoria.

### Linux Mint

Terminal 1, dentro da pasta local `bonsai-setup-harness`:

```bash
./linux/iniciar-bonsai.sh --contexto 8192 --sem-visao
```

Terminal 2, dentro da pasta local `lab-NX`:

```bash
python3 scripts/launch_bonsai_pi.py --verificar
python3 scripts/launch_bonsai_pi.py
```

### Windows PowerShell

Terminal 1, dentro de `bonsai-setup-harness`:

```powershell
.\iniciar-bonsai.ps1 -Contexto 8192 -SemVisao -SemNavegador
```

Terminal 2, dentro de `lab-NX`:

```powershell
py -3 scripts\launch_bonsai_pi.py --verificar
py -3 scripts\launch_bonsai_pi.py
```

Se o servidor ja estiver rodando, nao execute o inicializador novamente.
Confirme primeiro `http://127.0.0.1:8080/health` e
`http://127.0.0.1:8080/v1/models`. Se faltar o Pi, instale a versao
suportada pelo seu ambiente e repita `pi --version`.

## O que acontece

O launcher verifica a saude da API, se `bonsai-2-4b` esta carregado e
le o contexto efetivo em `/props`. Configura um **perfil isolado** em
`~/.labnx-bonsai-pi/models.json`, sem modificar `~/.pi/agent` nem os
perfis do Hermes/Claude Code. O provider e `openai-completions`, com
temperatura 0.2, chave local dummy e janela de contexto conforme o servidor.

Ao iniciar, o Pi recebe `docs/BONSAI_CASTLE_TASK.md` e comeca por uma
mudanca pequena, testavel, voltada ao Castle Crashers no Switch. Ele nao
instala o Bonsai, nao inicia o Eden automaticamente e nao executa trabalho
quando seu terminal esta fechado.

Outros modos:

```bash
python3 scripts/launch_bonsai_pi.py --interativo
python3 scripts/launch_bonsai_pi.py --somente-leitura
python3 scripts/launch_bonsai_pi.py --modelo 2B --verificar
python3 -m unittest discover -s tests -p 'test_bonsai_pi.py' -v
```

Para 2B, primeiro reinicie o servidor com `--modelo 2B` (Linux) ou
`-Modelo 2B` (Windows); o launcher bloqueia IDs de modelo divergentes.

## Validacao e cautelas

O preflight apenas prova conectividade e configuracao. Testes mock nao
provam tool calling real, recompilacao PowerPC, NRO do jogo, frames do
Castle Crashers ou gameplay no Eden. Verifique o resumo, o `git diff`,
os testes e os logs antes de aceitar as mudancas do agente.

O Pi pode executar comandos e editar arquivos. Use uma branch propria,
mantenha dumps fora do repositorio e nao rode o agente como administrador.
Por padrao, a conexao e somente localhost; ao usar `--base-url` remoto,
considere que o servidor remoto podera receber codigo e contexto.
