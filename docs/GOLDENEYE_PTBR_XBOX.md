# GoldenEye 007 PT-BR + controles tipo Xbox no lab-NX

## Estado comprovado

- ROM recebida: GoldenEye 007 N64 USA, 12.582.912 bytes, SHA-1 `abe01e4aeb033b6c0836819f549c791b26cfde83`, CRC32 `B6330846`.
- Módulo `nxlab/goldeneye_controls.py`: ações independentes dos analógicos e botões, deadzone radial, sensibilidade, inversão Y, modos hold/toggle e detecção por borda. Testes unitários do mapeamento realizados.
- Módulo `nxlab/goldeneye_ptbr.py`: aplicar patch IPS externo ao arquivo do usuário; verifica integridade da ROM e recalcula o checksum do N64.
- **Não foi obtido um patch PT-BR** nem testada ROM traduzida. O controle não foi conectado ao gameplay ou a um NRO. Nenhuma jogabilidade Switch foi demonstrada.

## Layout Xbox 3.1 Diamond adaptado aos nomes Nintendo Switch

| Switch | Função |
| --- | --- |
| Esquerdo | andar e strafe |
| Direito | olhar e mirar |
| ZL | mira (segurar) |
| ZR | disparar (segurar) |
| A | usar/interagir |
| Y | recarregar |
| B | agachar (alternar) |
| X / R | próxima arma |
| L | arma anterior |
| + | pausar |

As letras seguem o rótulo Nintendo, não a posição física das letras no Xbox. Ações como *usar* e *recarregar* são **independentes** neste adaptador; no jogo N64 original, ações podem compartilhar o mesmo botão e exigirão tratamento no engine.

Configuração inicial: deadzone de movimento 15%, olhar 12%, sensibilidade 1,0, curva linear, eixo Y não invertido. Configurações podem ser ajustadas após testes com Joy-Con/Pro Controller no Switch.

## Tradução

Existe patch brasileiro v1.3 por MJay/BR Traduções para ROM USA exata, mas ele não foi baixado aqui; não assumir formato IPS sem verificar o arquivo. Versão anterior é documentada no formato IPS. Não publicar ROM, patch de terceiros ou assets protegidos no repositório.

```bash
python -m nxlab.goldeneye_ptbr inspect "GoldenEye 007 (USA).zip"
python -m nxlab.goldeneye_ptbr apply "GoldenEye 007 (USA).zip" "traducao.ips" --out "GoldenEye 007 (PT-BR).z64"
python -m unittest discover -s tests -v
```

## Próxima integração para jogo real

1. Selecionar motor N64 ou port a partir do código C decompilado. O projeto [jkdansereau/goldeneye-pc-port](https://github.com/jkdansereau/goldeneye-pc-port) v0.5.0 oferece base PC comprovadamente jogável, mas sem build Switch/ARM64 pronto.
2. Conectar amostras de SDL/libnx às ações do adaptador. Separar contexto de menu, mira/câmera, uso, recarga e troca de arma. Validar comportamento (não só tradução de botões).
3. Aplicar patch de tradução e testar todos os menus, briefings e texturas. Verificar hashes e compatibilidade com extração de assets do port.
4. Preparar build ARM64/NRO, validar com Eden e Switch V2 real. Registrar logs, captura de frames e sessão jogável; não considerar simulação sintética prova de execução do jogo.

## Fontes

- https://www.xbox.com/pt-BR/games/goldeneye-007
- https://goldeneye.fandom.com/wiki/Control_style
- https://github.com/jkdansereau/goldeneye-pc-port
- https://joao13traducoes.com/2020/07/n64-goldeneye-007-br-traducoes/
