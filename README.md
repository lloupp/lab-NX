# lab-NX

Laboratório de desenvolvimento, execução e diagnóstico de aplicativos homebrew e ports para Nintendo Switch.

## Objetivo
Criar um pipeline reproduzível: **código-fonte → compilação ARM64 (devkitPro/libnx) → NRO → execução no Eden → análise de logs/capturas → validação no Nintendo Switch físico**.

O laboratório não é um emulador novo nem converte jogos de Xbox 360/PS3 automaticamente. Integra ferramentas externas e testes por etapas.

## Componentes previstos

- **devkitPro + libnx + SDL2/deko3d:** compilação e APIs do Switch.
- **Eden:** execução e depuração em emulador, como dependência externa.
- **nsemu:** executor experimental alternativo, quando aplicável.
- **nxlab (Python):** diagnósticos, build, testes, registro de logs e relatórios.
- **Pong SDL2:** jogo piloto para verificar gráficos, entrada, física e ciclo de execução.
- **Nintendo Switch V2:** validação final em hardware real.

## Evidências e limites

Na validação local inicial do Pong, passaram 10 testes do orquestrador e os testes de física, renderização SDL2 em Linux, execução de 180 quadros, movimento via teclado e pausa.

**Ainda não foram comprovadas:** compilação do arquivo `.nro`, execução no Eden e execução no Switch físico. Essas etapas precisam de devkitPro/Docker, Eden e testes no console real, respectivamente.

## Regras do projeto

- Não publicar ISOs, ROMs, XEX, EBOOT, NSP, chaves, firmware ou quaisquer recursos protegidos dos jogos.
- Preservar as licenças e avisos de autoria dos componentes externos.
- Manter logs, artefatos e dados privados em diretórios ignorados pelo Git.
- Marcar claramente cada resultado como **testado**, **parcial** ou **não testado**.
- Nunca confundir um teste de demonstração/sintético com execução do jogo original.

## Próximas etapas

1. Importar o código-fonte revisado do NX-Lab v0.2.1 e Pong.
2. Validar toolchain ARM64 e geração de NRO.
3. Executar smoke test no Eden e guardar capturas/logs.
4. Executar o NRO no Switch físico com hbmenu/NetLoader.
5. Adicionar adaptadores isolados para projetos maiores, sem distribuir arquivos dos jogos.

Projeto de testes e interoperabilidade. Não afiliado à Nintendo.
