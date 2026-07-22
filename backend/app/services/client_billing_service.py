import json
import httpx
import fdb
from datetime import datetime, date, timedelta
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.client_billing import ClientBillingConfig, BillingTemplate
from ..models.company_config import CompanyConfig
from ..schemas.client_billing import ClientBillingConfigCreate, ClientBillingConfigUpdate

COBRANCA_SQL = """
SELECT Par.Empresa,
       Emp.NomeFantasia,
       Clg.Codigo                                          AS Cliente,
       Clg.Nome,
       Clg.CpfCnpj,
       COALESCE(Clg.Fone, Clg.FoneCelular)                 AS Fone,
       Clg.Endereco,
       Clg.NumeroEndereco,
       Clg.Bairro,
       Clg.Regiao,
       Clg.Cidade,
       COALESCE(Cli.DiasCarenciaJuros, 0)                  AS DiasCarenciaJuros,
       Doc.IdDocumento,
       Par.Documento||'/'||Par.Parcela                     AS Documento,
       Tpd.Abreviatura,
       0                                                    AS Atrazo,
       Doc.Emissao,
       Par.Vencimento,
       Par.Valor,
       (Par.Valor - Par.ValorPendente)                     AS CapitalRecebido,
       Par.ValorPendente,
       COALESCE(Pmt.Multa, 0)                              AS Multa,
       COALESCE(NULLIF(Cli.JurosAtraso, 0), Pmt.Juros, 0)  AS Juros,
       COALESCE(Pmt.TipoJuro, '')                           AS TipoJuro,
       Par.IDTRECPARCELA,
       Par.PORTADOR,
       Par.PARCELA                                          AS Parcela,
       ''                                                   AS NossoNumero,
       ''                                                   AS NumeroBoleto,
       Par.UltimoRecebimento,
       Par.Situacao
  FROM TRecParcela Par
 INNER JOIN TRecDocumento Doc
    ON Doc.Empresa   = Par.Empresa
   AND Doc.Cliente   = Par.Cliente
   AND Doc.Tipo      = Par.Tipo
   AND Doc.Documento = Par.Documento
 INNER JOIN TRecTipoDocumento Tpd
    ON Tpd.Codigo    = Par.Tipo
   AND COALESCE(Tpd.Cartao, 'N') = 'N'
 INNER JOIN TRecCliente Cli
    ON Cli.Empresa   = Par.Empresa
   AND Cli.Codigo    = Par.Cliente
 INNER JOIN TRecClienteGeral Clg
    ON Clg.Codigo    = Cli.Codigo
 INNER JOIN TGerEmpresa Emp
    ON Emp.Codigo    = Par.Empresa
  LEFT JOIN TRecParametro Pmt
    ON Pmt.Empresa   = Emp.Codigo
  WHERE Par.Empresa          = ?
    AND Par.ValorPendente > 0
    AND Par.Situacao <> 'A'
    AND Par.IdRenegociacao  IS NULL
    AND Clg.Codigo = ?
  ORDER BY Par.Vencimento ASC
"""

SIMPLE_COUNT_SQL = """
SELECT COUNT(*) FROM TRecParcela
 WHERE Empresa = ? AND Cliente = ?
   AND Situacao <> 'A' AND IdRenegociacao IS NULL
   AND ValorPendente > 0
"""


def _get_fb_connection(empresa: str, configs: list[CompanyConfig]):
    for c in configs:
        if c.company_code == empresa:
            conn = fdb.connect(
                dsn=c.fb_database.replace("/", "\\"),
                user=c.fb_user,
                password=c.fb_password,
                charset="WIN1252",
            )
            return conn
    raise ValueError(f"Firebird config not found for empresa {empresa}")


def _format_date(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d")
    d = str(raw)[:10]
    return d


def _format_valor(raw) -> str:
    if raw is None:
        return "0"
    try:
        return f"{float(raw):.2f}"
    except (ValueError, TypeError):
        return str(raw)


PLACEHOLDER_MAP = {
    "phone": 5,
    "nome": 3,
    "nome_cliente": 3,
    "cliente": 2,
    "codigo_cliente": 2,
    "cpf_cnpj": 4,
    "empresa": 0,
    "nome_fantasia": 1,
    "valor_cobranca": 20,
    "valor_total": 18,
    "capital_recebido": 19,
    "status_cobranca": 30,
    "vencimento": 17,
    "data_vencimento": 17,
    "emissao": 16,
    "documento": 13,
    "id_documento": 12,
    "abreviatura": 14,
    "parcela": 26,
    "portador": 25,
    "endereco": 6,
    "numero": 7,
    "bairro": 8,
    "cidade": 10,
    "regiao": 9,
    "atraso": 15,
    "dias_atraso": 15,
    "dias_carencia": 11,
    "juros_taxa": 22,
    "multa_taxa": 21,
    "tipo_juro": 23,
    "nosso_numero": 27,
    "numero_boleto": 28,
    "num_boleto": 28,
    "first_name": 3,
    "celular": 5,
}


def _substitute_placeholders(template: str, row: tuple) -> str:
    result = template
    for placeholder, col_idx in PLACEHOLDER_MAP.items():
        if col_idx < len(row) and row[col_idx] is not None:
            val = row[col_idx]
            if isinstance(val, (datetime, date)):
                val = _format_date(val)
            else:
                val = str(val)
            result = result.replace("{{" + placeholder + "}}", val)
            result = result.replace("{" + placeholder + "}", val)
    return result


class ClientBillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_client_to_firebird(self, client_code: str, client_name: str, client_phone: str, eco_empresa: str):
        try:
            result = await self.db.execute(
                select(CompanyConfig).where(CompanyConfig.company_code == eco_empresa)
            )
            company = result.scalar_one_or_none()
            if not company:
                return
            fb_conn = fdb.connect(
                dsn=company.fb_database.replace("/", "\\"),
                user=company.fb_user,
                password=company.fb_password,
                charset="WIN1252",
            )
            try:
                cursor = fb_conn.cursor()
                cursor.execute(
                    "UPDATE TRecClienteGeral SET Nome = ?, Fone = ? WHERE Codigo = ?",
                    (client_name, client_phone, client_code)
                )
                fb_conn.commit()
            except Exception:
                fb_conn.rollback()
            finally:
                fb_conn.close()
        except Exception as e:
            print(f"[sync_client_to_firebird] Erro ao atualizar {client_code}: {e}")

    async def _resolve_template_data(self, config: ClientBillingConfig) -> dict:
        if config.billing_template_id:
            result = await self.db.execute(
                select(BillingTemplate).where(BillingTemplate.id == config.billing_template_id)
            )
            tpl = result.scalar_one_or_none()
            if tpl:
                return {
                    "url": tpl.url,
                    "method": tpl.method,
                    "headers": tpl.headers,
                    "body": tpl.body,
                    "tag": tpl.tag,
                    "api_token": tpl.api_token,
                    "flow_id": tpl.flow_id,
                    "offset_days": tpl.offset_days,
                    "send_time": tpl.send_time,
                }
        name = config.template_name or "sem nome"
        raise ValueError(f"Config '{name}' (cliente {config.client_name}) não possui billing_template_id. Edite o grupo, selecione o template correto e salve.")

    async def create_config(
        self, data: ClientBillingConfigCreate, user_id: UUID, eco_empresa: str
    ) -> ClientBillingConfig:
        config = ClientBillingConfig(
            client_code=data.client_code,
            client_name=data.client_name,
            client_phone=data.client_phone,
            eco_empresa=eco_empresa,
            billing_template_id=data.billing_template_id,
            template_name=data.template_name,
            template_method=data.template_method,
            template_url=data.template_url,
            template_headers=data.template_headers,
            template_body=data.template_body,
            template_tag=data.template_tag,
            api_token=data.api_token,
            flow_id=data.flow_id,
            offset_days=data.offset_days,
            send_time=data.send_time,
            created_by=user_id,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def list_configs(
        self, eco_empresa: str | None = None, is_active: bool | None = None
    ) -> list[ClientBillingConfig]:
        query = select(ClientBillingConfig).options(selectinload(ClientBillingConfig.creator))
        conditions = []
        if eco_empresa:
            conditions.append(ClientBillingConfig.eco_empresa == eco_empresa)
        if is_active is not None:
            conditions.append(ClientBillingConfig.is_active == is_active)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(ClientBillingConfig.client_name)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_config(self, config_id: UUID) -> ClientBillingConfig | None:
        query = (
            select(ClientBillingConfig)
            .where(ClientBillingConfig.id == config_id)
            .options(selectinload(ClientBillingConfig.creator))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_config(
        self, config_id: UUID, data: ClientBillingConfigUpdate
    ) -> ClientBillingConfig | None:
        config = await self.get_config(config_id)
        if not config:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)
        config.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def delete_config(self, config_id: UUID) -> bool:
        config = await self.get_config(config_id)
        if not config:
            return False
        await self.db.delete(config)
        await self.db.commit()
        return True

    async def check_due_configs(self):
        today = date.today()
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        query = select(ClientBillingConfig).where(
            and_(
                ClientBillingConfig.is_active == True,
            )
        )
        result = await self.db.execute(query)
        configs = result.scalars().all()

        if not configs:
            return

        empresa_configs_result = await self.db.execute(
            select(CompanyConfig)
        )
        empresa_configs = empresa_configs_result.scalars().all()

        for config in configs:
            try:
                await self._process_config(config, empresa_configs, today, current_time)
            except Exception as e:
                import traceback
                traceback.print_exc()

        await self.db.commit()

    async def check_single_config(self, config: ClientBillingConfig):
        today = date.today()
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")
        empresa_configs_result = await self.db.execute(
            select(CompanyConfig)
        )
        empresa_configs = empresa_configs_result.scalars().all()
        try:
            await self._process_config(config, empresa_configs, today, current_time)
        except Exception as e:
            import traceback
            traceback.print_exc()
        await self.db.commit()

    async def send_test(self, config: ClientBillingConfig):
        import httpx
        tpl = await self._resolve_template_data(config)
        body_template = tpl["body"] or ""

        empresa = config.eco_empresa or "01"
        fb_row = None
        try:
            empresa_configs_result = await self.db.execute(
                select(CompanyConfig)
            )
            empresa_configs = empresa_configs_result.scalars().all()
            fb_conn = _get_fb_connection(empresa, empresa_configs)
            try:
                cursor = fb_conn.cursor()
                cursor.execute(SIMPLE_COUNT_SQL, (empresa, config.client_code))
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute(COBRANCA_SQL, (empresa, config.client_code))
                    rows = cursor.fetchall()
                    for row in rows:
                        if row[17] is not None:
                            fb_row = row
                            break
                fb_conn.commit()
            except Exception:
                fb_conn.rollback()
            finally:
                fb_conn.close()
        except Exception:
            pass

        if fb_row:
            body_template = _substitute_placeholders(body_template, fb_row)
        else:
            test_row = (
                empresa, "", config.client_code, config.client_name, "",
                config.client_phone, "", "", "", "", "",
                "0", "", "", "", "0", "", "", "0", "0", "0",
                "0", "0", "", "", "", "", "", "", "", "",
            )
            body_template = _substitute_placeholders(body_template, test_row)

        try:
            payload = json.loads(body_template)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"JSON inválido no template body de '{config.client_name}': {e}")

        headers = {"Content-Type": "application/json"}
        if tpl["headers"]:
            for h in tpl["headers"]:
                if isinstance(h, (list, tuple)) and len(h) >= 2 and h[0]:
                    headers[str(h[0])] = str(h[1])
        headers["X-ACCESS-TOKEN"] = tpl["api_token"]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                tpl["url"],
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()


    async def _process_config(
        self,
        config: ClientBillingConfig,
        empresa_configs: list[CompanyConfig],
        today: date,
        current_time: str,
    ):
        if config.next_check_date and config.next_check_date > today:
            return

        if config.send_time and current_time < config.send_time:
            nc = today + timedelta(days=1)
            config.next_check_date = nc
            return

        empresa = config.eco_empresa or "01"
        fb_conn = _get_fb_connection(empresa, empresa_configs)

        try:
            cursor = fb_conn.cursor()
            cursor.execute(SIMPLE_COUNT_SQL, (empresa, config.client_code))
            count = cursor.fetchone()[0]
            if count == 0:
                config.is_active = False
                config.next_check_date = None
                fb_conn.commit()
                fb_conn.close()
                return
            cursor.execute(COBRANCA_SQL, (empresa, config.client_code))
            rows = cursor.fetchall()
            fb_conn.commit()
        except Exception:
            fb_conn.rollback()
            raise
        finally:
            fb_conn.close()

        target_date = None
        target_row = None
        for row in rows:
            venc = row[17]
            if venc is None:
                continue
            if isinstance(venc, datetime):
                venc_date = venc.date()
            elif isinstance(venc, date):
                venc_date = venc
            else:
                continue

            if config.last_pendencia_vencimento and venc_date <= config.last_pendencia_vencimento:
                continue

            target_date = venc_date
            target_row = row
            break

        if target_date is None:
            config.last_pendencia_vencimento = None
            config.next_check_date = None
            return

        send_date = target_date + timedelta(days=config.offset_days)

        if send_date != today:
            config.next_check_date = send_date
            return

        await self._send_message(config, target_row)
        config.last_pendencia_vencimento = target_date
        config.last_sent_at = datetime.utcnow()

        next_pendencia_target = self._find_next_pendencia(rows, target_date)
        if next_pendencia_target:
            next_send = next_pendencia_target + timedelta(days=config.offset_days)
            config.next_check_date = next_send
        else:
            config.is_active = False
            config.next_check_date = None

    def _find_next_pendencia(self, rows: list[tuple], last_venc: date) -> date | None:
        for row in rows:
            venc = row[17]
            if venc is None:
                continue
            if isinstance(venc, datetime):
                venc_date = venc.date()
            elif isinstance(venc, date):
                venc_date = venc
            else:
                continue
            if venc_date > last_venc:
                return venc_date
        return None

    async def _send_message(self, config: ClientBillingConfig, row: tuple):
        tpl = await self._resolve_template_data(config)
        body_template = tpl["body"] or ""
        processed_body = _substitute_placeholders(body_template, row)

        try:
            payload = json.loads(processed_body)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"JSON inválido no template body de '{config.client_name}': {e}")

        headers = {"Content-Type": "application/json"}
        if tpl["headers"]:
            for h in tpl["headers"]:
                if isinstance(h, (list, tuple)) and len(h) >= 2 and h[0]:
                    headers[str(h[0])] = str(h[1])
        headers["X-ACCESS-TOKEN"] = tpl["api_token"]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                tpl["url"],
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
