# v2.0.0 — ECOnnect Billing + Template Engine

## Novas Funcionalidades

### 🧩 BillingTemplate — Templates de Cobrança no Banco
- Criado modelo `BillingTemplate` no banco de dados PostgreSQL
- API REST completa: `GET/POST/PUT/DELETE /api/client-billing/templates`
- Templates agora são referenciados por ID, não mais copiados como snapshot
- Ao editar um template no editor, os grupos vinculados refletem a alteração automaticamente

### 🔗 Vinculação Dinâmica Template-Grupo
- Adicionado `billing_template_id` como FK em `BillingGroup` e `ClientBillingConfig`
- Ao criar/editar um grupo, o template é resolvido dinamicamente do banco
- `send_test()` e `_send_message()` consultam o template atual no banco a cada execução
- Se o `billing_template_id` não existir, exibe erro claro no lugar de fallback silencioso

### 🔥 Teste com Dados Reais do Firebird
- `send_test()` agora consulta o Firebird igual ao scheduler faz
- Busca pendências reais do cliente via `COBRANCA_SQL`
- Substitui placeholders com dados reais do banco
- Firebird offline → fallback para dados do config (nome/telefone)
- Placeholder: `{{phone}}` substitui, `{phone}` mantém literal
- Placeholder com chave simples OU dupla são aceitos

### 🎨 Loading Popup Redesenhado
- Nova animação: 2 logos da ECOnnect com listras se separam, giram 360° e voltam
- 5 listras visíveis, ciclo de 2s, mais fluido (30fps)
- Texto "Carregando..." com pontinhos animados
- Cor branca para melhor contraste
- Timer de segurança para evitar loading infinito

### 📊 Tabela de Clientes nos Grupos
- Colunas reorganizadas com proporções inteligentes:
  - Nome ocupa espaço flexível (Stretch)
  - Telefone, Status, Próx. Cobrança com larguras fixas maiores
- Código e Editar com tamanhos confortáveis
- Clique no corpo do grupo expande/minimiza (não só na setinha)

## Correções de Bugs

### 🔴 Críticos

| Bug | Descrição | Solução |
|---|---|---|
| **BUG 2** | `update_group` apagava `BillingGroupClient` e recriava SEM `config_id` | Agora preserva `config_id` dos clientes existentes |
| **BUG 1** | Placeholder `{phone}` e `{{phone}}` inconsistentes entre frontend e backend | Ambos os formatos são aceitos e substituídos |
| **Loading infinito** | Loading nunca fechava após processo terminar | Relay não é mais destruído antes do tempo; `closed` flag evita duplo close |

### 🟡 Altos

| Bug | Descrição | Solução |
|---|---|---|
| **BUG 4** | `create_config()` ignorava `billing_template_id` | Agora salva o campo no banco |
| **BUG 5** | Frontend não enviava `billing_template_id` ao criar configs | Enviado nos payloads de criação |
| **BUG 3** | `register_group` criava config duplicado em cada chamada | Pula clientes que já têm `config_id` |
| **BUG 14** | `_ab_save_group` destruía `config_id` ao salvar | BUG 2 corrigido → `config_id` preservado |

### 🟢 Médios

- `flow_id` extraído do body JSON primeiro, fallback pra header
- Sincronização de template com backend ao salvar via editor
- `_resolve_template_data()` sem fallback — erro explícito se sem vínculo

## Detalhes Técnicos

### Modelos

```
BillingTemplate
├── name, method, url, headers, body, tag
├── api_token, flow_id
├── offset_days, send_time
└── eco_empresa, created_by, created_at, updated_at

BillingGroup / ClientBillingConfig
├── billing_template_id (FK → BillingTemplate)
└── ... (demais campos de template como snapshot fallback)
```

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/client-billing/templates` | Listar templates |
| `POST` | `/api/client-billing/templates` | Criar template |
| `PUT` | `/api/client-billing/templates/{id}` | Atualizar template |
| `DELETE` | `/api/client-billing/templates/{id}` | Excluir template |

---

**Data:** 22/07/2026
