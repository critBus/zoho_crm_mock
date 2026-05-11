# Crear nuevo archivo: app/services/error_simulation.py

from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import ErrorSimulation
import requests
from requests.exceptions import ConnectTimeout, SSLError, Timeout, ConnectionError
import time
from fastapi import HTTPException

class ErrorSimulationService:
    """Servicio para simular errores de conexión"""
    
    VALID_ERROR_TYPES = [
        "ConnectTimeout",
        "SSLError", 
        "Timeout",
        "ConnectionError"
    ]
    
    @staticmethod
    def get_active_simulation(db: Session, endpoint: str) -> Optional[ErrorSimulation]:
        """Obtiene la simulación activa para un endpoint"""
        # Buscar simulación específica para el endpoint
        simulation = db.query(ErrorSimulation).filter(
            ErrorSimulation.is_active == True,
            ErrorSimulation.endpoint_filter == endpoint
        ).first()
        
        # Si no hay específica, buscar una global (sin filtro)
        if not simulation:
            simulation = db.query(ErrorSimulation).filter(
                ErrorSimulation.is_active == True,
                ErrorSimulation.endpoint_filter == None
            ).first()
        
        return simulation
    
    @staticmethod
    def should_raise_error(simulation: ErrorSimulation) -> bool:
        """Determina si debe levantar un error basado en el contador"""
        if not simulation.is_active:
            return False
        
        if simulation.current_error_count < simulation.consecutive_errors:
            return True
        
        return False
    
    @staticmethod
    def increment_error_count(db: Session, simulation: ErrorSimulation):
        """Incrementa el contador de errores"""
        simulation.current_error_count += 1
        simulation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(simulation)
    
    @staticmethod
    def reset_error_count(db: Session, simulation: ErrorSimulation):
        """Resetea el contador de errores"""
        simulation.current_error_count = 0
        simulation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(simulation)
    
    @staticmethod
    def raise_simulated_error(error_type: str, url: str):
        """Levanta la excepción simulada correspondiente"""
        error_messages = {
            "ConnectTimeout": f"HTTPSConnectionPool(host='www.zohoapis.eu', port=443): Max retries exceeded with url: {url} (Caused by ConnectTimeoutError)",
            "SSLError": f"HTTPSConnectionPool(host='www.zohoapis.eu', port=443): Max retries exceeded with url: {url} (Caused by SSLError(SSL: UNEXPECTED_EOF_WHILE_READING))",
            "Timeout": f"HTTPSConnectionPool(host='www.zohoapis.eu', port=443): Max retries exceeded with url: {url} (Caused by TimeoutError)",
            "ConnectionError": f"HTTPSConnectionPool(host='www.zohoapis.eu', port=443): Max retries exceeded with url: {url} (Caused by ConnectionError)"
        }
        
        error_message = error_messages.get(error_type, f"Simulated error: {error_type}")
        
        if error_type == "Timeout":
            # Hacer que el request tarde más que el timeout del cliente
            delay =  30  # 30 segundos por defecto
            time.sleep(delay)  # Esto hará que el cliente haga timeout
            
        elif error_type == "ConnectionError":
            # Retornar 503 y cerrar conexión
            raise HTTPException(
                status_code=503,
                detail="Service Unavailable - Simulated Connection Error"
            )
            
        elif error_type == "HTTPError":
            # Retornar error HTTP que el cliente manejará como error
            status_code = 500
            raise HTTPException(
                status_code=status_code,
                detail=f"Simulated HTTP Error {status_code}"
            )
            
        elif error_type == "SSLError":
            # Retornar respuesta que podría causar SSL error en el cliente
            raise HTTPException(
                status_code=500,
                detail="Simulated SSL Error - SSL handshake failed"
            )

        if error_type == "ConnectTimeout":
            raise ConnectTimeout(error_message)
        elif error_type == "SSLError":
            raise SSLError(error_message)
        elif error_type == "Timeout":
            raise Timeout(error_message)
        elif error_type == "ConnectionError":
            raise ConnectionError(error_message)
        else:
            raise ConnectionError(error_message)
    
    @staticmethod
    def create_or_update_simulation(
        db: Session,
        error_type: str,
        is_active: bool,
        consecutive_errors: int,
        endpoint_filter: Optional[str] = None
    ) -> ErrorSimulation:
        """Crea o actualiza una simulación de error"""
        if error_type not in ErrorSimulationService.VALID_ERROR_TYPES:
            raise ValueError(f"Error type must be one of: {ErrorSimulationService.VALID_ERROR_TYPES}")
        
        # Buscar existente
        simulation = db.query(ErrorSimulation).filter(
            ErrorSimulation.error_type == error_type,
            ErrorSimulation.endpoint_filter == endpoint_filter
        ).first()
        
        if simulation:
            # Actualizar existente
            simulation.is_active = is_active
            simulation.consecutive_errors = consecutive_errors
            simulation.current_error_count = 0  # Resetear contador
            simulation.updated_at = datetime.utcnow()
        else:
            # Crear nueva
            simulation = ErrorSimulation(
                error_type=error_type,
                is_active=is_active,
                consecutive_errors=consecutive_errors,
                current_error_count=0,
                endpoint_filter=endpoint_filter
            )
            db.add(simulation)
        
        db.commit()
        db.refresh(simulation)
        return simulation
    
    @staticmethod
    def get_all_simulations(db: Session):
        """Obtiene todas las simulaciones"""
        return db.query(ErrorSimulation).order_by(ErrorSimulation.created_at.desc()).all()
    
    @staticmethod
    def delete_simulation(db: Session, simulation_id: int) -> bool:
        """Elimina una simulación"""
        simulation = db.query(ErrorSimulation).filter(ErrorSimulation.id == simulation_id).first()
        if simulation:
            db.delete(simulation)
            db.commit()
            return True
        return False
    
    @staticmethod
    def reset_all_simulations(db: Session):
        """Resetea todas las simulaciones"""
        db.query(ErrorSimulation).update({
            ErrorSimulation.is_active: False,
            ErrorSimulation.current_error_count: 0
        })
        db.commit()