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


## Experimento incremental — fila deko3d de referência (21/10/2026)

O bloqueio original foi reproduzido no job Eden de
[39346020067](https://github.com/lloupp/lab-NX/actions/runs/39346020067):
`main-entered`, `romfs-mounted`, `device-created`, `swapchain-created`,
`dksh-loaded` e `queue-create-lean-start` aparecem, mas não há
`queue-create-returned` nem frame. **Não confundir build aprovado, boot do
guest ou comandos gravados com pixels renderizados.**

### Comparação técnica

Referências:
- [deko3d Primer — Queues](https://github.com/devkitPro/deko3d/blob/master/Primer.md)
  (configuração e valores padrão de `DkQueueMaker`);
- [Atmosphère — inicialização da fila da GPU console](https://git.niklascfw.de/OmniNX/Atmosphere/commit/d9fff85bc4)
  (sequência `device -> queue`, `queueMaker.flags = DkQueueFlags_Graphics`).

| Ponto | PR #19 original | Experimento de referência |
| --- | --- | --- |
| Ordem de inicialização | Device, swapchain, DKSH, command lists, **queue** | Device, **queue**, depois swapchain, DKSH e command lists |
| Flags | `Graphics \| DisableZcull` | `Graphics` |
| `commandMemorySize` | `DK_QUEUE_MIN_CMDMEM_SIZE` | Default deko3d (também mínimo) |
| `perWarpScratchMemorySize` | `0` | Default deko3d |
| `flushThreshold` | Default | Default |

A configuração de referência vem de código de inicialização de deko3d usado
no Switch, **não** de um teste oficialmente aprovado no Eden. Por isso
esta mudança é um experimento de compatibilidade, não prova de correção
do emulador. Ela retira sobrescritas desnecessárias e isola `dkQueueCreate`
antes de recursos gráficos adicionais. Se o Eden falhar ainda nesta etapa,
o próximo passo é capturar stack trace no host e comparar backend Vulkan com
OpenGL ou GPU nativa; não afirmar sucesso do triângulo.

### Resultado real da configuração de referência

O workflow [#39596692296](https://github.com/lloupp/lab-NX/actions/runs/39596692296)
foi executado no Eden 0.2.1 em Ubuntu com Vulkan llvmpipe.

- **Build ARM64/DKSH:** PASS.
- **Boot do NRO:** PASS (`main-entered` e `romfs-mounted`).
- **Device:** PASS (`device-created`).
- **Fila:** FAIL — último marcador `queue-create-reference-start`; não ocorreu `queue-create-returned`.
- **Primeiro frame:** FAIL — não houve `first-deko-frame-submitted`, nem prova de pixels.

Isso demonstra que o travamento independe da criação de swapchain,
carregamento DKSH ou gravação de comandos, que agora ocorrem *depois* da fila.
A alteração é válida como isolamento, **mas não corrigiu o Eden**. O [fonte
de `dkQueueCreate`](https://github.com/devkitPro/deko3d/blob/master/source/dk_queue.cpp)
mostra que o início de `Queue::initialize` chama `nvGpuChannelCreate`, seguido
pela preparação de command memory e work buffer; a telemetria do guest
**não permite distinguir qual dessas chamadas internas parou**. Atribuir
o erro a uma dessas etapas específicas exigiria depuração do host/emulador.


### Matriz de backends Eden 0.2.1

Execução [#39598002283](https://github.com/lloupp/lab-NX/actions/runs/39598002283):

| Gate | Vulkan llvmpipe | OpenGL GLSL (Xvfb) |
| --- | --- | --- |
| NRO ARM64/DKSH | PASS | PASS (mesmo artefato) |
| Backend selecionado no log | PASS: Vulkan | PASS: OpenGL |
| `main-entered` + `romfs-mounted` | PASS | **FAIL** (host sem contexto GLX) |
| `queue-create-returned` | FAIL | **Não executou** |
| `first-deko-frame-submitted` | FAIL | **Não executou** |
| Diagnóstico do host | `std::bad_alloc` (varia por execução) | `glx: failed to create drisw screen`, `QGLXContext: Failed to create dummy context` |

**Atenção:** o segundo teste não prova falha da fila no OpenGL porque
a execução parou **antes** de entrar em `main` no guest. A workflow passou
a instalar bibliotecas Mesa/GLX adicionais e a verificar `glxinfo` em
Xvfb para corrigir essa limitação do ambiente de teste. Um backend só
pode ser declarado testado se o log confirmar o backend e o guest
registrar pelo menos `main-entered`.

### Mudanças e observabilidade

- Criação da fila imediatamente após `device-created` com evento
  `queue-create-reference-start`; somente um retorno real gera
  `queue-create-returned` e `queue-ready`.
- Trace em `sdmc:/switch/lab-nx/goldeneye/deko_boot_trace.txt` agora é
  reiniciado em cada execução, evitando falsos positivos de sessões antigas.
- Marcadores separados de `first-frame-acquire-start`,
  `first-frame-image-acquired`, `first-frame-commands-submitted` e
  `first-frame-present-returned` localizam o próximo possível bloqueio.
- Workflow de CI possui validação independente de **boot** (main + RomFS),
  **queue** (retorno do `dkQueueCreate`) e **submissão de frame** (retorno
  do `PresentImage` sem erro), com relatórios `boot-check.txt`,
  `queue-check.txt`, `frame-check.txt` e capturas PNG.
- Mesmo `first-deko-frame-submitted` **não comprova pixels na tela**.
  Uma captura efetiva com triângulo visível precisa ser inspecionada
  separadamente para afirmar primeiro frame renderizado.

O teste principal é executado pelo workflow
[goldeneye-deko3d-stage1.yml](../.github/workflows/goldeneye-deko3d-stage1.yml)
na branch da PR #19. Não houve merge nem integração de Fast3D ou da
branch local de memória `d932006`.

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
