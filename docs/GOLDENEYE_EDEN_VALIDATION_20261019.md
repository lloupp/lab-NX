# GoldenEye NX — Eden v0.2.1 execução real e rastreamento ARM64

Data: 19/10/2026. Branch: `feat/goldeneye-ptbr-localization`. PR #13 (draft).

## COMPROVADO NO EDEN

O `nxlab/switch_loader/goldeneye-nx-loader.nro` compilou em devkitA64/libnx e foi executado no **Eden v0.2.1 Linux x86-64**, com Vulkan software **Mesa Lavapipe/llvmpipe 25.2.8**.

Workflow e logs (ROM ausente intencionalmente): https://github.com/lloupp/lab-NX/actions/runs/39318192666

O próprio **código AArch64 convidado** gravou em `sdmc:/switch/lab-nx/goldeneye/eden_boot_trace.txt`:

```
main-entered
console-init-ok
hid-init-ok
rom-load-failed
```

Isto comprova execução real de `main()`, inicialização de `consoleInit`, inicialização HID e tentativa de carga da ROM. `rom-load-failed` é **esperado**, porque não enviamos ROM comercial ao runner público do GitHub. O emulador reconheceu o título como `GoldenEye NX Loader (diagnostico)` e executou serviços de display.

O vídeo permaneceu preto, com 0 FPS. Portanto **não houve primeiro pixel/quadros do GoldenEye nativo no Eden**, mesmo com main em execução. Uma execução de diagnóstico é diferente de uma missão rodando.

## EXECUÇÃO LOCAL COM ROM PRIVADA

Também foi instalado Eden oficial localmente, junto ao Mesa Lavapipe empacotado pelo GitHub Actions (https://github.com/lloupp/lab-NX/actions/runs/39316271126). A ROM americana original foi montada na SD emulada sem ser enviada a repositórios.

- O Eden reconheceu o NRO e inicializou Vulkan após configurar `VK_ICD_FILENAMES`.
- Chegou a `BootGame: Booting game` e mostrou `Launching...`.
- O contêiner tem **4 GiB de limite cgroup**; o processo foi encerrado pelo OOM killer quando ultrapassou essa memória (`memory.events: oom_kill=1`). Na segunda execução interrompida previamente para evitar OOM, não houve log do convidado suficiente para confirmar que a ROM foi carregada.
- **Não** existe captura comprovada de textura Rareware executada no Eden com a ROM local.
- Uma primeira captura do **jogo original** existe, mas é referência de emulação N64 em Linux/Mupen64Plus, não Switch.

## ARQUIVOS

- `nxlab/switch_loader/source/main.c`: trace escrito pelo NRO convidado (sem copiar ROM).
- `.github/workflows/goldeneye-eden-boot.yml`: gera NRO, configura Eden + Lavapipe, executa com Xvfb e exporta capturas/logs.
- `.github/workflows/goldeneye-eden-lavapipe.yml`: empacota somente driver gráfico OSS.
- `.github/workflows/goldeneye-eden-binary.yml`: obtém Eden v0.2.1 oficial.

## PRÓXIMA PRIORIDADE

1. Validar a apresentação do framebuffer básico com uma tela de diagnóstico **sem ROM** no CI. Se a tela permanecer preta, depurar o caminho VI/Framebuffer/libnx no Eden. Não confundir tela sintética de diagnóstico com pixels originais.
2. Testar o NRO com a ROM original numa máquina Eden com mais de 4 GiB de RAM ou no Switch físico e procurar `rom-load-success` e `first-rom-sprite-frame-submitted` no arquivo `eden_boot_trace.txt`.
3. Integrar `gfx_pc.cpp` (Fast3D, cujo objeto AArch64 já compila) com um backend GPU real Switch, mapeamento de memória, shims do motor GoldenEye e sidecars derivados da ROM. Essa etapa **não foi implementada**.
4. Aplicar patch PT-BR legítimo e conectar input ao motor quando o frame do jogo estiver funcional.

Nunca enviar ROM, imagens proprietárias ou assets derivados ao CI/repositório público.
