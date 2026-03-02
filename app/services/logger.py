import json
import uuid
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import REQUESTS_LOG_DIR, RESPONSES_LOG_DIR

class ApiLogger:
    """Logger para registrar todas las peticiones y respuestas"""
    
    @staticmethod
    def generate_request_id() -> str:
        return f"req_{uuid.uuid4().hex[:12]}"
    
    @staticmethod
    def generate_filename(endpoint: str, request_id: str, log_type: str) -> str:
        """Genera nombre de archivo para logs TXT"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Limpiar endpoint para nombre de archivo
        clean_endpoint = endpoint.replace("/", "_").replace("?", "_").replace("=", "_")
        if len(clean_endpoint) > 50:
            clean_endpoint = clean_endpoint[:50]
        return f"{timestamp}_{clean_endpoint}_{request_id}_{log_type}.txt"
    
    @staticmethod
    async def log_request(
        request_id: str,
        endpoint: str,
        method: str,
        url: str,
        headers: Dict[str, Any],
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Registra petición de entrada en DB y TXT"""
        filename = ApiLogger.generate_filename(endpoint, request_id, "request")
        filepath = REQUESTS_LOG_DIR / filename
        
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "query_params": query_params
        }
        
        # Escribir archivo TXT
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(log_data, indent=2, ensure_ascii=False))
        
        return filename
    
    @staticmethod
    async def log_response(
        request_id: str,
        endpoint: str,
        status_code: int,
        headers: Dict[str, Any],
        body: Dict[str, Any],
        response_time_ms: int,
        zoho_contact_id: Optional[str] = None,
        zoho_deal_id: Optional[str] = None,
        zoho_lead_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> str:
        """Registra respuesta de salida en DB y TXT"""
        filename = ApiLogger.generate_filename(endpoint, request_id, "response")
        filepath = RESPONSES_LOG_DIR / filename
        
        log_data = {
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": endpoint,
            "status_code": status_code,
            "headers": headers,
            "body": body,
            "response_time_ms": response_time_ms,
            "zoho_contact_id": zoho_contact_id,
            "zoho_deal_id": zoho_deal_id,
            "zoho_lead_id": zoho_lead_id,
            "success": success,
            "error_message": error_message
        }
        
        # Escribir archivo TXT
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(log_data, indent=2, ensure_ascii=False))
        
        return filename