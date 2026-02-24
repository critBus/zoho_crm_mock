## 🚀 Instrucciones de Uso

### 1. Instalar dependencias con uv

```bash
# Instalar uv si no lo tienes
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navegar al directorio del proyecto
cd zoho_mock

# Instalar dependencias
uv pip install -r requirements.txt

# O usar pyproject.toml
uv pip install -e .
```

### 2. Ejecutar el servidor

```bash
# Opción 1: Con uvicorn directamente
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Opción 2: Con el comando definido en pyproject.toml
uv run zoho-mock

# Opción 3: Con Python directamente
python -m app.main
```

### 3. Configurar tu proyecto para usar el mock

En tu proyecto principal, modifica la configuración de Zoho API para apuntar al mock:

```python
# settings.py o configuración equivalente
ZOHO_API_BASE_URL = "http://localhost:8000"
ZOHO_LOGIN_URL = "http://localhost:8000"
```

### 4. Acceder al panel de administración

- **URL:** `http://localhost:8000/admin/login`
- **Usuario:** `admin`
- **Contraseña:** `admin123`

### 5. Endpoints disponibles

| Método | Endpoint          | Descripción          |
| ------ | ----------------- | -------------------- |
| POST   | `/token`          | Obtener access token |
| POST   | `/Contacts`       | Crear contacto       |
| PUT    | `/Contacts`       | Actualizar contacto  |
| POST   | `/Deals`          | Crear deal           |
| PUT    | `/Deals`          | Actualizar deal      |
| GET    | `/admin/logs`     | Ver logs de API      |
| GET    | `/admin/contacts` | Ver contactos        |
| GET    | `/admin/deals`    | Ver deals            |
| GET    | `/admin/stats`    | Ver estadísticas     |

## 📊 Características Principales

### ✅ Persistencia de Datos

- **SQLite** para almacenar todos los registros
- **Zoho IDs** se conservan entre reinicios
- **Contactos y Deals** mantienen su estado

### ✅ Logging Completo

- **Base de datos:** Tabla `api_logs` con toda la información
- **Archivos TXT:** Separados por request/response con timestamp y endpoint
- **Información registrada:**
  - Headers de entrada/salida
  - Body de entrada/salida
  - URLs completas
  - Códigos de respuesta
  - Métodos HTTP
  - Tiempos de respuesta
  - Zoho IDs relacionados

### ✅ Panel de Administración

- **Filtros avanzados** para logs, contactos y deals
- **Paginación** para grandes volúmenes de datos
- **Estadísticas** en tiempo real
- **Vista detallada** de cada registro

### ✅ Compatibilidad

- **Mismos endpoints** que Zoho CRM real
- **Mismos formatos** de request/response
- **IDs de Zoho** generados consistentemente

## 📁 Estructura de Logs TXT

### Requests (`logs/requests/`)

```
20240115_143022__Contacts_req_abc123_request.txt
20240115_143025__Deals_req_def456_request.txt
```

### Responses (`logs/responses/`)

```
20240115_143022__Contacts_req_abc123_response.txt
20240115_143025__Deals_req_def456_response.txt
```

### Formato de archivo

```json
{
  "request_id": "req_abc123",
  "timestamp": "2024-01-15T14:30:22.123456",
  "endpoint": "/Contacts",
  "method": "POST",
  "url": "http://localhost:8000/Contacts",
  "headers": {...},
  "body": {...},
  "query_params": {...}
}
```

## 🔧 Personalización

### Cambiar credenciales de admin

Edita `app/config.py`:

```python
ADMIN_USERNAME = "tu_usuario"
ADMIN_PASSWORD = "tu_contraseña_segura"
```

### Cambiar puerto

```bash
uv run uvicorn app.main:app --reload --port 9000
```

### Limpiar base de datos

```bash
rm data/zoho_mock.db
# Las tablas se recrean automáticamente al iniciar
```

Este mock te permitirá desarrollar y probar tu integración con Zoho CRM sin depender del servicio real, manteniendo toda la trazabilidad necesaria para debugging y auditoría