# ECOnnect

Plataforma para gerenciamento e automação de integrações entre sistemas ECO e APIs externas. Permite criar, testar e monitorar requisições HTTP de forma centralizada.

## Funcionalidades

- Cadastro e gerenciamento de integrações com APIs REST
- Templates de requisição reutilizáveis com suporte a variáveis
- Testador de requisições com resposta em tempo real
- Dashboard com acompanhamento de execuções
- Histórico de requisições e auditoria
- Múltiplos bancos de dados (PostgreSQL e Firebird)
- Controle de acesso por usuário e empresa

## Requisitos

- Python 3.10+
- PostgreSQL 12+ (obrigatório)
- Firebird 2.5+ (opcional, para integrações com sistemas ECO locais)

## Instalação

```bash
# Clonar o repositório
git clone https://github.com/seu-usuario/econnect.git
cd econnect

# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
pip install -r backend\requirements.txt
pip install -r frontend\requirements.txt
```

### Configuração

Copie o arquivo de ambiente e ajuste as credenciais:

```bash
copy backend\.env.example backend\.env
```

Edite `backend\.env` com as configurações do seu banco PostgreSQL e demais serviços.

### Executar

```bash
start_econnect.bat
```

O servidor inicia em `http://localhost:9899` e a interface gráfica abre automaticamente.

## Build

Para gerar o executável:

```bash
scripts\build.bat
```

Para gerar o instalador:

```bash
scripts\build_installer.bat
```

## Estrutura

```
backend/         -- API FastAPI
frontend/        -- Interface PySide6
scripts/         -- Scripts de build e instalação
icons/           -- Ícones do aplicativo
```

## Licença

Uso interno.
