from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import zoho, admin
from app.config import BASE_DIR

# # Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Zoho CRM Mock API",
    description="Mock de la API de Zoho CRM con persistencia SQLite y logging completo",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(zoho.router, prefix="", tags=["Zoho CRM"])
app.include_router(admin.router, prefix="", tags=["Admin"])


@app.get("/")
async def root():
    return {
        "message": "Zoho CRM Mock API",
        "version": "1.0.0",
        "endpoints": {
            "token": "POST /token",
            "contacts": "POST /Contacts, PUT /Contacts",
            "deals": "POST /Deals, PUT /Deals",
            "leads": "POST /Leads, PUT /Leads",  # Nuevo
            "admin": "GET /admin/logs, /admin/contacts, /admin/deals, /admin/leads, /admin/stats"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def run():
    """Función para ejecutar con uv"""
    import uvicorn
    uvicorn.run(
        app,#"app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    run()