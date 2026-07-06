# release-manager

Skill de gerenciamento de versoes e patchnotes.

## Gatilho

A cada 10 solicitacoes do usuario (contador persistido em `.opencode/counters/request-count.json`), execute o fluxo abaixo automaticamente, a menos que o usuario peca explicitamente para nao fazer.

## Contador

- Usar arquivo `.opencode/counters/request-count.json` com formato `{ "count": 0 }`
- Incrementar a cada interacao com o usuario
- Quando count >= 10, disparar o release flow e resetar para 0

## Release Flow

### 1. Levantar mudancas

```bash
# Ler commits recentes desde o ultimo tag de versao
git describe --tags --abbrev=0
git log <ultimo-tag>..HEAD --oneline

# Ler arquivos modificados nao commitados
git status --short
git diff --stat

# Verificar VERSION atual
cat VERSION

# Verificar INDEX.md para determinar proxima versao
cat patchnotes/INDEX.md
```

### 2. Determinar nova versao

- Ler `patchnotes/README.md` para seguir as regras de SemVer
- Seguir o template la definido para o arquivo de patchnote
- Incrementar conforme SemVer (major/minor/patch) baseado nas mudancas
- Atualizar `VERSION` na raiz do projeto

### 3. Criar patchnote

Criar `patchnotes/vX.Y.Z.md` seguindo este formato (sem emojis, sem acentos para evitar problemas de encoding):

```
# vX.Y.Z - Titulo da Versao

**Data**: YYYY-MM-DD

## Novidades
- (item)

## Melhorias
- (item)

## Correcoes
- (item)

## Dependencias
- (item)

## Arquivos Modificados
- (item)

## Arquivos Criados
- (item)
```

### 4. Atualizar INDEX.md

Adicionar entrada no topo da tabela em `patchnotes/INDEX.md`.

### 5. Commit

Antes de commitar, SEMPRE:

1. Revisar `git status` e `git diff` para cada arquivo que sera commitado
2. Verificar se ha dados sensiveis: senhas, tokens, chaves de API, conexoes de banco, caminhos absolutos com nomes de usuario
3. NUNCA commitar arquivos que contenham:
   - `.env` ou variaveis de ambiente reais
   - Tokens ou chaves de API
   - Senhas em texto claro
   - Caminhos com nome de usuario pessoal (ex: `C:\Users\Suportee`)
   - Arquivos gerados por ferramentas (`graphify-out/`, `__pycache__/`, etc.)

```bash
git add patchnotes/vX.Y.Z.md patchnotes/INDEX.md VERSION
```

4. Mensagem de commit deve seguir o padrao:

```
<tipo>(<escopo>): breve descricao

- bullet points detalhando cada mudanca
- arquivos principais envolvidos
- motivo das alteracoes
```

Tipos: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`, `style`

Exemplo:
```
docs(patchnotes): versao v1.4.0 com graphify integration

- Instalado graphify para geracao de grafo de conhecimento do codigo
- Modificado AGENTS.md com instrucoes de auto-update
- Adicionado git hooks (post-commit, post-checkout) para rebuild automatico
- Criado skill graphify-auto-update para OpenCode
```

5. Incluir tambem no commit todos os arquivos de codigo alterados que fazem parte desta versao (exceto os gerados por ferramentas)

## Seguranca

- Usar `git diff -- <caminho>` para inspecionar cada arquivo antes de adicionar
- Verificar se ha numeros de telefone, emails pessoais, ou caminhos com nomes de usuario
- Se encontrar dado sensivel, pular o arquivo e avisar o usuario
