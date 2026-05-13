import time
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ApiLog
from app.services.zoho_mock import ZohoMockService
from app.services.logger import ApiLogger
from app.config import ZOHO_MOCK_CONFIG
from app.models import ZohoLead
from app.services.zoho_mock import ZohoMockService
import traceback
from app.services.error_simulation import ErrorSimulationService
from requests.exceptions import ConnectTimeout, SSLError, Timeout, ConnectionError

router = APIRouter()

async def log_api_call(
    db: Session,
    request: Request,
    endpoint: str,
    method: str,
    body: Optional[dict] = None,
    response_status: int = 200,
    response_body: Optional[dict] = None,
    response_time_ms: int = 0,
    zoho_contact_id: Optional[str] = None,
    zoho_deal_id: Optional[str] = None,
    zoho_lead_id:Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """Registra llamada API en DB y archivos TXT"""
    request_id = ApiLogger.generate_request_id()
    headers = dict(request.headers)
    
    # Log request
    await ApiLogger.log_request(
        request_id=request_id,
        endpoint=endpoint,
        method=method,
        url=str(request.url),
        headers=headers,
        body=body,
        query_params=dict(request.query_params)
    )
    
    # Log response
    await ApiLogger.log_response(
        request_id=request_id,
        endpoint=endpoint,
        status_code=response_status,
        headers={"Content-Type": "application/json"},
        body=response_body or {},
        response_time_ms=response_time_ms,
        zoho_contact_id=zoho_contact_id,
        zoho_deal_id=zoho_deal_id,
        zoho_lead_id=zoho_lead_id,
        success=success,
        error_message=error_message
    )
    
    # Guardar en DB
    api_log = ApiLog(
        request_id=request_id,
        endpoint=endpoint,
        method=method,
        url=str(request.url),
        headers=headers,
        body=body,
        query_params=dict(request.query_params),
        response_status_code=response_status,
        response_headers={"Content-Type": "application/json"},
        response_body=response_body,
        response_time_ms=response_time_ms,
        zoho_contact_id=zoho_contact_id,
        zoho_deal_id=zoho_deal_id,
        zoho_lead_id=zoho_lead_id,
        success=success,
        error_message=error_message
    )
    db.add(api_log)
    db.commit()
    
    return request_id

async def check_and_raise_simulated_error(
    db: Session,
    request: Request,
    endpoint: str
):
    """Verifica si debe levantar un error simulado"""
    simulation = ErrorSimulationService.get_active_simulation(db, endpoint)
    
    if simulation and ErrorSimulationService.should_raise_error(simulation):
        # Incrementar contador
        ErrorSimulationService.increment_error_count(db, simulation)
        
        # Extraer URL de la petición
        url = str(request.url)
        
        # Loguear el error simulado
        start_time = time.time()
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint=endpoint,
            method=request.method,
            response_status=500,
            response_body={"error": f"Simulated {simulation.error_type}"},
            response_time_ms=response_time_ms,
            success=False,
            error_message=f"Simulated {simulation.error_type} (count: {simulation.current_error_count}/{simulation.consecutive_errors})"
        )
        
        # Levantar el error simulado
        ErrorSimulationService.raise_simulated_error(simulation.error_type, url)
    
    return simulation

@router.post("/oauth/v2/token")
async def login(request: Request, db: Session = Depends(get_db)):
    """Simula login de Zoho para obtener access token"""
    start_time = time.time()
        # VERIFICAR ERROR SIMULADO
    await check_and_raise_simulated_error(db, request, "/token")
    
    try:
        token = ZohoMockService.get_or_create_token(db)
        
        response_body = {
            "access_token": token.access_token,
            "expires_in": token.expires_in,
            "token_type": token.token_type
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/token",
            method="POST",
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms
        )
        
        return response_body
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_call(
            db=db,
            request=request,
            endpoint="/token",
            method="POST",
            response_status=500,
            response_body={"error": str(e)},
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crm/v2/Contacts")
async def create_contact(request: Request, db: Session = Depends(get_db)):
    """
    Crea un contacto en Zoho CRM
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
        # VERIFICAR ERROR SIMULADO
    await check_and_raise_simulated_error(db, request, "/Contacts")
    
    try:
        body = await request.json()
        contact_data = body.get("data", [{}])[0]
        
        contact, is_new, code, message = ZohoMockService.create_contact(db, contact_data)
        
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                {
                    "code": code,
                    "status": "success" if code == "SUCCESS" else "error",
                    "details": ZohoMockService._build_details_response(
                        zoho_id=contact.zoho_id,
                        created_at=contact.created_at,
                        modified_at=contact.updated_at,
                        include_creator=True
                    ),
                    "message": message
                }
            ]
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="POST",
            body=body,
            response_status=201 if is_new else 200,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_contact_id=contact.zoho_id
        )
        
        return response_body
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="POST",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/crm/v2/Contacts")
async def update_contact(request: Request, db: Session = Depends(get_db)):
    """
    Actualiza un contacto en Zoho CRM
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
        # VERIFICAR ERROR SIMULADO
    await check_and_raise_simulated_error(db, request, "/Contacts")
    
    try:
        body = await request.json()
        contact_data = body.get("data", [{}])[0]
        zoho_id = contact_data.get("id")
        
        if not zoho_id:
            error_response = {
                "data": [
                    {
                        "code": "REQUIRED_FIELD_MISSING",
                        "status": "error",
                        "message": "Contact ID is required"
                    }
                ]
            }
            response_time_ms = int((time.time() - start_time) * 1000)
            await log_api_call(
                db=db,
                request=request,
                endpoint="/Contacts",
                method="PUT",
                body=body,
                response_status=400,
                response_body=error_response,
                response_time_ms=response_time_ms,
                success=False,
                error_message="Contact ID is required"
            )
            return error_response
        
        contact, code, message = ZohoMockService.update_contact(db, zoho_id, contact_data)
        
        if not contact:
            response_body = {
                "data": [
                    {
                        "code": code,
                        "status": "error",
                        "message": message
                    }
                ]
            }
            status_code = 404
        else:
            response_body = {
                "data": [
                    {
                        "code": code,
                        "status": "success",
                        "details": ZohoMockService._build_details_response(
                            zoho_id=contact.zoho_id,
                            created_at=contact.created_at,
                            modified_at=contact.updated_at,
                            include_creator=True
                        ),
                        "message": message
                    }
                ]
            }
            status_code = 200
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="PUT",
            body=body,
            response_status=status_code,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_contact_id=zoho_id
        )
        
        return response_body
    
    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="PUT",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crm/v2/Deals")
async def create_deal(request: Request, db: Session = Depends(get_db)):
    """
    Crea un deal en Zoho CRM
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
        # VERIFICAR ERROR SIMULADO
    await check_and_raise_simulated_error(db, request, "/Deals")
    
    try:
        body = await request.json()
        deal_data = body.get("data", [{}])[0]
        triggers = body.get("trigger", [])
        
        # Obtener contacto relacionado si existe
        contact = None
        contact_id = deal_data.get("Contact_Name", {}).get("id")
        if contact_id:
            contact = ZohoMockService.get_contact_by_id(db, contact_id)
        
        deal = ZohoMockService.create_deal(db, deal_data, contact)
        
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                {
                    "code": "SUCCESS",
                    "status": "success",
                    "details": ZohoMockService._build_details_response(
                        zoho_id=deal.zoho_id,
                        created_at=deal.created_at,
                        modified_at=deal.updated_at,
                        include_creator=True
                    ),
                    "message": "record added"
                }
            ]
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="POST",
            body=body,
            response_status=201,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_deal_id=deal.zoho_id,
            zoho_contact_id=contact.zoho_id if contact else None
        )
        
        return response_body
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="POST",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/crm/v2/Deals")
async def update_deal(request: Request, db: Session = Depends(get_db)):
    """
    Actualiza un deal en Zoho CRM
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, "/Deals")
    
    try:
        body = await request.json()
        deal_data_list = body.get("data", [])
        
        results = []
        for deal_data in deal_data_list:
            zoho_id = deal_data.get("id")
            
            if not zoho_id:
                results.append({
                    "code": "REQUIRED_FIELD_MISSING",
                    "status": "error",
                    "message": "Deal ID is required"
                })
                continue
            
            deal, code, message = ZohoMockService.update_deal(db, zoho_id, deal_data)
            
            if not deal:
                results.append({
                    "code": code,
                    "status": "error",
                    "message": message
                })
            else:
                results.append({
                    "code": code,
                    "status": "success",
                    "details": ZohoMockService._build_details_response(
                        zoho_id=deal.zoho_id,
                        created_at=deal.created_at,
                        modified_at=deal.updated_at,
                        include_creator=True
                    ),
                    "message": message
                })
        
        response_body = {
            "data": results
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="PUT",
            body=body,
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms
        )
        
        return response_body
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="PUT",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/crm/v2/Deals/{deal_id}")
async def update_deal_by_id(request: Request,deal_id: str, db: Session = Depends(get_db)):
    """
    Actualiza un deal en Zoho CRM
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Deals/{deal_id}")
    
    try:
        body = await request.json()
        deal_data_list = body.get("data", [])
        
        results = []
        for deal_data in deal_data_list:
            zoho_id = deal_id
            
            if not zoho_id:
                results.append({
                    "code": "REQUIRED_FIELD_MISSING",
                    "status": "error",
                    "message": "Deal ID is required"
                })
                continue
            
            deal, code, message = ZohoMockService.update_deal(db, zoho_id, deal_data)
            
            if not deal:
                results.append({
                    "code": code,
                    "status": "error",
                    "message": message
                })
            else:
                results.append({
                    "code": code,
                    "status": "success",
                    "details": ZohoMockService._build_details_response(
                        zoho_id=deal.zoho_id,
                        created_at=deal.created_at,
                        modified_at=deal.updated_at,
                        include_creator=True
                    ),
                    "message": message
                })
        
        response_body = {
            "data": results
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint=f"/Deals/{deal_id}",
            method="PUT",
            body=body,
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms
        )
        
        return response_body
    
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint=f"/Deals/{deal_id}",
            method="PUT",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# Agregar después de update_deal

@router.post("/crm/v2/Leads")
async def create_lead(request: Request, db: Session = Depends(get_db)):
    """
    Crea un lead en Zoho CRM y automáticamente un Deal relacionado
    Formato de respuesta igual al Zoho real (basado en logs.txt)
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Leads")
    try:
        body = await request.json()
        lead_data_list = body.get("data", [])
        triggers = body.get("trigger", [])
        
        results = []
        created_deals = []
        
        for lead_data in lead_data_list:
            lead, is_new, code, message, deal = ZohoMockService.create_lead(db, lead_data)
            
            # Construir respuesta EXACTAMENTE como Zoho real
            result = {
                "code": code,
                "status": "success" if code == "SUCCESS" else "error",
                "details": ZohoMockService._build_details_response(
                    zoho_id=lead.zoho_id,
                    created_at=lead.created_at,
                    modified_at=lead.updated_at,
                    include_creator=True
                ),
                "message": message
            }
            results.append(result)
            
            if deal:
                created_deals.append(deal)
        
        response_body = {
            "data": results
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Leads",
            method="POST",
            body=body,
            response_status=201,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_lead_id=results[0]["details"]["id"] if results else None
        )
        return response_body
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Leads",
            method="POST",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/crm/v2/Leads")
async def update_lead(request: Request, db: Session = Depends(get_db)):
    """
    Actualiza un lead en Zoho CRM
    Formato de respuesta igual al Zoho real (similar a PUT /Deals)
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Leads")
    try:
        body = await request.json()
        
        response_body= {
            "data": [
                {
                    "code": "INVALID_DATA",
                    "details": {},
                    "message": "the id given seems to be invalid",
                    "status": "error"
                }
            ]
        }            
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Leads",
            method="PUT",
            body=body,
            response_status=202,
            response_body=response_body,
            response_time_ms=response_time_ms
        )
        
        return response_body
        
    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Leads",
            method="PUT",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


# Agregar después de update_deal en app/routes/zoho.py

@router.get("/crm/v2/Deals/search")
async def search_deals(
    request: Request,
    db: Session = Depends(get_db),
    criteria: Optional[str] = Query(None),
    per_page: int = Query(200, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort_by: str = Query("id", regex="^[a-zA-Z_]+$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Busca deals en Zoho CRM usando criterios
    Formato de respuesta igual al Zoho real
    Ejemplo: /Deals/search?criteria=(EC_ID:equals:FL-TEST00000001)
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Deals/search")
    try:
        # Parsear criterios de búsqueda
        search_filters = ZohoMockService.parse_search_criteria(criteria)
        
        # Ejecutar búsqueda
        deals, total_count = ZohoMockService.search_deals(
            db, search_filters, page, per_page, sort_by, sort_order
        )
        
        if not deals or len(deals) == 0:
            response_time_ms = int((time.time() - start_time) * 1000)
            await log_api_call(
                db=db,
                request=request,
                endpoint="/Deals/search",
                method="GET",
                response_status=204,
                response_body={},
                response_time_ms=response_time_ms,
                success=True
            )
            return Response(status_code=204)
        
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                {
                    **deal.deal_data,  # Todos los campos del deal
                }
                for deal in deals
            ],
            "info": {
                "per_page": per_page,
                "count": len(deals),
                "page": page,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "more_records": (page * per_page) < total_count
            }
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals/search",
            method="GET",
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_deal_id=deals[0].zoho_id if deals else None
        )
        return response_body
        
    except Exception as e:
        print(traceback.format_exc())
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "code": "ERROR",
            "status": "error",
            "message": str(e)
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals/search",
            method="GET",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
    


# Agregar después de update_contact en app/routes/zoho.py

@router.get("/crm/v2/Contacts/search")
async def search_contacts(
    request: Request,
    db: Session = Depends(get_db),
    criteria: Optional[str] = Query(None),
    per_page: int = Query(200, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort_by: str = Query("id", regex="^[a-zA-Z_]+$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Busca contactos en Zoho CRM usando criterios
    Formato de respuesta igual al Zoho real
    Ejemplos:
    - /Contacts/search?criteria=(Email:equals:correo@ejemplo.com)
    - /Contacts/search?criteria=(Phone:equals:52007922)
    - /Contacts/search?criteria=((Email:equals:correo@ejemplo.com)or(Phone:equals:52007922))
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Deals/search")
    try:
        # Parsear criterios de búsqueda
        search_filters = ZohoMockService.parse_search_criteria(criteria)
        
        # Ejecutar búsqueda
        contacts, total_count = ZohoMockService.search_contacts(
            db, search_filters, page, per_page, sort_by, sort_order
        )
        
        if not contacts or len(contacts) == 0:
            response_time_ms = int((time.time() - start_time) * 1000)
            await log_api_call(
                db=db,
                request=request,
                endpoint="/Contacts/search",
                method="GET",
                response_status=204,
                response_body={},
                response_time_ms=response_time_ms,
                success=True
            )
            return Response(status_code=204)
        
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                ZohoMockService.build_zoho_contact_response(contact)
                for contact in contacts
            ],
            "info": {
                "per_page": per_page,
                "count": len(contacts),
                "page": page,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "more_records": (page * per_page) < total_count
            }
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts/search",
            method="GET",
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_contact_id=contacts[0].zoho_id if contacts else None
        )
        return response_body
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "code": "ERROR",
            "status": "error",
            "message": str(e)
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts/search",
            method="GET",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crm/v2/Contacts/{contact_id}")
async def get_contact(
    request: Request,
    contact_id: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene un contacto por su Zoho ID
    Formato de respuesta igual al Zoho real
    """
    start_time = time.time()
    await check_and_raise_simulated_error(db, request, f"/Contacts/{contact_id}")
    try:
        contact = db.query(ZohoContact).filter(ZohoContact.zoho_id == contact_id).first()
        
        if not contact:
            # Verificar si el ID tiene formato válido (15 dígitos después de CRM)
            if not re.match(r'^\d{15,18}$', contact_id):
                response_body = {
                    "code": "INVALID_URL_PATTERN",
                    "details": {},
                    "message": "Please check if the URL trying to access is a correct one",
                    "status": "error"
                }
                response_time_ms = int((time.time() - start_time) * 1000)
                await log_api_call(
                    db=db,
                    request=request,
                    endpoint=f"/Contacts/{contact_id}",
                    method="GET",
                    response_status=404,
                    response_body=response_body,
                    response_time_ms=response_time_ms,
                    success=False,
                    error_message="Invalid URL pattern"
                )
                raise HTTPException(status_code=404, detail=response_body)
            
            # ID válido pero no encontrado
            response_time_ms = int((time.time() - start_time) * 1000)
            await log_api_call(
                db=db,
                request=request,
                endpoint=f"/Contacts/{contact_id}",
                method="GET",
                response_status=204,
                response_body={},
                response_time_ms=response_time_ms,
                success=True
            )
            return Response(status_code=204)
        
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                ZohoMockService.build_zoho_contact_response(contact)
            ]
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        await log_api_call(
            db=db,
            request=request,
            endpoint=f"/Contacts/{contact_id}",
            method="GET",
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_contact_id=contact.zoho_id
        )
        return response_body
        
    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "code": "ERROR",
            "status": "error",
            "message": str(e)
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint=f"/Contacts/{contact_id}",
            method="GET",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crm/v8/Deals/{deal_id}/actions/add_tags")
async def add_deal_tags(request: Request, deal_id: str, db: Session = Depends(get_db)):
    """
    Añade tags a un deal en Zoho CRM (Soporta ruta v8 explícita).
    Formato de respuesta igual al Zoho real.
    """
    start_time = time.time()
    endpoint_name = f"/Deals/{deal_id}/actions/add_tags"
    
    # VERIFICAR ERROR SIMULADO
    await check_and_raise_simulated_error(db, request, endpoint_name)
    
    try:
        body = await request.json()
        tags_input = body.get("tags", [])
        
        # Extraer solo los nombres de los tags enviados en el body
        tag_names = [tag.get("name") for tag in tags_input if isinstance(tag, dict) and tag.get("name")]
        
        deal, code, message = ZohoMockService.add_tags_to_deal(db, deal_id, tag_names)
        
        if not deal:
            error_response = {
                "data": [
                    {
                        "code": code,
                        "details": {},
                        "message": message,
                        "status": "error"
                    }
                ]
            }
            response_time_ms = int((time.time() - start_time) * 1000)
            await log_api_call(
                db=db,
                request=request,
                endpoint=endpoint_name,
                method="POST",
                body=body,
                response_status=404,
                response_body=error_response,
                response_time_ms=response_time_ms,
                success=False,
                error_message=message
            )
            return error_response
            
        # Construir respuesta EXACTAMENTE como Zoho real
        response_body = {
            "data": [
                {
                    "code": code,
                    "details": {
                        "id": deal.zoho_id,
                        "tags": deal.deal_data.get("tags", [])
                    },
                    "message": message,
                    "status": "success"
                }
            ]
        }
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        await log_api_call(
            db=db,
            request=request,
            endpoint=endpoint_name,
            method="POST",
            body=body,
            response_status=200,
            response_body=response_body,
            response_time_ms=response_time_ms,
            zoho_deal_id=deal.zoho_id
        )
        
        return response_body
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        error_response = {
            "data": [
                {
                    "code": "ERROR",
                    "status": "error",
                    "message": str(e)
                }
            ]
        }
        await log_api_call(
            db=db,
            request=request,
            endpoint=endpoint_name,
            method="POST",
            response_status=500,
            response_body=error_response,
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))