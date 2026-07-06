# graphify-auto-update

Auto-executa `graphify update .` sempre que o codigo for modificado.

## Regras

1. Após qualquer modificação em arquivos de código (criar, editar, renomear, excluir), execute `graphify update .` ao final da tarefa.
2. O `graphify update .` é AST-only (tree-sitter), 100% local, sem custo de API.
3. Não precisa rodar a cada edição individual — apenas uma vez ao final do conjunto de mudanças.
4. Se o gráfico já existir em `graphify-out/`, o update é incremental e rápido.
5. Ignore esta regra se o usuário explicitamente disser para não atualizar o grafo.
