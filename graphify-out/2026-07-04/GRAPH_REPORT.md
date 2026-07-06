# Graph Report - ECOnnect  (2026-07-04)

## Corpus Check
- 118 files · ~53,111 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1047 nodes · 2673 edges · 75 communities (61 shown, 14 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 223 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9222a0ef`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_DashboardView|DashboardView]]
- [[_COMMUNITY_MainWindow|MainWindow]]
- [[_COMMUNITY_MundoBotsView|MundoBotsView]]
- [[_COMMUNITY_integrations.py|integrations.py]]
- [[_COMMUNITY_templates.py|templates.py]]
- [[_COMMUNITY_Theme|Theme]]
- [[_COMMUNITY_QLabel|QLabel]]
- [[_COMMUNITY_requests.py|requests.py]]
- [[_COMMUNITY_FirebirdClient|FirebirdClient]]
- [[_COMMUNITY_StyledTable|StyledTable]]
- [[_COMMUNITY_database.py|database.py]]
- [[_COMMUNITY_User|User]]
- [[_COMMUNITY_show_error|show_error]]
- [[_COMMUNITY_RequestTesterView|RequestTesterView]]
- [[_COMMUNITY_settings.py|settings.py]]
- [[_COMMUNITY_show_success|show_success]]
- [[_COMMUNITY_eco_auth.py|eco_auth.py]]
- [[_COMMUNITY_CalculadoraDialog|CalculadoraDialog]]
- [[_COMMUNITY_Melhorias Técnicas|Melhorias Técnicas]]
- [[_COMMUNITY_sql_variables.py|sql_variables.py]]
- [[_COMMUNITY_UserSettingsView|UserSettingsView]]
- [[_COMMUNITY_deps.py|deps.py]]
- [[_COMMUNITY_LogViewerWindow|LogViewerWindow]]
- [[_COMMUNITY__hex_to_rgb|_hex_to_rgb]]
- [[_COMMUNITY_auth.py|auth.py]]
- [[_COMMUNITY_RequisicoesView|RequisicoesView]]
- [[_COMMUNITY_Request|Request]]
- [[_COMMUNITY_StreamDialog|StreamDialog]]
- [[_COMMUNITY_main.py|main.py]]
- [[_COMMUNITY_.__init__|.__init__]]
- [[_COMMUNITY_VariablePickerDialog|VariablePickerDialog]]
- [[_COMMUNITY_users.py|users.py]]
- [[_COMMUNITY_barcode.py|barcode.py]]
- [[_COMMUNITY_cobranca.py|cobranca.py]]
- [[_COMMUNITY_ApiClient|ApiClient]]
- [[_COMMUNITY_sql_variable_dialogs.py|sql_variable_dialogs.py]]
- [[_COMMUNITY_TemplateListView|TemplateListView]]
- [[_COMMUNITY_AutoCompleteTextEdit|AutoCompleteTextEdit]]
- [[_COMMUNITY_ECOnnect v1.1.0|ECOnnect v1.1.0]]
- [[_COMMUNITY_Melhorias|Melhorias]]
- [[_COMMUNITY_._open_preview_dialog|._open_preview_dialog]]
- [[_COMMUNITY_Patchnotes — ECOnnect|Patchnotes — ECOnnect]]
- [[_COMMUNITY_ECOnnect|ECOnnect]]
- [[_COMMUNITY_RequestFormView|RequestFormView]]
- [[_COMMUNITY_Novidades|Novidades]]
- [[_COMMUNITY_ScheduleWidget|ScheduleWidget]]
- [[_COMMUNITY_INDEX|INDEX.md]]
- [[_COMMUNITY_ECOnnect v1.2.2|ECOnnect v1.2.2]]
- [[_COMMUNITY_config.py|config.py]]
- [[_COMMUNITY_template_api.py|template_api.py]]
- [[_COMMUNITY_ECOnnect v1.2.0|ECOnnect v1.2.0]]
- [[_COMMUNITY_get_company_config|get_company_config]]
- [[_COMMUNITY_N8nLoadingDialog|N8nLoadingDialog]]
- [[_COMMUNITY_N8nResponseDialog|N8nResponseDialog]]
- [[_COMMUNITY_Melhorias|Melhorias]]

## God Nodes (most connected - your core abstractions)
1. `MundoBotsView` - 74 edges
2. `User` - 67 edges
3. `show_error()` - 67 edges
4. `run_in_thread()` - 49 edges
5. `MainWindow` - 41 edges
6. `show_success()` - 35 edges
7. `RequisicoesView` - 30 edges
8. `IntegrationService` - 25 edges
9. `AutoCompleteTextEdit` - 25 edges
10. `FirebirdClient` - 24 edges

## Surprising Connections (you probably didn't know these)
- `get_me()` --references--> `User`  [EXTRACTED]
  backend/app/routers/auth.py → backend/app/models/user.py
- `login()` --indirect_call--> `User`  [INFERRED]
  backend/app/routers/auth.py → backend/app/models/user.py
- `RequestService` --uses--> `IntegrationService`  [INFERRED]
  backend/app/services/request_service.py → backend/app/services/integration_service.py
- `MainWindow` --uses--> `Theme`  [INFERRED]
  frontend/app/app.py → frontend/app/core/theme.py
- `MainWindow` --uses--> `BoletoWatcher`  [INFERRED]
  frontend/app/app.py → frontend/app/services/boleto_watcher.py

## Import Cycles
- None detected.

## Communities (75 total, 14 thin omitted)

### Community 0 - "DashboardView"
Cohesion: 0.12
Nodes (11): _ActivityEntry, _card_qss(), _chart_card_qss(), _ChartCard, DashboardView, _MetricCard, _PanelSection, QWidget (+3 more)

### Community 1 - "MainWindow"
Cohesion: 0.06
Nodes (6): MainWindow, LoadingOverlay, LogViewerWindow, Sidebar, QMainWindow, Signal

### Community 3 - "integrations.py"
Cohesion: 0.17
Nodes (23): IntegrationConfig, _build_response(), create_integration(), delete_integration(), get_integration(), get_integration_by_template(), list_integrations(), AsyncSession (+15 more)

### Community 4 - "templates.py"
Cohesion: 0.07
Nodes (54): MetaMessage, Template, get_credentials(), list_messages(), AsyncSession, save_credentials(), send_message(), sync_template() (+46 more)

### Community 5 - "Theme"
Cohesion: 0.09
Nodes (16): Enum, apply_palette(), _build_app_qss(), _build_palette(), _set_titlebar_theme(), Theme, ThemeManager, ThemeType (+8 more)

### Community 6 - "QLabel"
Cohesion: 0.15
Nodes (5): QLabel, QPushButton, QTableWidget, QTextEdit, QWidget

### Community 7 - "requests.py"
Cohesion: 0.43
Nodes (13): User, _build_response(), cancel_request(), create_request(), get_request(), get_request_history(), list_requests(), AsyncSession (+5 more)

### Community 8 - "FirebirdClient"
Cohesion: 0.12
Nodes (18): FileSystemEventHandler, FirebirdClient, _log_fb(), _build_pdf_path(), buscar_codigo_e_linha(), _extrair_linha_do_texto(), _linha_para_barcode(), date (+10 more)

### Community 9 - "StyledTable"
Cohesion: 0.19
Nodes (6): RequestEditDialog, RequestListView, _status_colors(), show_confirm(), HistoryDialog, _status_colors()

### Community 10 - "database.py"
Cohesion: 0.19
Nodes (12): Base, AuditLog, RequestParameterValue, list_logs(), AsyncSession, _company_filter(), dashboard_summary(), AsyncSession (+4 more)

### Community 12 - "show_error"
Cohesion: 0.16
Nodes (3): AdminUsersView, UserEditDialog, StyledTable

### Community 13 - "RequestTesterView"
Cohesion: 0.12
Nodes (5): any, KeyValueEditor, _RequestResultEvent, RequestTesterView, _result_qss()

### Community 15 - "show_success"
Cohesion: 0.30
Nodes (4): get_company_config(), _build_sidebar_qss(), _hex_to_rgb(), show_success()

### Community 16 - "eco_auth.py"
Cohesion: 0.17
Nodes (13): hash_senha(), listar_empresas(), _log_eco(), login_completo(), _obter_nome(), _obter_role(), senha_supervisor(), _upsert_autonomias() (+5 more)

### Community 17 - "CalculadoraDialog"
Cohesion: 0.14
Nodes (4): CalculadoraDialog, _FilterPopup, ScheduleDialog, QDialog

### Community 18 - "Melhorias Técnicas"
Cohesion: 0.11
Nodes (17): Arquivos Criados, Arquivos Modificados, 🗄️ Banco de Dados, 🐞 Bug de deduplicação de parcelas, 🧮 Calculadora Animada, Correções, 🛠️ Código de Barras (barcode.py), 🔗 Dependências (+9 more)

### Community 19 - "sql_variables.py"
Cohesion: 0.29
Nodes (15): SqlVariable, _build_list_response(), _build_response(), create_sql_variable(), delete_sql_variable(), get_sql_variable(), list_sql_variables(), AsyncSession (+7 more)

### Community 21 - "deps.py"
Cohesion: 0.29
Nodes (11): get_db(), get_current_user(), AsyncSession, require_admin(), CompanyConfig, _build_response(), get_company_config(), AsyncSession (+3 more)

### Community 22 - "LogViewerWindow"
Cohesion: 0.10
Nodes (6): ChatBubble, ContactItem, ECOchatView, MetaView, TemplateFormView, WhatsWebView

### Community 23 - "_hex_to_rgb"
Cohesion: 0.08
Nodes (5): eco_login(), update_company_config(), Path, _resolve_env(), Settings

### Community 24 - "auth.py"
Cohesion: 0.13
Nodes (21): do_run_migrations(), run_async_migrations(), run_migrations_online(), Config, Path, _resolve_env_file(), Settings, eco_login() (+13 more)

### Community 25 - "RequisicoesView"
Cohesion: 0.16
Nodes (4): _extract_variables(), StreamDialog, _substitute_variables(), TriggerVariablesDialog

### Community 26 - "Request"
Cohesion: 0.35
Nodes (4): Request, AsyncSession, UUID, RequestService

### Community 28 - "main.py"
Cohesion: 0.26
Nodes (9): _backend_log(), _ensure_permissions(), lifespan(), Write directly to econnect.log (same file as frontend)., _run_migrations(), _scheduler_loop(), AsyncSession, receive_webhook() (+1 more)

### Community 29 - ".__init__"
Cohesion: 0.14
Nodes (5): LogSignal, N8nWorker, StreamWorker, _SignalRelay, QObject

### Community 30 - "VariablePickerDialog"
Cohesion: 0.21
Nodes (3): N8nResponseDialog, QFrame, ScheduleWidget

### Community 31 - "users.py"
Cohesion: 0.33
Nodes (10): delete_user(), list_users(), AsyncSession, UUID, update_user(), update_user_permissions(), Config, UserPermissionsUpdate (+2 more)

### Community 32 - "barcode.py"
Cohesion: 0.33
Nodes (11): calcular_codigo_barras(), _calcular_fator(), calcular_linha_digitavel(), _campo_livre_001(), _campo_livre_748(), _campo_livre_756(), _extrair_banco(), _formatar_valor() (+3 more)

### Community 33 - "cobranca.py"
Cohesion: 0.27
Nodes (7): check_sent(), CheckSentRequest, CheckSentResponse, AsyncSession, CobrancaService, AsyncSession, UUID

### Community 35 - "sql_variable_dialogs.py"
Cohesion: 0.29
Nodes (5): create_sql_variable(), delete_sql_variable(), list_sql_variables(), update_sql_variable(), _parse_column_names()

### Community 39 - "ECOnnect v1.1.0"
Cohesion: 0.18
Nodes (11): Aba de Requisições, Abas de Administração, Correções, Dependências, ECOnnect v1.1.0, Janela Frameless, Melhorias, Módulo Mundo dos Bots (+3 more)

### Community 40 - "Melhorias"
Cohesion: 0.18
Nodes (10): Correções, ECOnnect v1.2.1, Filtros e Busca, Histórico de Envios, Interface de Agendamento, Labels e Nomenclatura, Melhorias, Novidades (+2 more)

### Community 42 - "Patchnotes — ECOnnect"
Cohesion: 0.20
Nodes (9): 1. Nomenclatura dos arquivos, 2. Versionamento (SemVer), 3. O que documentar em cada versão, 4. Checklist ao criar uma nova versão, Estrutura, Fluxo de Criação, Patchnotes — ECOnnect, Regras (+1 more)

### Community 43 - "ECOnnect"
Cohesion: 0.20
Nodes (9): Build, Configuração, ECOnnect, Estrutura, Executar, Funcionalidades, Instalação, Licença (+1 more)

### Community 44 - "RequestFormView"
Cohesion: 0.12
Nodes (4): AdminTabsView, RequestFormView, show_error(), run_in_thread()

### Community 45 - "Novidades"
Cohesion: 0.22
Nodes (9): Dashboard Expandido, Diálogo de Agendamento, Gerenciamento de Permissões por Aba, Gerenciamento de Variáveis SQL, Módulo Cobrança (Backend), Módulo Meta (WhatsApp Business API), Novidades, Requisições como View Independente (+1 more)

### Community 49 - "ScheduleWidget"
Cohesion: 0.18
Nodes (10): 1. Levantar mudancas, 2. Determinar nova versao, 3. Criar patchnote, 4. Atualizar INDEX.md, 5. Commit, Contador, Gatilho, Release Flow (+2 more)

### Community 50 - "INDEX.md"
Cohesion: 0.25
Nodes (4): Índice de Versões — ECOnnect, Dependências, ECOnnect v1.0.0, Novidades

### Community 51 - "ECOnnect v1.2.2"
Cohesion: 0.25
Nodes (7): Auto-fill de URL por Tipo, Correções, ECOnnect v1.2.2, Integração com IA (Ollama), Integração com n8n, Novidades, Técnico

### Community 55 - "ECOnnect v1.2.0"
Cohesion: 0.33
Nodes (6): Breaking Changes, Correções, Dependências, ECOnnect v1.2.0, Melhorias, Procedimentos de Atualização

### Community 61 - "Melhorias"
Cohesion: 0.50
Nodes (4): Diálogo de Edição, Fluxo de Execução, Melhorias, Tabela de Requisições

## Knowledge Gaps
- **85 isolated node(s):** `Config`, `Config`, `Config`, `Config`, `Config` (+80 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MundoBotsView` connect `MundoBotsView` to `MainWindow`, `AppLogger`, `QLabel`, `FirebirdClient`, `RequestFormView`, `show_success`, `CalculadoraDialog`, `dashboard.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `show_error()` connect `RequestFormView` to `DashboardView`, `MainWindow`, `MundoBotsView`, `Theme`, `StyledTable`, `User`, `show_error`, `RequestTesterView`, `settings.py`, `show_success`, `eco_auth.py`, `UserSettingsView`, `RequisicoesView`, `sql_variable_dialogs.py`, `AppLogger`, `TemplateListView`, `AutoCompleteTextEdit`, `config.py`, `get_company_config`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `DashboardView`, `MundoBotsView`, `Theme`, `TemplateListView`, `FirebirdClient`, `RequestFormView`, `settings.py`, `show_success`, `eco_auth.py`, `UserSettingsView`, `LogViewerWindow`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `MundoBotsView` (e.g. with `MainWindow` and `FirebirdClient`) actually correct?**
  _`MundoBotsView` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `User` (e.g. with `login()` and `.check_sent_status()`) actually correct?**
  _`User` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `QLabel` (e.g. with `.__init__()` and `._setup_ui()`) actually correct?**
  _`QLabel` has 59 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Config`, `Write directly to econnect.log (same file as frontend).`, `Config` to the rest of the system?**
  _87 weakly-connected nodes found - possible documentation gaps or missing edges._