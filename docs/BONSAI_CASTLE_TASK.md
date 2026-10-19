# Missao inicial — Castle Crashers NX, com Bonsai 4B + Pi

Voce e um agente de programacao local, limitado ao diretorio deste repositorio.
Objetivo: obter progresso **executavel e verificavel** na integracao do jogo original
no Nintendo Switch, sem relatar como concluido o que nao foi medido.

1. Leia README.md, scripts/eden_stage1_private.sh, o codigo em
   switch/castle_bootstrap e testes relacionados. Consulte os docs existentes
   apenas se forem necessarios para esta tarefa.
2. Confirme o estado atual: o NRO ARM64 inicial e o interpretador PowerPC
   restrito nao equivalem a port jogavel. Verifique que provas realmente existem.
3. Identifique UM menor bloqueio tecnico resolvivel agora para avancar da
   interpretacao restrita do PPC para um trecho real do jogo. Priorize runtime,
   despachante de chamadas e seguranca de memoria antes de telas ilustrativas.
4. Implemente a menor correcao util no codigo real e acrescente teste focado.
   Rode primeiro o teste afetado, depois os testes disponiveis. Tente compilacao
   devkitPro e Eden SOMENTE se as ferramentas estiverem instaladas.
5. Se houver copia privada autorizada de XEX/PE no computador, nao a mova
   para o repositorio; nao inclua codigo de jogo derivado, ROM, ISO, chaves,
   arte, executaveis comerciais ou capturas privadas nos commits.
6. Registre no resumo final: arquivos alterados, comandos executados,
   resultado de cada teste, evidencia de guest PPC original, evidencia de
   imagem real do jogo (se houver), bloqueios e proximo passo especifico.

Regras: nao fabricar screenshots, nao substituir gameplay real por desenho
sintetico, nao modificar componentes fora do lab-NX, nao publicar/mesclar/push
sem ordem explicita do usuario. Evite varrer pastas grandes ou ler binarios
inteiros para o prompt. Trabalhe uma etapa por vez; se houver bloqueio, pare
e informe o dado ou ferramenta que falta.
