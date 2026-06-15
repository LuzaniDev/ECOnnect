from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.integration import IntegrationConfig
from ..models.request import Request
from ..models.template import Template
from ..models.audit_log import AuditLog

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _company_filter(eco: str | None):
    if not eco:
        return []
    return [User.eco_empresa == eco]


@router.get("/summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    eco = current_user.eco_empresa
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    async def fetch_one(query):
        return (await db.execute(query)).scalar() or 0

    cf = _company_filter(eco)

    # ── Requests ──────────────────────────────────────
    def req_query(*where):
        q = select(func.count(Request.id)).join(Request.creator)
        if cf:
            q = q.where(*cf)
        if where:
            q = q.where(*where)
        return q

    total_requests = await fetch_one(req_query())
    pending = await fetch_one(req_query(Request.status == "pending"))
    sent = await fetch_one(req_query(Request.status == "sent"))
    cancelled = await fetch_one(req_query(Request.status == "cancelled"))
    sent_today = await fetch_one(req_query(
        Request.status == "sent",
        Request.created_at >= today_start,
    ))
    pending_today = await fetch_one(req_query(
        Request.status == "pending",
        Request.created_at >= today_start,
    ))

    # requests over time (last 14 days)
    req_time_q = select(
        func.date(Request.created_at),
        func.count(Request.id),
    ).join(Request.creator).where(
        Request.created_at >= two_weeks_ago,
    )
    if cf:
        req_time_q = req_time_q.where(*cf)
    req_time_q = req_time_q.group_by(
        func.date(Request.created_at)
    ).order_by(func.date(Request.created_at))
    req_time_result = await db.execute(req_time_q)
    requests_over_time = [
        {"date": str(d), "count": c} for d, c in req_time_result.all()
    ]

    # daily breakdown by status (last 14 days)
    req_by_status_day_q = select(
        func.date(Request.created_at),
        func.count(case((Request.status == "sent", 1))),
        func.count(case((Request.status == "pending", 1))),
        func.count(case((Request.status == "cancelled", 1))),
    ).join(Request.creator).where(
        Request.created_at >= two_weeks_ago,
    )
    if cf:
        req_by_status_day_q = req_by_status_day_q.where(*cf)
    req_by_status_day_q = req_by_status_day_q.group_by(
        func.date(Request.created_at)
    ).order_by(func.date(Request.created_at))
    req_by_status_result = await db.execute(req_by_status_day_q)
    requests_by_status_day = [
        {"date": str(d), "sent": s, "pending": p, "cancelled": c}
        for d, s, p, c in req_by_status_result.all()
    ]

    # requests by template (top 10)
    req_by_template_q = select(
        Template.name,
        func.count(Request.id),
    ).join(Request, Request.template_id == Template.id).join(Request.creator)
    if cf:
        req_by_template_q = req_by_template_q.where(*cf)
    req_by_template_q = req_by_template_q.group_by(Template.name).order_by(
        func.count(Request.id).desc()
    ).limit(10)
    req_by_template_result = await db.execute(req_by_template_q)
    requests_by_template = [
        {"name": n, "count": c} for n, c in req_by_template_result.all()
    ]

    # requests by tag
    req_by_tag_q = select(
        func.coalesce(Request.tag, "sem tag"),
        func.count(Request.id),
    ).join(Request.creator)
    if cf:
        req_by_tag_q = req_by_tag_q.where(*cf)
    req_by_tag_q = req_by_tag_q.group_by(Request.tag).order_by(
        func.count(Request.id).desc()
    )
    req_by_tag_result = await db.execute(req_by_tag_q)
    requests_by_tag = [
        {"tag": t, "count": c} for t, c in req_by_tag_result.all()
    ]

    # requests by user (top 5)
    req_by_user_q = select(
        Request.created_by,
        User.username,
        func.count(Request.id),
    ).join(Request.creator)
    if cf:
        req_by_user_q = req_by_user_q.where(*cf)
    req_by_user_q = req_by_user_q.group_by(
        Request.created_by, User.username
    ).order_by(func.count(Request.id).desc()).limit(5)
    req_by_user_result = await db.execute(req_by_user_q)
    requests_by_user = [
        {"user_id": str(uid), "username": un, "count": c}
        for uid, un, c in req_by_user_result.all()
    ]

    # weekly comparison
    this_week_start = now - timedelta(days=now.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    this_week = await fetch_one(
        req_query(Request.created_at >= this_week_start)
    )
    last_week = await fetch_one(
        req_query(
            Request.created_at >= last_week_start,
            Request.created_at < this_week_start,
        )
    )
    # Weekly breakdown by status
    def _week_counts(start, end=None):
        conditions = [Request.created_at >= start]
        if end:
            conditions.append(Request.created_at < end)
        return {
            s: fetch_one(req_query(Request.status == s, *conditions))
            for s in ("sent", "pending", "cancelled")
        }

    tw_sent = await fetch_one(req_query(
        Request.status == "sent",
        Request.created_at >= this_week_start,
    ))
    tw_pending = await fetch_one(req_query(
        Request.status == "pending",
        Request.created_at >= this_week_start,
    ))
    tw_cancelled = await fetch_one(req_query(
        Request.status == "cancelled",
        Request.created_at >= this_week_start,
    ))
    lw_sent = await fetch_one(req_query(
        Request.status == "sent",
        Request.created_at >= last_week_start,
        Request.created_at < this_week_start,
    ))
    lw_pending = await fetch_one(req_query(
        Request.status == "pending",
        Request.created_at >= last_week_start,
        Request.created_at < this_week_start,
    ))
    lw_cancelled = await fetch_one(req_query(
        Request.status == "cancelled",
        Request.created_at >= last_week_start,
        Request.created_at < this_week_start,
    ))

    weekly_comparison = [
        {"week": "Semana Passada", "sent": lw_sent, "pending": lw_pending, "cancelled": lw_cancelled, "total": last_week},
        {"week": "Esta Semana", "sent": tw_sent, "pending": tw_pending, "cancelled": tw_cancelled, "total": this_week},
    ]

    # ── Integrations ──────────────────────────────────
    integ_where = [IntegrationConfig.eco_empresa == eco] if eco else []

    total_integrations = await fetch_one(
        select(func.count(IntegrationConfig.id)).where(*integ_where)
    )
    active_integrations = await fetch_one(
        select(func.count(IntegrationConfig.id)).where(
            IntegrationConfig.is_active == True, *integ_where
        )
    )
    cobranca_integrations = await fetch_one(
        select(func.count(IntegrationConfig.id)).where(
            IntegrationConfig.type == "cobranca", *integ_where
        )
    )

    # Integration type distribution
    integ_type_q = select(
        IntegrationConfig.type, func.count(IntegrationConfig.id)
    ).where(*integ_where).group_by(IntegrationConfig.type)
    integ_type_result = await db.execute(integ_type_q)
    integration_types = [
        {"type": t or "outro", "count": c}
        for t, c in integ_type_result.all()
    ]

    # ── Users & Templates ─────────────────────────────
    total_users = await fetch_one(
        select(func.count(User.id)).where(User.eco_empresa == eco)
        if eco else select(func.count(User.id))
    )
    total_templates = await fetch_one(
        select(func.count(Template.id)).where(Template.eco_empresa == eco)
        if eco else select(func.count(Template.id))
    )

    # ── Recent Activity (audit log) ───────────────────
    audit_q = select(
        AuditLog.username, AuditLog.action,
        AuditLog.entity_type, AuditLog.created_at,
    ).join(AuditLog.user)
    if cf:
        audit_q = audit_q.where(*cf)
    audit_q = audit_q.order_by(AuditLog.created_at.desc()).limit(10)
    audit_result = await db.execute(audit_q)
    recent_activity = [
        {"username": u, "action": a, "entity": e, "created_at": str(c)}
        for u, a, e, c in audit_result.all()
    ]

    # ── Upcoming schedules ────────────────────────────
    upcoming_q = select(
        IntegrationConfig.name, IntegrationConfig.next_run_at,
    ).where(
        IntegrationConfig.schedule_enabled == True,
        IntegrationConfig.is_active == True,
        IntegrationConfig.next_run_at >= now,
        *integ_where,
    ).order_by(IntegrationConfig.next_run_at.asc()).limit(5)
    upcoming_result = await db.execute(upcoming_q)
    upcoming_schedules = [
        {"name": n, "next_run_at": str(r)}
        for n, r in upcoming_result.all()
    ]

    # ── Recent runs ───────────────────────────────────
    runs_q = select(
        IntegrationConfig.name, IntegrationConfig.last_run_at,
    ).where(
        IntegrationConfig.last_run_at.isnot(None),
        *integ_where,
    ).order_by(IntegrationConfig.last_run_at.desc()).limit(5)
    runs_result = await db.execute(runs_q)
    recent_runs = [
        {"name": n, "last_run_at": str(r)}
        for n, r in runs_result.all()
    ]

    return {
        "requests": {
            "total": total_requests,
            "pending": pending,
            "sent": sent,
            "cancelled": cancelled,
            "sent_today": sent_today,
            "pending_today": pending_today,
        },
        "integrations": {
            "total": total_integrations,
            "active": active_integrations,
            "cobranca": cobranca_integrations,
        },
        "users": total_users,
        "templates": total_templates,
        "requests_over_time": requests_over_time,
        "requests_by_status_day": requests_by_status_day,
        "requests_by_template": requests_by_template,
        "requests_by_tag": requests_by_tag,
        "requests_by_user": requests_by_user,
        "weekly_comparison": weekly_comparison,
        "integration_types": integration_types,
        "recent_activity": recent_activity,
        "upcoming_schedules": upcoming_schedules,
        "recent_runs": recent_runs,
    }
