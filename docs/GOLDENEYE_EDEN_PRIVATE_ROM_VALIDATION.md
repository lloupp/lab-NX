# GoldenEye NX — teste privado da ROM no Eden (19/10/2026)

**Contexto:** PR #13, branch `feat/goldeneye-ptbr-localization`, homebrew NRO `goldeneye-nx-loader.nro`.

## Evidência reproduzida neste ciclo

- A ROM USA original fornecida pelo usuário foi verificada localmente (12.582.912 bytes, CRC32 `B6330846`, SHA-1 `abe01e4aeb033b6c0836819f549c791b26cfde83`).
- Eden Linux oficial 0.2.1 executado localmente sob Xvfb/Mesa Lavapipe. O NRO foi reconhecido: `Loading GoldenEye NX Loader (diagnostico)`, seguido de `BootGame: Booting game`.
- A ROM foi montada **somente no ambiente privado**, em `XDG_DATA_HOME/eden/sdmc/switch/lab-nx/goldeneye/baserom.u.z64`. Nunca foi colocada em GitHub Actions.
- O primeiro teste encontrou a janela de inicialização sobre chaves, que **não são necessárias para NRO homebrew**. O executor desenvolvido trata o aviso via xdotool ou XTest do Linux.
- O segundo teste passou pela etapa de boot do frontend, mas excedeu o limite de 2.300 MiB de RSS configurado no guardião. O contêiner tem limite cgroup de 4 GiB, insuficiente para sustentar confortavelmente Eden + Lavapipe e todas as reservas de memória.
- O arquivo de trace do código ARM64 convidado **não apareceu** no teste privado: NÃO foram observados `rom-load-success` nem `first-rom-sprite-frame-submitted`.
- Foi desenvolvido um executor Linux isolado `run_eden_private.py` com validação exata do hash da ROM, montagem privada da SDMC, inicialização gráfica, captura de tela, monitoramento/limite de RAM, classificação de provas e relatório `validation.json`. **Cinco testes automatizados** de validação, ZIP e logs passaram localmente. O pacote executável e os testes foram entregues na conversa, sem ROM.

## Estado e limites

O framebuffer de diagnóstico RGB **já foi demonstrado a 60 FPS no Eden** no workflow https://github.com/lloupp/lab-NX/actions/runs/39319212976, sem ROM. Isso comprova a rotina de framebuffer mas **não gameplay nem primeiro quadro do motor original**.

O código do Fast3D RSP foi previamente compilado para ARM64 como objeto, mas ainda precisa ser linkado ao motor GoldenEye e a um backend GPU. Sem isso, o atual NRO no máximo desenha uma textura original extraída da ROM.

## Próximo passo verificável

Executar o runner com ROM privada num Linux Mint/Ubuntu com idealmente **8–16 GiB de RAM**, Eden oficial e libvulkan/Mesa estáveis. Procurar:
```
main-entered
console-init-ok
hid-init-ok
rom-load-success
framebuffer-ready
first-rom-sprite-frame-submitted
```
Depois verificar uma captura com pixels do logotipo Rareware. O rastro escrito por si só não comprova imagem visível. Manter essa evidência separada de emulação N64 no Linux e da compilação ARM64 de código isolado.

**Não publicar** a pasta privada do executor: ela contém uma cópia da ROM em `private-home`. Não fazer merge da PR antes de gameplay real.
