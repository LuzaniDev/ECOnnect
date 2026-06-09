from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.template import Template
from ..models.integration import IntegrationConfig
from ..schemas.template import TemplateCreate, TemplateUpdate


class TemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: TemplateCreate, user_id: UUID, eco_empresa: str | None = None) -> Template:
        template = Template(
            name=data.name,
            body=data.body,
            description=data.description,
            parameter_count=data.parameter_count,
            created_by=user_id,
            eco_empresa=eco_empresa,
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def list_all(self, active_only: bool = False, eco_empresa: str | None = None) -> list[Template]:
        query = (
            select(Template)
            .options(selectinload(Template.creator))
            .order_by(Template.created_at.desc())
        )
        if active_only:
            query = query.where(Template.is_active == True)
        if eco_empresa:
            query = query.where(Template.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, template_id: UUID, eco_empresa: str | None = None) -> Template | None:
        query = (
            select(Template)
            .where(Template.id == template_id)
            .options(selectinload(Template.creator))
        )
        if eco_empresa:
            query = query.where(Template.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self, template_id: UUID, data: TemplateUpdate
    ) -> Template | None:
        template = await self.get_by_id(template_id)
        if not template:
            return None

        if data.name is not None:
            template.name = data.name
        if data.body is not None:
            template.body = data.body
        if data.description is not None:
            template.description = data.description
        if data.is_active is not None:
            template.is_active = data.is_active
        if data.parameter_count is not None:
            template.parameter_count = data.parameter_count

        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete(self, template_id: UUID) -> bool:
        template = await self.get_by_id(template_id)
        if not template:
            return False

        result = await self.db.execute(
            select(IntegrationConfig).where(IntegrationConfig.template_id == template_id)
        )
        linked_integrations = result.scalars().all()
        for integ in linked_integrations:
            await self.db.delete(integ)

        await self.db.delete(template)
        await self.db.commit()
        return True
