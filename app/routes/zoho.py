import time
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ApiLog
from app.services.zoho_mock import ZohoMockService
from app.services.logger import ApiLogger
from app.config import ZOHO_MOCK_CONFIG

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
    success: bool = True,
    error_message: Optional[str] = None
):
    """Registra llamada API en DB y archivos TXT"""
    request_id = ApiLogger.generate_request_id()
    
    # Headers
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
        success=success,
        error_message=error_message
    )
    db.add(api_log)
    db.commit()
    
    return request_id


@router.post("/token")
async def login(request: Request, db: Session = Depends(get_db)):
    """Simula login de Zoho para obtener access token"""
    start_time = time.time()
    
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


@router.post("/Contacts")
async def create_contact(request: Request, db: Session = Depends(get_db)):
    """Crea un contacto en Zoho CRM"""
    start_time = time.time()
    
    try:
        body = await request.json()
        contact_data = body.get("data", [{}])[0]
        
        contact, is_new = ZohoMockService.create_contact(db, contact_data)
        
        response_body = {
            "code": "SUCCESS",
            "details": {
                "id": contact.zoho_id,
                "created_time": contact.created_at.isoformat(),
                "modified_time": contact.updated_at.isoformat()
            },
            "message": "Contact created successfully",
            "status": "success"
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
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="POST",
            response_status=500,
            response_body={"error": str(e)},
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/Contacts")
async def update_contact(request: Request, db: Session = Depends(get_db)):
    """Actualiza un contacto en Zoho CRM"""
    start_time = time.time()
    
    try:
        body = await request.json()
        contact_data = body.get("data", [{}])[0]
        zoho_id = contact_data.get("id")
        
        if not zoho_id:
            raise HTTPException(status_code=400, detail="Contact ID is required")
        
        contact = ZohoMockService.update_contact(db, zoho_id, contact_data)
        
        if not contact:
            response_body = {
                "code": "NOT_FOUND",
                "message": f"Contact with ID {zoho_id} not found",
                "status": "error"
            }
            status_code = 404
        else:
            response_body = {
                "code": "SUCCESS",
                "details": {
                    "id": contact.zoho_id,
                    "modified_time": contact.updated_at.isoformat()
                },
                "message": "Contact updated successfully",
                "status": "success"
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
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Contacts",
            method="PUT",
            response_status=500,
            response_body={"error": str(e)},
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/Deals")
async def create_deal(request: Request, db: Session = Depends(get_db)):
    """Crea un deal en Zoho CRM"""
    start_time = time.time()
    
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
        
        response_body = {
            "code": "SUCCESS",
            "details": {
                "id": deal.zoho_id,
                "created_time": deal.created_at.isoformat(),
                "modified_time": deal.updated_at.isoformat()
            },
            "message": "Deal created successfully",
            "status": "success"
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
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="POST",
            response_status=500,
            response_body={"error": str(e)},
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/Deals")
async def update_deal(request: Request, db: Session = Depends(get_db)):
    """Actualiza un deal en Zoho CRM"""
    start_time = time.time()
    
    try:
        body = await request.json()
        deal_data_list = body.get("data", [])
        
        results = []
        for deal_data in deal_data_list:
            zoho_id = deal_data.get("id")
            
            if not zoho_id:
                results.append({
                    "code": "ERROR",
                    "message": "Deal ID is required",
                    "status": "error"
                })
                continue
            
            deal = ZohoMockService.update_deal(db, zoho_id, deal_data)
            
            if not deal:
                results.append({
                    "code": "NOT_FOUND",
                    "message": f"Deal with ID {zoho_id} not found",
                    "status": "error"
                })
            else:
                results.append({
                    "code": "SUCCESS",
                    "details": {
                        "id": deal.zoho_id,
                        "modified_time": deal.updated_at.isoformat()
                    },
                    "message": "Deal updated successfully",
                    "status": "success"
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
        await log_api_call(
            db=db,
            request=request,
            endpoint="/Deals",
            method="PUT",
            response_status=500,
            response_body={"error": str(e)},
            response_time_ms=response_time_ms,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))