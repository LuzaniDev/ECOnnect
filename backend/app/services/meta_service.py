import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.meta_credentials import MetaCredentials
from ..models.meta_message import MetaMessage
from ..models.template import Template

META_GRAPH_URL = "https://graph.facebook.com/v22.0"


async def get_credentials(db: AsyncSession, eco_empresa: str) -> MetaCredentials | None:
    result = await db.execute(
        select(MetaCredentials).where(MetaCredentials.eco_empresa == eco_empresa)
    )
    return result.scalar_one_or_none()


async def save_credentials(
    db: AsyncSession, eco_empresa: str, data: dict
) -> MetaCredentials:
    creds = await get_credentials(db, eco_empresa)
    if creds:
        for field in ("waba_id", "phone_number_id", "access_token"):
            if data.get(field) is not None:
                setattr(creds, field, data[field])
        creds.is_verified = False
    else:
        creds = MetaCredentials(
            eco_empresa=eco_empresa,
            waba_id=data["waba_id"],
            phone_number_id=data["phone_number_id"],
            access_token=data["access_token"],
        )
        db.add(creds)
    await db.commit()
    await db.refresh(creds)
    return creds


async def verify_credentials(
    waba_id: str, phone_number_id: str, access_token: str
) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                f"{META_GRAPH_URL}/{waba_id}",
                params={"access_token": access_token},
            )
            if resp.status_code != 200:
                return False, f"Erro Meta: {resp.json().get('error', {}).get('message', str(resp.text))}"

            resp2 = await client.get(
                f"{META_GRAPH_URL}/{phone_number_id}",
                params={"access_token": access_token},
            )
            if resp2.status_code != 200:
                return False, f"Erro ao validar Phone Number ID: {resp2.json().get('error', {}).get('message', str(resp2.text))}"

            return True, "Conexão estabelecida com sucesso!"
        except httpx.RequestError as e:
            return False, f"Erro de conexão: {str(e)}"


async def create_meta_template(
    creds: MetaCredentials, template: Template
) -> tuple[str, str, str]:
    components = [
        {
            "type": "BODY",
            "text": template.body,
        }
    ]
    body = {
        "name": template.name,
        "language": "pt_BR",
        "category": "UTILITY",
        "components": components,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{META_GRAPH_URL}/{creds.waba_id}/message_templates",
                params={"access_token": creds.access_token},
                json=body,
            )
            data = resp.json()
            if resp.status_code == 200 or resp.status_code == 201:
                meta_id = data.get("id", "")
                status = data.get("status", "PENDING")
                return meta_id, status, "Template criado na Meta com sucesso!"
            else:
                err = data.get("error", {}).get("message", str(resp.text))
                return "", "REJECTED", f"Erro Meta: {err}"
        except httpx.RequestError as e:
            return "", "REJECTED", f"Erro de conexão: {str(e)}"


async def check_template_status(
    creds: MetaCredentials, meta_template_id: str
) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                f"{META_GRAPH_URL}/{creds.waba_id}/message_templates",
                params={
                    "access_token": creds.access_token,
                    "name": meta_template_id,
                },
            )
            data = resp.json()
            if resp.status_code == 200:
                templates = data.get("data", [])
                if templates:
                    status = templates[0].get("status", "UNKNOWN")
                    return status, ""
            return "UNKNOWN", "Template não encontrado na Meta"
        except httpx.RequestError as e:
            return "UNKNOWN", f"Erro de conexão: {str(e)}"


async def send_template_message(
    creds: MetaCredentials,
    template: Template,
    to_phone: str,
    parameter_values: dict[str, str],
) -> tuple[bool, str, str]:
    parameters = []
    for i in range(template.parameter_count):
        key = str(i + 1)
        parameters.append(
            {
                "type": "text",
                "text": parameter_values.get(key, ""),
            }
        )

    body = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template.name,
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "body",
                    "parameters": parameters,
                }
            ],
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{META_GRAPH_URL}/{creds.phone_number_id}/messages",
                params={"access_token": creds.access_token},
                json=body,
            )
            data = resp.json()
            if resp.status_code == 200 or resp.status_code == 201:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return True, msg_id, "Mensagem enviada com sucesso!"
            else:
                err = data.get("error", {}).get("message", str(resp.text))
                return False, "", f"Erro Meta: {err}"
        except httpx.RequestError as e:
            return False, "", f"Erro de conexão: {str(e)}"


async def log_message(db: AsyncSession, eco_empresa: str, data: dict) -> MetaMessage:
    msg = MetaMessage(
        eco_empresa=eco_empresa,
        from_phone=data.get("from_phone", ""),
        to_phone=data.get("to_phone", ""),
        direction=data.get("direction", "outgoing"),
        template_name=data.get("template_name"),
        body=data.get("body"),
        meta_message_id=data.get("meta_message_id"),
        status=data.get("status", "sent"),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_messages(
    db: AsyncSession, eco_empresa: str, phone: str | None = None
) -> list[MetaMessage]:
    query = (
        select(MetaMessage)
        .where(MetaMessage.eco_empresa == eco_empresa)
        .order_by(MetaMessage.created_at.desc())
    )
    if phone:
        query = query.where(
            (MetaMessage.from_phone == phone) | (MetaMessage.to_phone == phone)
        )
    result = await db.execute(query)
    return list(result.scalars().all())


async def process_webhook_entry(entry: dict, db: AsyncSession):
    changes = entry.get("changes", [])
    for change in changes:
        value = change.get("value", {})
        messages = value.get("messages", [])
        metadata = value.get("metadata", {})
        for msg in messages:
            from_phone = msg.get("from", "")
            msg_id = msg.get("id", "")
            msg_type = msg.get("type", "text")
            body = ""
            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                body = str(msg.get("interactive", {}))

            eco_empresa = metadata.get("phone_number_id", "")

            await log_message(
                db,
                eco_empresa=eco_empresa,
                data={
                    "from_phone": from_phone,
                    "to_phone": metadata.get("display_phone_number", ""),
                    "direction": "incoming",
                    "body": body,
                    "meta_message_id": msg_id,
                    "status": "received",
                },
            )

        statuses = value.get("statuses", [])
        for status in statuses:
            status_name = status.get("status", "")
            msg_id = status.get("id", "")
            result = await db.execute(
                select(MetaMessage).where(MetaMessage.meta_message_id == msg_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.status = status_name
                await db.commit()
