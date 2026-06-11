# Patchnotes — ECOnnect

Estrutura e regras para documentação de versões do ECOnnect.

---

## Estrutura

```
patchnotes/
├── README.md            ← Este arquivo (regras e template)
├── INDEX.md             ← Índice cronológico de todas as versões
├── v1.0.0.md            ← Patchnote da versão 1.0.0
├── v1.1.0.md            ← Patchnote da versão 1.1.0
└── ...
```

## Regras

### 1. Nomenclatura dos arquivos

- Formato: `vX.Y.Z.md` (ex: `v1.2.3.md`)
- Para versões pré-lançamento: `vX.Y.Z-rc.N.md` ou `vX.Y.Z-beta.N.md`
- O arquivo `INDEX.md` é manual — atualizado a cada novo patchnote.

### 2. Versionamento (SemVer)

Seguimos [Semantic Versioning 2.0.0](https://semver.org/):

| Incremento | Quando aplicar |
|-------------|---------------|
| **Major (X)** | Mudança incompatível na API, banco de dados, ou fluxo principal |
| **Minor (Y)** | Nova funcionalidade compatível com versões anteriores |
| **Patch (Z)** | Correção de bugs sem quebra de compatibilidade |

### 3. O que documentar em cada versão

| Seção | Obrigatório? | Descrição |
|-------|:---:|-----------|
| **Data** | Sim | Data de lançamento no formato `YYYY-MM-DD` |
| **Novidades** | Sim | Novas funcionalidades introduzidas |
| **Melhorias** | Sim | Aprimoramentos em funcionalidades existentes |
| **Correções** | Sim | Bugs corrigidos (referenciar issue se houver) |
| **Breaking Changes** | Se houver | Mudanças que exigem ação manual do usuário |
| **Procedimentos** | Se houver | Passos necessários na atualização (migração de BD, config, etc.) |
| **Dependências** | Se houver | Alterações em bibliotecas, serviços externos, ou requisitos de sistema |

### 4. Checklist ao criar uma nova versão

- [ ] Incrementar `VERSION` na raiz do projeto
- [ ] Executar build e testar
- [ ] Revisar se o instalador reflete a nova versão (`build_installer.bat`)
- [ ] Criar arquivo `patchnotes/vX.Y.Z.md` seguindo o template
- [ ] Atualizar `patchnotes/INDEX.md` com a nova entrada
- [ ] Se houver breaking changes, destacar no topo do patchnote
- [ ] Se houver procedimentos de atualização, detalhar passo a passo

---

## Template Padrão

```markdown
# ECOnnect vX.Y.Z

**Data**: YYYY-MM-DD

## Novidades
- (nova funcionalidade 1)
- (nova funcionalidade 2)

## Melhorias
- (melhoria 1)
- (melhoria 2)

## Correções
- (correção 1)
- (correção 2)

## Breaking Changes
- (mudança que requer ação manual, se houver)

## Procedimentos de Atualização
1. (passo 1)
2. (passo 2)

## Dependências
- (alterações em libs, serviços, ou requisitos)
```

---

## Fluxo de Criação

Sempre que for solicitado criar uma nova versão:

1. **Ler este README** para seguir as regras e o template.
2. **Ler o `patchnotes/INDEX.md`** para saber o histórico e determinar a próxima versão.
3. **Ler o arquivo `VERSION`** na raiz do projeto para confirmar a versão atual.
4. **Analisar o código** (commits recentes, alterações) para levantar as mudanças.
5. **Criar o arquivo** `patchnotes/vX.Y.Z.md` conforme o template.
6. **Atualizar** `patchnotes/INDEX.md`.
7. Incluir informações relevantes sobre procedimentos de atualização sempre que necessário.
