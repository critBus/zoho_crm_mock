from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import ApiLog, ZohoContact, ZohoDeal, ApiToken
from app.schemas import ApiLogListResponse, ContactSchema, DealSchema
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD
from pathlib import Path

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def check_admin_auth(request: Request):
    """Verifica autenticación básica para admin"""
    username = request.cookies.get("admin_user")
    password = request.cookies.get("admin_pass")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return True
    
    return False


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    """Página de login para admin"""
    return templates.TemplateResponse("admin/login.html", {"request": request})


@router.post("/admin/login")
async def admin_login_post(request: Request, response_class=HTMLResponse):
    """Procesa login de admin"""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        from fastapi.responses import RedirectResponse
        response = RedirectResponse(url="/admin/logs", status_code=303)
        response.set_cookie("admin_user", username, max_age=3600)
        response.set_cookie("admin_pass", password, max_age=3600)
        return response
    
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "error": "Credenciales inválidas"
    })


@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    endpoint: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    status_code: Optional[int] = Query(None),
    success: Optional[bool] = Query(None),
    zoho_contact_id: Optional[str] = Query(None),
    zoho_deal_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Vista de logs de API con filtros"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    # Query base
    query = db.query(ApiLog)
    
    # Aplicar filtros
    if endpoint:
        query = query.filter(ApiLog.endpoint.contains(endpoint))
    if method:
        query = query.filter(ApiLog.method == method)
    if status_code:
        query = query.filter(ApiLog.response_status_code == status_code)
    if success is not None:
        query = query.filter(ApiLog.success == success)
    if zoho_contact_id:
        query = query.filter(ApiLog.zoho_contact_id == zoho_contact_id)
    if zoho_deal_id:
        query = query.filter(ApiLog.zoho_deal_id == zoho_deal_id)
    if date_from:
        from datetime import datetime
        query = query.filter(ApiLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        from datetime import datetime
        query = query.filter(ApiLog.created_at <= datetime.fromisoformat(date_to))
    
    # Ordenar por más reciente
    query = query.order_by(ApiLog.created_at.desc())
    
    # Paginación
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Estadísticas
    stats = {
        "total_requests": db.query(func.count(ApiLog.id)).scalar(),
        "success_count": db.query(func.count(ApiLog.id)).filter(ApiLog.success == True).scalar(),
        "error_count": db.query(func.count(ApiLog.id)).filter(ApiLog.success == False).scalar(),
        "avg_response_time": db.query(func.avg(ApiLog.response_time_ms)).scalar() or 0,
    }
    
    return templates.TemplateResponse("admin/logs.html", {
        "request": request,
        "logs": logs,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "stats": stats,
        "filters": {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "success": success,
            "zoho_contact_id": zoho_contact_id,
            "zoho_deal_id": zoho_deal_id,
            "date_from": date_from,
            "date_to": date_to,
        }
    })


@router.get("/admin/contacts", response_class=HTMLResponse)
async def admin_contacts(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    email: Optional[str] = Query(None),
    zoho_id: Optional[str] = Query(None),
):
    """Vista de contactos de Zoho"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    query = db.query(ZohoContact)
    
    if email:
        query = query.filter(ZohoContact.email.contains(email))
    if zoho_id:
        query = query.filter(ZohoContact.zoho_id.contains(zoho_id))
    
    query = query.order_by(ZohoContact.created_at.desc())
    
    total = query.count()
    contacts = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return templates.TemplateResponse("admin/contacts.html", {
        "request": request,
        "contacts": contacts,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "filters": {
            "email": email,
            "zoho_id": zoho_id,
        }
    })


@router.get("/admin/deals", response_class=HTMLResponse)
async def admin_deals(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    deal_name: Optional[str] = Query(None),
    zoho_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
):
    """Vista de deals de Zoho"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    query = db.query(ZohoDeal)
    
    if deal_name:
        query = query.filter(ZohoDeal.deal_name.contains(deal_name))
    if zoho_id:
        query = query.filter(ZohoDeal.zoho_id.contains(zoho_id))
    if stage:
        query = query.filter(ZohoDeal.stage == stage)
    
    query = query.order_by(ZohoDeal.created_at.desc())
    
    total = query.count()
    deals = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return templates.TemplateResponse("admin/deals.html", {
        "request": request,
        "deals": deals,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "filters": {
            "deal_name": deal_name,
            "zoho_id": zoho_id,
            "stage": stage,
        }
    })


@router.get("/admin/stats", response_class=HTMLResponse)
async def admin_stats(request: Request, db: Session = Depends(get_db)):
    """Vista de estadísticas"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    from sqlalchemy import func
    
    stats = {
        "total_contacts": db.query(func.count(ZohoContact.id)).scalar(),
        "total_deals": db.query(func.count(ZohoDeal.id)).scalar(),
        "total_api_calls": db.query(func.count(ApiLog.id)).scalar(),
        "success_rate": (
            db.query(func.count(ApiLog.id)).filter(ApiLog.success == True).scalar() / 
            max(db.query(func.count(ApiLog.id)).scalar(), 1) * 100
        ),
        "avg_response_time": db.query(func.avg(ApiLog.response_time_ms)).scalar() or 0,
        "endpoints": db.query(
            ApiLog.endpoint, 
            func.count(ApiLog.id).label("count")
        ).group_by(ApiLog.endpoint).all(),
        "methods": db.query(
            ApiLog.method, 
            func.count(ApiLog.id).label("count")
        ).group_by(ApiLog.method).all(),
        "status_codes": db.query(
            ApiLog.response_status_code, 
            func.count(ApiLog.id).label("count")
        ).group_by(ApiLog.response_status_code).all(),
    }
    
    return templates.TemplateResponse("admin/stats.html", {
        "request": request,
        "stats": stats
    })

# ... (código existente) ...

@router.get("/admin/logs/{log_id}", response_class=HTMLResponse)
async def admin_log_detail(
    request: Request,
    log_id: int,
    db: Session = Depends(get_db),
):
    """Vista de detalle de un log específico"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    log = db.query(ApiLog).filter(ApiLog.id == log_id).first()
    
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found")
    
    return templates.TemplateResponse("admin/log_detail.html", {
        "request": request,
        "log": log,
        # "json": json
    })


@router.get("/admin/contacts/{contact_id}", response_class=HTMLResponse)
async def admin_contact_detail(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
):
    """Vista de detalle de un contacto específico"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    contact = db.query(ZohoContact).filter(ZohoContact.id == contact_id).first()
    
    if not contact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Obtener logs relacionados
    related_logs = db.query(ApiLog).filter(
        ApiLog.zoho_contact_id == contact.zoho_id
    ).order_by(ApiLog.created_at.desc()).limit(10).all()
    
    return templates.TemplateResponse("admin/contact_detail.html", {
        "request": request,
        "contact": contact,
        "related_logs": related_logs,
        # "json": json
    })


@router.get("/admin/deals/{deal_id}", response_class=HTMLResponse)
async def admin_deal_detail(
    request: Request,
    deal_id: int,
    db: Session = Depends(get_db),
):
    """Vista de detalle de un deal específico"""
    if not check_admin_auth(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=303)
    
    deal = db.query(ZohoDeal).filter(ZohoDeal.id == deal_id).first()
    
    if not deal:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Obtener logs relacionados
    related_logs = db.query(ApiLog).filter(
        ApiLog.zoho_deal_id == deal.zoho_id
    ).order_by(ApiLog.created_at.desc()).limit(10).all()
    
    return templates.TemplateResponse("admin/deal_detail.html", {
        "request": request,
        "deal": deal,
        "related_logs": related_logs,
        # "json": json
    })