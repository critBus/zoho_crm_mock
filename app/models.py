from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ZohoContact(Base):
    __tablename__ = "zoho_contacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoho_id = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(50))
    country = Column(String(100))
    state = Column(String(100))
    city = Column(String(100))
    address = Column(Text)
    postal_code = Column(String(20))
    account_name_id = Column(String(50))
    owner_id = Column(String(50))
    commercial_origin = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_logs = relationship("ApiLog", back_populates="contact")
    
    def __repr__(self):
        return f"<ZohoContact(zoho_id={self.zoho_id}, email={self.email})>"


class ZohoDeal(Base):
    __tablename__ = "zoho_deals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoho_id = Column(String(50), unique=True, nullable=False, index=True)
    ec_id = Column(String(100), index=True)
    deal_name = Column(String(255))
    amount = Column(String(50))
    stage = Column(String(100))
    contact_id = Column(String(50))  # Zoho ID del contacto relacionado
    account_name_id = Column(String(50))
    owner_id = Column(String(50))
    commercial_origin = Column(String(100))
    pipeline = Column(String(100))
    deal_data = Column(JSON)  # Datos completos del deal
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_logs = relationship("ApiLog", back_populates="deal")
    
    def __repr__(self):
        return f"<ZohoDeal(zoho_id={self.zoho_id}, deal_name={self.deal_name})>"


class ApiToken(Base):
    __tablename__ = "api_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    access_token = Column(String(500), nullable=False)
    refresh_token = Column(String(500))
    token_type = Column(String(50), default="Zoho-oauthtoken")
    expires_in = Column(Integer, default=3600)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<ApiToken(id={self.id}, active={self.is_active})>"


class ApiLog(Base):
    __tablename__ = "api_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Request Info
    request_id = Column(String(100), unique=True, index=True)
    endpoint = Column(String(500), index=True)
    method = Column(String(10), index=True)
    url = Column(Text)
    headers = Column(JSON)
    body = Column(JSON)
    query_params = Column(JSON)
    
    # Response Info
    response_status_code = Column(Integer, index=True)
    response_headers = Column(JSON)
    response_body = Column(JSON)
    response_time_ms = Column(Integer)
    
    # Metadata
    zoho_contact_id = Column(String(50), ForeignKey("zoho_contacts.zoho_id"), nullable=True)
    zoho_deal_id = Column(String(50), ForeignKey("zoho_deals.zoho_id"), nullable=True)
    zoho_lead_id = Column(String(50), ForeignKey("zoho_leads.zoho_id"), nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    contact = relationship("ZohoContact", back_populates="api_logs")
    deal = relationship("ZohoDeal", back_populates="api_logs")
    lead = relationship("ZohoLead", back_populates="api_logs")
    
    def __repr__(self):
        return f"<ApiLog(id={self.id}, endpoint={self.endpoint}, status={self.response_status_code})>"


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), index=True)
    entity = Column(String(50))
    entity_id = Column(String(50))
    action = Column(String(50))
    payload = Column(JSON)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<WebhookLog(id={self.id}, event_type={self.event_type})>"
    


# Agregar después de ZohoDeal
class ZohoLead(Base):
    __tablename__ = "zoho_leads"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    zoho_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Datos básicos del lead
    email = Column(String(255), index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(50))
    mobile = Column(String(50))
    country = Column(String(100))
    state = Column(String(100))
    city = Column(String(100))
    address = Column(Text)
    postal_code = Column(String(20))
    
    # Datos específicos de Leads (basado en tus logs)
    ec_id = Column(String(100), index=True)
    company = Column(String(255))
    title = Column(String(100))
    industry = Column(String(100))
    annual_revenue = Column(String(50))
    number_of_employees = Column(String(20))
    lead_source = Column(String(100))
    lead_status = Column(String(100))
    rating = Column(String(50))
    
    # Campos personalizados de tus logs
    plataforma = Column(String(100))
    tipo_cliente = Column(String(50))
    origen_comercial = Column(String(255))
    tipo_de_servicio = Column(String(100))
    agencia_enjoy_pro = Column(String(255))
    agencia_padre = Column(String(255))
    vendedor = Column(String(100))
    mercado = Column(String(100))
    importe = Column(String(50))
    estado_expediente = Column(String(100))
    estado_de_la_reserva = Column(String(100))
    
    # Datos completos en JSON para flexibilidad
    lead_data = Column(JSON)
    
    owner_id = Column(String(50))
    commercial_origin = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_logs = relationship("ApiLog", back_populates="lead")
    
    def __repr__(self):
        return f"<ZohoLead(zoho_id={self.zoho_id}, email={self.email})>"