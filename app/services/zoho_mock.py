import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models import ZohoContact, ZohoDeal, ApiToken
from app.config import ZOHO_MOCK_CONFIG

class ZohoMockService:
    """Servicio que simula el comportamiento de Zoho CRM API"""
    
    @staticmethod
    def generate_zoho_id(prefix: str = "CRM") -> str:
        """Genera un ID único de Zoho"""
        random_part = ''.join(random.choices(string.digits, k=15))
        return f"{prefix}{random_part}"
    
    @staticmethod
    def get_or_create_token(db: Session) -> ApiToken:
        """Obtiene o crea un token de acceso"""
        token = db.query(ApiToken).filter(ApiToken.is_active == True).first()
        
        if not token or (token.expires_at and token.expires_at < datetime.utcnow()):
            # Crear nuevo token
            if token:
                token.is_active = False
                db.add(token)
            
            expires_at = datetime.utcnow() + timedelta(seconds=3600)
            token = ApiToken(
                access_token=ZOHO_MOCK_CONFIG["default_access_token"],
                refresh_token="mock_refresh_token_" + ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
                expires_in=3600,
                expires_at=expires_at,
                is_active=True
            )
            db.add(token)
            db.commit()
            db.refresh(token)
        
        return token
    
    @staticmethod
    def create_contact(db: Session, contact_data: Dict[str, Any]) -> Tuple[ZohoContact, bool]:
        """Crea o actualiza un contacto"""
        email = contact_data.get("Email", "")
        phone = contact_data.get("Mobile", "")
        
        # Buscar contacto existente por email o teléfono
        existing_contact = None
        if email:
            existing_contact = db.query(ZohoContact).filter(ZohoContact.email == email).first()
        if not existing_contact and phone:
            existing_contact = db.query(ZohoContact).filter(ZohoContact.phone == phone).first()
        
        is_new = existing_contact is None
        
        if is_new:
            zoho_id = ZohoMockService.generate_zoho_id("CRM")
            contact = ZohoContact(
                zoho_id=zoho_id,
                email=email,
                first_name=contact_data.get("First_Name", ""),
                last_name=contact_data.get("Last_Name", ""),
                phone=phone,
                country=contact_data.get("Pa_s", ""),
                state=contact_data.get("Estado", ""),
                city=contact_data.get("Ciudad", ""),
                address=contact_data.get("Direcci_n", ""),
                postal_code=contact_data.get("Mailing_Zip", ""),
                account_name_id=contact_data.get("Account_Name", {}).get("id") if isinstance(contact_data.get("Account_Name"), dict) else None,
                owner_id=contact_data.get("Owner", {}).get("id") if isinstance(contact_data.get("Owner"), dict) else None,
                commercial_origin=contact_data.get("Origen_Comercial", ""),
            )
            db.add(contact)
        else:
            contact = existing_contact
            # Actualizar campos
            contact.first_name = contact_data.get("First_Name", contact.first_name)
            contact.last_name = contact_data.get("Last_Name", contact.last_name)
            contact.phone = phone or contact.phone
            contact.country = contact_data.get("Pa_s", contact.country)
            contact.state = contact_data.get("Estado", contact.state)
            contact.city = contact_data.get("Ciudad", contact.city)
            contact.address = contact_data.get("Direcci_n", contact.address)
            contact.postal_code = contact_data.get("Mailing_Zip", contact.postal_code)
            contact.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(contact)
        
        return contact, is_new
    
    @staticmethod
    def update_contact(db: Session, zoho_id: str, contact_data: Dict[str, Any]) -> Optional[ZohoContact]:
        """Actualiza un contacto existente"""
        contact = db.query(ZohoContact).filter(ZohoContact.zoho_id == zoho_id).first()
        
        if not contact:
            return None
        
        # Actualizar campos permitidos
        updatable_fields = [
            "first_name", "last_name", "phone", "country", "state", 
            "city", "address", "postal_code", "email"
        ]
        
        field_mapping = {
            "First_Name": "first_name",
            "Last_Name": "last_name",
            "Mobile": "phone",
            "Pa_s": "country",
            "Estado": "state",
            "Ciudad": "city",
            "Direcci_n": "address",
            "Mailing_Zip": "postal_code",
            "Email": "email",
            "Tienda": "commercial_origin"
        }
        
        for zoho_field, model_field in field_mapping.items():
            if zoho_field in contact_data and model_field in updatable_fields:
                setattr(contact, model_field, contact_data[zoho_field])
        
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)
        
        return contact
    
    @staticmethod
    def create_deal(db: Session, deal_data: Dict[str, Any], contact: Optional[ZohoContact] = None) -> ZohoDeal:
        """Crea un deal en Zoho"""
        zoho_id = ZohoMockService.generate_zoho_id("DEAL")
        
        deal = ZohoDeal(
            zoho_id=zoho_id,
            deal_name=deal_data.get("Deal_Name", ""),
            amount=deal_data.get("Amount", "0"),
            stage=deal_data.get("Stage", "Nueva solicitud"),
            contact_id=contact.zoho_id if contact else deal_data.get("Contact_Name", {}).get("id"),
            account_name_id=deal_data.get("Account_Name", {}).get("id") if isinstance(deal_data.get("Account_Name"), dict) else None,
            owner_id=deal_data.get("Owner", {}).get("id") if isinstance(deal_data.get("Owner"), dict) else None,
            commercial_origin=deal_data.get("Origen_Comercial", ""),
            pipeline=deal_data.get("Pipeline", ""),
            deal_data=deal_data,
        )
        
        db.add(deal)
        db.commit()
        db.refresh(deal)
        
        return deal
    
    @staticmethod
    def update_deal(db: Session, zoho_id: str, deal_data: Dict[str, Any]) -> Optional[ZohoDeal]:
        """Actualiza un deal existente"""
        deal = db.query(ZohoDeal).filter(ZohoDeal.zoho_id == zoho_id).first()
        
        if not deal:
            return None
        
        # Actualizar campos permitidos
        updatable_fields = [
            "deal_name", "amount", "stage", "commercial_origin", "pipeline"
        ]
        
        field_mapping = {
            "Deal_Name": "deal_name",
            "Amount": "amount",
            "Stage": "stage",
            "Origen_Comercial": "commercial_origin",
            "Pipeline": "pipeline",
            "Tienda": "commercial_origin"
        }
        
        for zoho_field, model_field in field_mapping.items():
            if zoho_field in deal_data and model_field in updatable_fields:
                setattr(deal, model_field, deal_data[zoho_field])
        
        # Actualizar deal_data completo
        deal.deal_data = {**deal.deal_data, **deal_data}
        deal.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(deal)
        
        return deal
    
    @staticmethod
    def get_contact_by_id(db: Session, zoho_id: str) -> Optional[ZohoContact]:
        """Obtiene un contacto por su Zoho ID"""
        return db.query(ZohoContact).filter(ZohoContact.zoho_id == zoho_id).first()
    
    @staticmethod
    def get_deal_by_id(db: Session, zoho_id: str) -> Optional[ZohoDeal]:
        """Obtiene un deal por su Zoho ID"""
        return db.query(ZohoDeal).filter(ZohoDeal.zoho_id == zoho_id).first()