# Castle Crashers — M2: análise XEX2 (19/10/2026)

**Fonte analisada:** cópia do arquivo XBLA mantida de forma privada pelo usuário no Google Drive; os bytes do jogo, chaves e recursos não fazem parte deste repositório.

## Resultados confirmados no arquivo real

| Campo | Valor |
|---|---|
| Formato | XEX2 |
| Executável | default.xex, 765.952 bytes |
| Title ID | 584108B7 |
| Module flags | 0x00000001 (título) |
| Base | 0x82000000 |
| Entry point | 0x820B7090 |
| Imagem declarada | 2.949.120 bytes |
| Payload start | 0x2000 |
| Criptografia declarada | Normal (ID 1) |
| Compressão declarada | Normal/LZX (ID 2) |
| Janela LZX | 32.768 bytes |
| Primeiro bloco compactado | 59.392 bytes |
| Cabeçalhos opcionais | 15 |
| Imports do XEX | 2 bibliotecas |

### Imports por biblioteca

- `xam.xex`: **146 entradas** de importação.
- `xboxkrnl.exe`: **255 entradas** de importação.
- Total: **401 entradas**; não equivale a 401 APIs únicas ou ordinais já identificados.

### Bibliotecas estáticas detectadas nos metadados

`XAPILIB`, `D3D9`, `XGRAPHC`, `XBOXKRNL`, `XNET`, `XAUD`, `XMP`, `XONLINE`, `QNET`, `XRNSS`, `XRNMS`, `LIBCPMT`, `XHV`.

O nome de uma biblioteca estática **não comprova** a presença/uso de toda a sua API no jogo.

## Comandos M2

Após o M1 extrair `default.xex` para armazenamento **privado**:

```bash
python3 -m nxlab.m2 /private/default.xex --report /private/castle-m2.json
python3 -m unittest discover -s tests -v
```

O relatório JSON contém **somente metadados não sensíveis**, nunca conteúdo de arquivos, assinaturas, material criptográfico ou dados de licença. O caminho de origem também não aparece no JSON. O parser é read-only, limitado por tamanho, com validações de limites e testes de dados sintéticos.

## ReXGlue — integração seguinte

A referência indicada é [rexglue/rexglue-sdk](https://github.com/rexglue/rexglue-sdk), que atualmente oferece importação de XEX e geração de C++. Esse SDK evolui rapidamente. Um teste de código gerado deve registrar **versão exata e hash do artefato**.

**Ainda não foi executado** o ReXGlue com o XEX do Castle Crashers neste laboratório: o executável `rexglue` não está instalado no ambiente de testes. O fato de o SDK alegar suporte a XEX não comprova que vá processar este jogo.

Próximo marco:
1. disponibilizar SDK ReXGlue isolado e registrar sua versão;
2. tentar a leitura e extração via SDK; verificar se gera imagem PE com seções PPC válidas;
3. capturar diagnósticos de imports/ordinais e limitações do codegen;
4. executar uma função realmente recompilada em um teste controlado, somente após validação.

## Estado/limites

- **Comprovado:** leitura do XEX real, criptografia/compressão declaradas, dependências XAM/Xboxkrnl, endereço de entrada, cabeçalho de segurança, tamanho da imagem e bibliotecas estáticas.
- **Comprovado localmente:** 20 testes do pacote maior (14 existentes + 6 do M2) passaram. A variante reduzida publicada está sob teste independente da CI.
- **Não comprovado:** descriptografia, LZX aplicado aos dados, extração da imagem PPC, resolução de ordinais, recompilação, funcionamento do jogo, Eden ou hardware.
- Segurança: não divulgar XEX, arquivos comerciais, chaves, conteúdo, material de licença ou outputs que embutam assets.

Formato e offsets verificados com estruturas XEX2 do projeto [Xenia](https://github.com/xenia-project/xenia).
