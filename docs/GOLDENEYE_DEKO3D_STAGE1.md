# GoldenEye NX — primeiro bootstrap deko3d ARM64 (19/10/2026)

## Escopo e base

A branch **`feat/goldeneye-deko3d-stage1-20261019`** foi criada a partir da branch REMOTA `feat/goldeneye-ptbr-localization`. A branch **local** `feat/goldeneye-switch-engine-port` com o commit de memória N64 `d932006` **não foi alterada, não foi incluída e não foi publicada**. Integração com ela precisa acontecer explicitamente após publicar/transferir esse commit, evitando perder o estado local.

Esta implementação **NÃO é o motor do GoldenEye**, nem um backend `GfxRenderingAPI` completo. Não consome a ROM, não reproduz Fast3D e não gera quadro do jogo. O executável independente é um teste GPU deko3d com triângulo sintético.

## Código executável criado

`nxlab/switch_deko_smoke`:

- `Makefile`: compilação independente com devkitA64; usa **`uam`** para produzir dois shaders **DKSH** e RomFS embutido no NRO; links deko3d/libnx.
- `source/triangle_vsh.glsl`: triângulo de diagnóstico no shader, sem dados da ROM.
- `source/color_fsh.glsl`: cor interpolada de diagnóstico.
- `source/main.c`: usa **DkDevice, DkImageLayout, DkImage, DkSwapchain, DkMemBlock, DkShader, DkCmdBuf, DkQueue**. Gera comandos de limpeza e triângulo; tenta apresentar quadros; mantém rastreamento em `sdmc:/switch/lab-nx/goldeneye/deko_boot_trace.txt`. Criação da fila usa a configuração enxuta `Graphics | DisableZcull`, command memory mínimo e sem scratch por warp. Não modifica o carregador da ROM existente.

## Etapa adicional — vertex buffer de CPU para GPU (commit a23f513)

- O triângulo não está mais embutido no GLSL: a CPU preenche um bloco de memória `DkMemBlock` com estruturas `GeDekoVertex` (posição 3 floats + cor RGB 3 floats).
- O deko3d liga `DkVtxAttribState`, `DkVtxBufferState` e `DkBufExtents` por `dkCmdBufBindVtxBuffers`, criando uma entrada concreta para geometria proveniente do motor.
- Os shaders DKSH recebem os atributos nos locais 0 e 1, compilados via `uam`.
- **Build ARM64 e shaders aprovado** em https://github.com/lloupp/lab-NX/actions/runs/39346020067.
- **Ainda não há primeira imagem de geometria** por causa do bloqueio de `dkQueueCreate`. A rotina atual usa três vértices sintéticos, não VBO extraído do Fast3D.

## Evidência real

**Compilação ARM64 + DKSH: aprovado.** Builds oficiais em Docker devkitPro:

- https://github.com/lloupp/lab-NX/actions/runs/39344391065
- https://github.com/lloupp/lab-NX/actions/runs/39344547995
- https://github.com/lloupp/lab-NX/actions/runs/39344894345
- https://github.com/lloupp/lab-NX/actions/runs/39345296250

**Execução real no Eden v0.2.1 + Vulkan/Mesa llvmpipe: parcialmente inicializada.**

Na última tentativa, o NRO ARM64 conseguiu registrar:

```text
main-entered
romfs-mounted
device-created
swapchain-created
dksh-loaded
command-memory-alloc-start
command-memory-alloc-returned
command-buffer-create-start
command-buffer-create-returned
command-buffer-add-memory-start
command-buffer-add-memory-returned
bind-render-target-start
bind-render-target-finished
bind-render-target-start
bind-render-target-finished
render-commands-recording-start
render-commands-recorded
queue-create-lean-start
```

**Não** registrou `queue-create-returned`, `deko3d-ready` ou `first-deko-frame-submitted`.

A captura real do Eden permaneceu na tela **"Launching..."** com **0 FPS**. O processo hospedeiro registrou `terminate called after throwing an instance of 'std::length_error': vector::_M_default_append`. O problema persiste com o mínimo de command memory, scratch warp=0 e Z-cull desativado. Esse é o **bloqueio de execução no emulador**, não um erro de compilação dos shaders nem prova de um problema no código de jogo ainda ausente.

**Importante:** a workflow `.github/workflows/goldeneye-deko3d-stage1.yml` separa o build e a tentativa real no Eden; o job do Eden **falha deliberadamente** se não houver o marcador de envio do primeiro frame; as capturas/logs são preservados via `if: always()`. Isso evita CI verde enganoso.

## Como reproduzir no Linux Mint do usuário

```bash
git fetch origin feat/goldeneye-deko3d-stage1-20261019
# Em diretório SEPARADO para não tocar na branch com o runtime de memória:
git worktree add ../goldeneye-deko-stage1 origin/feat/goldeneye-deko3d-stage1-20261019
cd ../goldeneye-deko-stage1/nxlab/switch_deko_smoke
export DEVKITPRO=/opt/devkitpro
make -j2
```

Copie `goldeneye-deko-smoke.nro` para hbmenu/Switch ou abra o NRO pelo Eden. Não é necessário fornecer ROM ou chaves para esse homebrew. Consulte `deko_boot_trace.txt` na SDMC. O próximo marco verificável é `queue-create-returned`, depois `first-deko-frame-submitted`, **mais captura visível** do triângulo.

## Próximas prioridades, em ordem

1. Diagnosticar `dkQueueCreate` no Eden com **Vulkan Intel/Mesa nativo** (em vez de llvmpipe), no Switch físico, ou depurador do emulador; comparar o mesmo NRO com um deko_basic oficial no Eden. Não presumir que o problema está no jogo.
2. Após fila/triângulo gráfico comprovado, mover geometria sintética do shader para **buffers de vértices reais**, habilitando envio dinâmico da CPU para deko3d.
3. Projetar e implementar subset funcional da interface `GfxRenderingAPI` do GoldenEye PC Port; inicialmente geometria sem textura, ampliando para blending, depth, scissor e texturas.
4. Integrar os commits locais de memória `d932006` após sincronização explícita da branch; conectar Fast3D real, não apenas o shader sintético.
5. Capturar display list real do motor; validar pixels produzidos pelo motor do jogo no Eden/Switch.

**Nenhuma ROM, recurso extraído ou chave privada foi publicada.**
