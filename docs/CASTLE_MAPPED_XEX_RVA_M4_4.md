# M4.4 — Correção do endereçamento do XEX descompactado

**Data:** 20/10/2026. Evidência retirada exclusivamente da imagem privada do Castle Crashers fornecida pelo usuário. Imagem de 2.949.120 bytes, SHA-256: 964aa6b9d993beb8ad9a986d0555e47c36b4b5716b0b8377c6631ae8b39c03ab.

## Defeito comprovado

A imagem produzida pela descompactação XEX2/LZX é uma **imagem de memória PE, organizada por RVA**, não o mesmo layout de arquivo bruto PE. Base da imagem 0x82000000. Assim, a função 0x82053A88 está no offset 0x53A88 do arquivo decodificado, e NÃO no offset 0x4B488 obtido com PointerToRawData da seção .text.

No offset correto, o LLVM PowerPC desmonta uma sequência equivalente a li r3,4; blr. O ReXGlue oficial também identifica e recompila a função 0x82053A88. No offset incorreto existiam zeros. O código anterior extraía instruções de posições indevidas.

**As alegações anteriores M2.8/M4.3 sobre funções nos endereços 0x8208EE10, 0x820E4520 e 0x8205A08C foram invalidadas.** Elas não demonstravam a execução das instruções efetivamente presentes nesses endereços. A instrução real em 0x8208EE10 é um desvio, e o interpretador corrigido rejeita a função por opcode não suportado.

## Correções implementadas

- switch/castle_bootstrap/source/ppc_pe.c: lê bytes originais a partir de RVA da seção executável.
- nxlab/ppc_leaf.py: usa endereços RVA para extração, tradução e testes.
- nxlab/pe_elf.py: envolve os bytes reais da imagem mapeada num ELF PowerPC privado.
- nxlab/import_contracts.py: lê descritores por RVA. Teste independente no XEX original confirmou 401 slots, 206 descritores, 195 thunks e **zero diferenças nos valores dos descritores** entre mapeamento antigo e corrigido.
- tests/test_ppc_pe.c, tests/test_ppc_leaf.py, tests/test_lzx_image.py e tests/test_import_contracts.py: os PE sintéticos agora têm instruções inválidas no antigo endereço de arquivo, detectando regressões.
- switch/castle_bootstrap/source/main.c: só anuncia execução verificada com Title ID legítimo e **duas funções** PPC originais com resultados corretos.

## Testes reais independentes

Foi recuperada a imagem original somente no diretório privado. O ReXGlue 0.10.0.24-dev.gbd833a2 recompilou o XEX (17 unidades C++). A função original 0x82053A88 foi extraída da saída genuína ReXGlue para um teste privado, compilada num ELF nativo AArch64 Linux e executada sob QEMU, com resultado 4.

O **mesmo fonte C do interpretador compilado no NRO** também foi compilado para ARM64 Linux e executado no QEMU contra a imagem privada original. Resultados:

| Endereço PPC | Entrada r3 | ARM64/QEMU | Host x86-64 |
| --- | ---: | ---: | ---: |
| 0x82053A88 | 17 | 4 | 4 |
| 0x82053A98 | 1 | 0 | 0 |
| 0x82053AA0 | 4294967295 | 5 | 5 |

O endereço incorreto 0x8208EE10 agora termina corretamente com PPC_PE_UNSUPPORTED.

## Validação pendente no Eden

A versão corrigida do NRO ARM64, com os recursos privados no SD emulado e XEX Castle Title ID 584108B7, exige as duas verificações antes de exibir:

**Private PowerPC PE: LEAF EXECUTED / VERIFIED**

- função 0x82053A88 retorna r3=4;
- função 0x82053AA0 retorna r3=5.

O NRO bootstrap já rodou no Eden com OpenGL, mas o teste da imagem original dentro do Eden continua pendente por limite de 4 GiB de RAM na sessão local (Eden usa cerca de 4,4 GiB residente). A execução de código PPC original em ARM64 Linux/QEMU **não é** execução do jogo dentro do Eden nem prova de gameplay.

Nenhum arquivo comercial, imagem PowerPC decodificada, código C++ derivado ou binário derivado do game foi publicado.
