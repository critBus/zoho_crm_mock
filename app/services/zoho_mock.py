import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models import ZohoContact, ZohoDeal, ApiToken
from app.config import ZOHO_MOCK_CONFIG
from app.models import ZohoContact, ZohoDeal, ZohoLead, ApiToken
import re
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import and_, or_

class ZohoMockService:
    """Servicio que simula el comportamiento de Zoho CRM API"""
    
    # Owner y Created_By defaults (basado en tus logs)
    DEFAULT_OWNER_ID = "711111000000111111"
    DEFAULT_OWNER_NAME = "Zoho Defualt Owner"
    
    @staticmethod
    def generate_zoho_id(prefix: str = "CRM") -> str:
        """Genera un ID único de Zoho (15 dígitos como en los logs reales)"""
        random_part = ''.join(random.choices(string.digits, k=15))
        return f"{prefix}{random_part}"
    
    @staticmethod
    def get_or_create_token(db: Session) -> ApiToken:
        """Obtiene o crea un token de acceso"""
        token = db.query(ApiToken).filter(ApiToken.is_active == True).first()
        
        if not token or (token.expires_at and token.expires_at < datetime.utcnow()):
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
    def _build_details_response(
        zoho_id: str, 
        created_at: datetime, 
        modified_at: datetime,
        include_creator: bool = True
    ) -> Dict[str, Any]:
        """Construye el objeto details igual que Zoho real"""
        details = {
            "id": zoho_id,
            "Created_Time": created_at.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
            "Modified_Time": modified_at.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
        }
        
        if include_creator:
            details["Created_By"] = {
                "id": ZohoMockService.DEFAULT_OWNER_ID,
                "name": ZohoMockService.DEFAULT_OWNER_NAME
            }
            details["Modified_By"] = {
                "id": ZohoMockService.DEFAULT_OWNER_ID,
                "name": ZohoMockService.DEFAULT_OWNER_NAME
            }
        
        return details
    
    @staticmethod
    def create_contact(db: Session, contact_data: Dict[str, Any]) -> Tuple[ZohoContact, bool, str]:
        """
        Crea o actualiza un contacto
        Returns: (contact, is_new, response_code)
        """
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
            response_code = "SUCCESS"
            message = "record added"
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
            
            response_code = "DUPLICATE_DATA"
            message = "duplicate data"
        
        db.commit()
        db.refresh(contact)
        
        return contact, is_new, response_code, message
    
    @staticmethod
    def update_contact(db: Session, zoho_id: str, contact_data: Dict[str, Any]) -> Tuple[Optional[ZohoContact], str, str]:
        """
        Actualiza un contacto existente
        Returns: (contact, response_code, message)
        """
        contact = db.query(ZohoContact).filter(ZohoContact.zoho_id == zoho_id).first()
        
        if not contact:
            return None, "NOT_FOUND", f"Contact with ID {zoho_id} not found"
        
        # Actualizar campos permitidos
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
            if zoho_field in contact_data and model_field in ["first_name", "last_name", "phone", "country", "state", "city", "address", "postal_code", "email"]:
                setattr(contact, model_field, contact_data[zoho_field])
        
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)
        
        return contact, "SUCCESS", "record updated"
    
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
            ec_id=deal_data.get("EC_ID", ""),
            pipeline=deal_data.get("Pipeline", ""),
            deal_data=deal_data,
        )
        
        db.add(deal)
        db.commit()
        db.refresh(deal)
        
        return deal
    
    @staticmethod
    def update_deal(db: Session, zoho_id: str, deal_data: Dict[str, Any]) -> Tuple[Optional[ZohoDeal], str, str]:
        """
        Actualiza un deal existente
        Returns: (deal, response_code, message)
        """
        deal = db.query(ZohoDeal).filter(ZohoDeal.zoho_id == zoho_id).first()
        
        if not deal:
            return None, "NOT_FOUND", f"Deal with ID {zoho_id} not found"
        
        # Actualizar campos permitidos
        field_mapping = {
            "Deal_Name": "deal_name",
            "Amount": "amount",
            "Stage": "stage",
            "Origen_Comercial": "commercial_origin",
            "Pipeline": "pipeline",
            "Tienda": "commercial_origin"
        }
        
        for zoho_field, model_field in field_mapping.items():
            if zoho_field in deal_data and model_field in ["deal_name", "amount", "stage", "commercial_origin", "pipeline"]:
                setattr(deal, model_field, deal_data[zoho_field])
        
        # Actualizar deal_data completo
        deal.deal_data = {**deal.deal_data, **deal_data}
        deal.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(deal)
        
        return deal, "SUCCESS", "record updated"
    
    @staticmethod
    def get_contact_by_id(db: Session, zoho_id: str) -> Optional[ZohoContact]:
        """Obtiene un contacto por su Zoho ID"""
        return db.query(ZohoContact).filter(ZohoContact.zoho_id == zoho_id).first()
    
    @staticmethod
    def get_deal_by_id(db: Session, zoho_id: str) -> Optional[ZohoDeal]:
        """Obtiene un deal por su Zoho ID"""
        return db.query(ZohoDeal).filter(ZohoDeal.zoho_id == zoho_id).first()
    



    # Agregar después de get_deal_by_id

    @staticmethod
    def create_lead(db: Session, lead_data: Dict[str, Any]) -> Tuple[ZohoLead, bool, str, str, Optional[ZohoDeal]]:
        """
        Crea o actualiza un lead y automáticamente crea un Deal relacionado
        Returns: (lead, is_new, response_code, message, deal)
        """
        email = lead_data.get("Email", "")
        phone = lead_data.get("Phone", "")
        mobile = lead_data.get("Mobile", "")
        ec_id = lead_data.get("EC_ID", "")
        
        # Buscar lead existente por EC_ID
        existing_lead = None
        if ec_id:
            existing_lead = db.query(ZohoLead).filter(ZohoLead.ec_id == ec_id).first()
        
        is_new = existing_lead is None
        created_deal = None
        
        if is_new:
            zoho_id = ZohoMockService.generate_zoho_id("LEAD")
            lead = ZohoLead(
                zoho_id=zoho_id,
                email=email,
                first_name=lead_data.get("First_Name", ""),
                last_name=lead_data.get("Last_Name", ""),
                phone=phone,
                mobile=mobile,
                country=lead_data.get("Pais", "") or lead_data.get("Country", ""),
                state=lead_data.get("OCPI_state", "") or lead_data.get("State", ""),
                city=lead_data.get("OCPI_City", "") or lead_data.get("City", ""),
                address=lead_data.get("Direccion", "") or lead_data.get("Address", ""),
                postal_code=lead_data.get("OCPI_Zip_Code", "") or lead_data.get("Zip_Code", ""),
                # Campos específicos de Leads
                ec_id=ec_id,
                company=lead_data.get("Company", ""),
                title=lead_data.get("Title", ""),
                industry=lead_data.get("Industry", ""),
                lead_source=lead_data.get("Lead_Source", ""),
                lead_status=lead_data.get("Lead_Status", "New"),
                rating=lead_data.get("Rating", ""),
                # Campos personalizados
                plataforma=lead_data.get("Plataforma", ""),
                tipo_cliente=lead_data.get("tipo_cliente", ""),
                origen_comercial=lead_data.get("Origen_Comercial", ""),
                tipo_de_servicio=lead_data.get("Tipo_de_Servicio", ""),
                agencia_enjoy_pro=lead_data.get("Agencia_Enjoy_PRO", ""),
                agencia_padre=lead_data.get("Agencia_Padre", ""),
                vendedor=lead_data.get("Vendedor", ""),
                mercado=str(lead_data.get("Mercados", [])),
                importe=str(lead_data.get("Importe", "")),
                estado_expediente=lead_data.get("Estado_Expediente", ""),
                estado_de_la_reserva=lead_data.get("Estado_de_la_Reserva", ""),
                lead_data=lead_data,
                owner_id=lead_data.get("Owner", {}).get("id") if isinstance(lead_data.get("Owner"), dict) else None,
                commercial_origin=lead_data.get("Origen_Comercial", ""),
            )
            db.add(lead)
            db.flush()  # Para obtener el ID antes de commit
            response_code = "SUCCESS"
            message = "record added"
            
            # CREAR DEAL AUTOMÁTICAMENTE (nuevo comportamiento)
            created_deal = ZohoMockService._create_deal_from_lead(db, lead, lead_data)
            
        else:
            lead = existing_lead
            # Actualizar campos
            lead.first_name = lead_data.get("First_Name", lead.first_name)
            lead.last_name = lead_data.get("Last_Name", lead.last_name)
            lead.phone = phone or lead.phone
            lead.mobile = mobile or lead.mobile
            lead.country = lead_data.get("Pais", lead.country)
            lead.state = lead_data.get("OCPI_state", lead.state)
            lead.city = lead_data.get("OCPI_City", lead.city)
            lead.address = lead_data.get("Direccion", lead.address)
            lead.postal_code = lead_data.get("OCPI_Zip_Code", lead.postal_code)
            # Actualizar campos personalizados
            lead.plataforma = lead_data.get("Plataforma", lead.plataforma)
            lead.tipo_cliente = lead_data.get("tipo_cliente", lead.tipo_cliente)
            lead.origen_comercial = lead_data.get("Origen_Comercial", lead.origen_comercial)
            lead.tipo_de_servicio = lead_data.get("Tipo_de_Servicio", lead.tipo_de_servicio)
            lead.agencia_enjoy_pro = lead_data.get("Agencia_Enjoy_PRO", lead.agencia_enjoy_pro)
            lead.agencia_padre = lead_data.get("Agencia_Padre", lead.agencia_padre)
            lead.vendedor = lead_data.get("Vendedor", lead.vendedor)
            lead.estado_expediente = lead_data.get("Estado_Expediente", lead.estado_expediente)
            lead.estado_de_la_reserva = lead_data.get("Estado_de_la_Reserva", lead.estado_de_la_reserva)
            # Actualizar lead_data completo
            lead.lead_data = {**lead.lead_data, **lead_data}
            lead.updated_at = datetime.utcnow()
            response_code = "DUPLICATE_DATA"
            message = "duplicate data"
        
        db.commit()
        db.refresh(lead)
        if created_deal:
            db.refresh(created_deal)
        return lead, is_new, response_code, message, created_deal

    @staticmethod
    def _create_deal_from_lead(db: Session, lead: ZohoLead, lead_data: Dict[str, Any]) -> ZohoDeal:
        """
        Crea un Deal automáticamente cuando se crea un Lead
        Basado en el comportamiento real de Zoho CRM
        """
        # Generar ID único para el Deal
        deal_zoho_id = ZohoMockService.generate_zoho_id("DEAL")
        
        # Generar nombre del Deal automático (similar al real: T-TES_118264)
        numeracion = ''.join(random.choices(string.digits, k=6))
        deal_name = f"T-TES_{numeracion}"
        
        # Crear el Deal con los datos del Lead
        deal = ZohoDeal(
            zoho_id=deal_zoho_id,
            ec_id=lead.ec_id,  # Mismo EC_ID que el Lead
            deal_name=deal_name,
            amount=lead_data.get("Amount", "0"),
            stage=lead_data.get("Stage", "Nueva solicitud"),
            contact_id=lead.zoho_id,  # Relacionar con el Lead
            account_name_id=lead_data.get("Account_Name", {}).get("id") if isinstance(lead_data.get("Account_Name"), dict) else None,
            owner_id=lead.owner_id,
            commercial_origin=lead.origen_comercial,
            pipeline=lead_data.get("Pipeline", ""),
            # Guardar todos los campos en deal_data para búsqueda
            deal_data={
                **lead_data,
                "EC_ID": lead.ec_id,
                "Deal_Name": deal_name,
                "Stage": "Nueva solicitud",
                "Probability": 100,
                "Currency": "EUR",
                "Moneda": "EUROS",
                "Moneda_de_la_venta": "Sin escoger",
                "Exchange_Rate": 1,
                "Cost_per_Click": 0,
                "Cost_per_Conversion": 0,
                "Media_de_correos": 0,
                "Perdidos": 0,
                "Cantidad_de_días_en_cerrar": 0,
                "MC_Estimado": 0,
                "Prueba": 1,
                "Numeración_automática": numeracion,
                "Margen_de_Utilidad_1": 100,
                "Recomendaciones_de_vuelos": False,
                "Quiero_personalizar_mi_viaje": False,
                "Me_interesa_alquilar_un_coche": False,
                "Acepto_la_Política_de_Privacidad": True,
                "Enviar_Voucher": False,
                "Pertenece_a_Otas": False,
                "Pertenece_al_riesgo": "Sin seleccionar",
                "Locked__s": False,
                "Receptivo_Europa": False,
                "Con_quien_viaja": "Solo",
                "Acepta_recibir_informaciones_comerciales": False,
                "Predicción_de_venta_Prediction": "2026-05-10",
                # Campos de auditoría
                "Created_By": {
                    "name": "El que lo creo",
                    "id": ZohoMockService.DEFAULT_OWNER_ID,
                    "email": "elcorreo@example.com"
                },
                "Modified_By": {
                    "name": "PRODUCTO ETG",
                    "id": "452XXX0000000XXX00X",
                    "email": "test@test.test"
                },
                "Owner": {
                    "name": ZohoMockService.DEFAULT_OWNER_NAME,
                    "id": ZohoMockService.DEFAULT_OWNER_ID,
                    "email": "test@test.test"
                },
                "Contact_Name": {
                    "name": f"{lead.first_name} {lead.last_name}",
                    "id": lead.zoho_id
                },
                "Created_Time": lead.created_at.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                "Modified_Time": lead.updated_at.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                "Last_Activity_Time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+01:00"),
                "id": deal_zoho_id,
            }
        )
        
        db.add(deal)
        return deal

    @staticmethod
    def update_lead(db: Session, zoho_id: str, lead_data: Dict[str, Any]) -> Tuple[Optional[ZohoLead], str, str]:
        """
        Actualiza un lead existente
        Returns: (lead, response_code, message)
        """
        lead = db.query(ZohoLead).filter(ZohoLead.zoho_id == zoho_id).first()
        
        if not lead:
            return None, "NOT_FOUND", f"Lead with ID {zoho_id} not found"
        
        # Mapeo de campos de Zoho a modelo
        field_mapping = {
            "First_Name": "first_name",
            "Last_Name": "last_name",
            "Mobile": "mobile",
            "Phone": "phone",
            "Email": "email",
            "Pais": "country",
            "Country": "country",
            "OCPI_state": "state",
            "State": "state",
            "OCPI_City": "city",
            "City": "city",
            "Direccion": "address",
            "Address": "address",
            "OCPI_Zip_Code": "postal_code",
            "Zip_Code": "postal_code",
            "Company": "company",
            "Title": "title",
            "Industry": "industry",
            "Lead_Source": "lead_source",
            "Lead_Status": "lead_status",
            "Rating": "rating",
            "Plataforma": "plataforma",
            "tipo_cliente": "tipo_cliente",
            "Origen_Comercial": "origen_comercial",
            "Tipo_de_Servicio": "tipo_de_servicio",
            "Agencia_Enjoy_PRO": "agencia_enjoy_pro",
            "Agencia_Padre": "agencia_padre",
            "Vendedor": "vendedor",
            "Estado_Expediente": "estado_expediente",
            "Estado_de_la_Reserva": "estado_de_la_reserva",
        }
        
        for zoho_field, model_field in field_mapping.items():
            if zoho_field in lead_data and hasattr(lead, model_field):
                setattr(lead, model_field, lead_data[zoho_field])
        
        # Actualizar lead_data completo
        lead.lead_data = {**lead.lead_data, **lead_data}
        lead.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(lead)
        
        return lead, "SUCCESS", "record updated"

    @staticmethod
    def get_lead_by_id(db: Session, zoho_id: str) -> Optional[ZohoLead]:
        """Obtiene un lead por su Zoho ID"""
        return db.query(ZohoLead).filter(ZohoLead.zoho_id == zoho_id).first()

    @staticmethod
    def get_lead_by_email(db: Session, email: str) -> Optional[ZohoLead]:
        """Obtiene un lead por email"""
        return db.query(ZohoLead).filter(ZohoLead.email == email).first()
    


    @staticmethod
    def parse_search_criteria(criteria: Optional[str]) -> Dict[str, Any]:
        """
        Parsea el criterio de búsqueda de Zoho CRM
        Ejemplo: (EC_ID:equals:TRVD-F31E4D177F1)
        Ejemplo: (EC_ID:equals:FL-49E91ADFF6DC)and(Pasaporte:equals:N08799193)
        """
        filters = {}
        
        if not criteria:
            return filters
        
        # Patrón para extraer campos y valores
        # Formato: (Campo:operador:valor)
        pattern = r'\(([A-Za-z_]+):(equals|contains|starts_with|ends_with):([^)]+)\)'
        matches = re.findall(pattern, criteria)
        
        for field, operator, value in matches:
            filters[field] = {
                'operator': operator,
                'value': value
            }
        
        return filters

    # En el método search_deals de ZohoMockService, actualizar para buscar en deal_data
    @staticmethod
    def search_deals(
        db: Session,
        filters: Dict[str, Any],
        page: int = 1,
        per_page: int = 200,
        sort_by: str = "id",
        sort_order: str = "desc"
    ) -> Tuple[List[ZohoDeal], int]:
        """
        Busca deals en la base de datos según los criterios
        Returns: (lista_deals, total_count)
        """
        # Obtener todos los deals y filtrar manualmente para soporte JSON
        all_deals = db.query(ZohoDeal).all()
        filtered_deals = []
        
        for deal in all_deals:
            match = True
            deal_json = deal.deal_data or {}
            
            for field, filter_info in filters.items():
                operator = filter_info['operator']
                value = filter_info['value']
                
                # Buscar en campos directos del modelo
                if hasattr(deal, field.lower()):
                    model_value = getattr(deal, field.lower(), None)
                    if operator == 'equals' and str(model_value) != str(value):
                        match = False
                        break
                    elif operator == 'contains' and value not in str(model_value):
                        match = False
                        break
                
                # Buscar en deal_data (JSON) para campos personalizados como EC_ID
                elif field in deal_json:
                    deal_value = str(deal_json[field])
                    if operator == 'equals' and deal_value != value:
                        match = False
                        break
                    elif operator == 'contains' and value not in deal_value:
                        match = False
                        break
                else:
                    # Campo no encontrado
                    match = False
                    break
            
            if match:
                filtered_deals.append(deal)
        
        total_count = len(filtered_deals)
        
        # Ordenar
        if sort_order == 'desc':
            filtered_deals.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
        else:
            filtered_deals.sort(key=lambda x: x.updated_at or x.created_at)
        
        # Paginación
        offset = (page - 1) * per_page
        deals = filtered_deals[offset:offset + per_page]
        
        return deals, total_count