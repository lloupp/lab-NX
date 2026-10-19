# Castle Crashers — verificação real da cadeia LZX (M2.5)

## Evidência produzida em 19/10/2026

Usando a cópia XBLA privada fornecida pelo usuário e o algoritmo de metadados AES/XEX2 documentado no projeto Xenia:

| Verificação | Resultado |
|---|---|
| Arquivo | default.xex (765.952 bytes) |
| Payload criptografado | 757.760 bytes |
| Modo | AES-128-CBC sobre o payload XEX; chave de sessão envelopada em AES-128-ECB |
| Formato declarado | compression=normal/LZX, encryption=normal |
| Janela LZX | 32.768 bytes |
| Blocos LZX verificados | **14** |
| SHA-1 interno de cada bloco | **14 de 14 coincidentes** |
| Chunks comprimidos concatenáveis | **740.802 bytes** |
| Bytes fora da cadeia | **0** |
| Imagem PowerPC descompactada | **NÃO** |
| Código original executado | **NÃO** |
| Switch jogável | **NÃO** |

A operação privada validou as assinaturas de integridade internas dos blocos e
recuperou seus limites. SHA-1 é uma verificação de formato, **não** uma
assinatura de autenticidade do jogo. O script não publicou dados do payload.

## Ferramenta reutilizável

`nxlab/xex_lzx_preflight.py` contém o mesmo algoritmo de leitura/validação,
com tratamento de erros, limites de tamanho e sem chave embarcada.

A chave de envolvimento AES de uma fonte autorizada deve estar em um arquivo
**local, privado e externo ao repositório**, com exatamente 16 bytes, permissões
0600 no Linux. Nunca envie esse arquivo ao GitHub nem ao modelo Bonsai.

```bash
python3 -m pip install cryptography
python3 -m nxlab.xex_lzx_preflight \
  /private/default.xex \
  --wrapping-key-file /private/authorized-xex-key.bin \
  --report /private/xex-lzx-check.json
```

O relatório contém somente contagens de blocos/chunks e sinalizadores de status,
não chave, dados do jogo nem material bruto decripto.

Para testes sintéticos (sem jogos e sem chave real):

```bash
python3 -m unittest discover -s tests -v
```

## Próximo passo técnico

1. Integrar um descompressor **LZX real** para o fluxo de 740.802 bytes;
   verificar DOS/PE e cabeçalho PowerPC big-endian.
2. Produzir a imagem PowerPC **somente na área privada**.
3. Alimentar ReXGlue com imagem/XEX compatível, registrar versão exata e
   executar uma primeira função original com teste de saída.
4. Prosseguir para compatibilidade XAM/Xboxkrnl, gráficos e primeiro quadro.

Pesquisa complementar: [Xenia xex_module.cc](https://github.com/xenia-project/xenia/blob/master/src/xenia/cpu/xex_module.cc),
[360tools LZX decoder](https://github.com/sp00nznet/360tools/blob/main/tools/lzx_decompress.py),
[acceleration xex2ool](https://github.com/landaire/acceleration/tree/main/crates/xex2ool).

**Este marco confirma decriptação dos blocos e checksums, não descompressão LZX ou jogabilidade.**
