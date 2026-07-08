# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

BUILD_MODE = os.environ.get("BUILD_MODE", "onefile")

datas = [('backend/.env.example', '.'), ('frontend/assets', 'frontend/assets')]
binaries = []
hiddenimports = ['frontend.app.views.mundo_bots', 'frontend.app.views.dashboard', 'frontend.app.views.settings', 'frontend.app.views.login', 'frontend.app.views.requisicoes', 'frontend.app.views.request_form', 'frontend.app.views.request_list', 'frontend.app.views.request_tester', 'frontend.app.views.template_list', 'frontend.app.views.template_form', 'frontend.app.views.meta_view', 'frontend.app.views.meta_credentials', 'frontend.app.views.whatsweb_view', 'frontend.app.views.ecochat_view', 'frontend.app.views.admin_users', 'frontend.app.views.admin_tabs', 'frontend.app.widgets.sidebar', 'frontend.app.widgets.dialogs', 'frontend.app.widgets.log_viewer', 'frontend.app.widgets.loading_overlay', 'frontend.app.widgets.history_dialog', 'frontend.app.widgets.schedule_dialog', 'frontend.app.widgets.worker', 'frontend.app.widgets.table', 'frontend.app.widgets.autocomplete_textedit', 'frontend.app.widgets.sql_variable_dialogs', 'frontend.app.services.boleto_pdf', 'frontend.app.services.boleto_watcher', 'frontend.app.services.calculadora', 'frontend.app.services.barcode', 'frontend.app.api.auth_api', 'frontend.app.api.request_api', 'frontend.app.api.template_api', 'frontend.app.api.user_api', 'frontend.app.api.meta_api', 'frontend.app.api.audit_api', 'frontend.app.api.sql_variable_api', 'frontend.app.api.company_config_api', 'frontend.app.api.dashboard_api', 'frontend.app.api.integration_api', 'frontend.app.api.client', 'frontend.app.core.logger', 'frontend.app.core.eco_auth', 'frontend.app.core.firebird_client', 'frontend.app.core.theme', 'frontend.app.config', 'frontend.app.app', 'frontend.main',
    'asyncpg', 'asyncpg.protocol', 'fdb',
    'passlib.handlers.pbkdf2']
tmp_ret = collect_all('frontend')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('backend')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['frontend\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy.typing'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ECOnnect',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if BUILD_MODE == "onedir":
    COLLECT(exe, a.binaries, a.datas,
            strip=False,
            upx=False,
            upx_exclude=[],
            name='ECOnnect')
