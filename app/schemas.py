from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

# Token
class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str = "Zoho-oauthtoken"

# Contact
class ContactInput(BaseModel):
    data: List[Dict[str, Any]]

class ContactResponse(BaseModel):
    code: str
    details: Dict[str, Any]
    message: str
    status: str

# Deal
class DealInput(BaseModel):
    data: List[Dict[str, Any]]
    trigger: Optional[List[str]] = None

class DealResponse(BaseModel):
    code: str
    details: Dict[str, Any]
    message: str
    status: str

# API Log
class ApiLogSchema(BaseModel):
    id: int
    request_id: str
    endpoint: str
    method: str
    url: str
    response_status_code: int
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ApiLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    logs: List[ApiLogSchema]

# Contact List
class ContactSchema(BaseModel):
    id: int
    zoho_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Deal List
class DealSchema(BaseModel):
    id: int
    zoho_id: str
    deal_name: str
    amount: Optional[str]
    stage: Optional[str]
    contact_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Agregar después de Deal List

# Lead
class LeadInput(BaseModel):
    data: List[Dict[str, Any]]
    trigger: Optional[List[str]] = None

class LeadResponse(BaseModel):
    code: str
    details: Dict[str, Any]
    message: str
    status: str

class LeadSchema(BaseModel):
    id: int
    zoho_id: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    mobile: Optional[str]
    company: Optional[str]
    lead_status: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Agregar al final de app/schemas.py

class ErrorSimulationSchema(BaseModel):
    id: int
    error_type: str
    is_active: bool
    consecutive_errors: int
    current_error_count: int
    endpoint_filter: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ErrorSimulationInput(BaseModel):
    error_type: str
    is_active: bool = True
    consecutive_errors: int = 1
    endpoint_filter: Optional[str] = None

class ErrorSimulationResponse(BaseModel):
    success: bool
    message: str
    simulation: Optional[ErrorSimulationSchema] = None