"""Local OAuth consent, token grants and CRM identity reads for Holbran."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from html import escape
from secrets import compare_digest, token_urlsafe
from time import monotonic
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import OAUTH_API_DOMAIN, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_REDIRECT_URI
from app.database import get_db
from app.models import ApiLog, ApiToken, OAuthAuthorizationCode
from app.services.logger import ApiLogger
from app.services.error_simulation import ErrorSimulationService

router = APIRouter()
SCOPES = {"ZohoCRM.org.READ", "ZohoCRM.users.READ"}
SENSITIVE = {"authorization", "cookie", "client_secret", "code", "state", "access_token", "refresh_token"}


def _redact(values):
    return {key: "[REDACTED]" if key.lower() in SENSITIVE else value for key, value in values.items()}


async def _record(request, db, payload, status, started_at, form=None):
    """Retain useful HTTP evidence without recording OAuth credentials."""
    request_id = ApiLogger.generate_request_id()
    endpoint = request.url.path
    headers = _redact(dict(request.headers))
    body = _redact(form or {})
    query = _redact(dict(request.query_params))
    response_body = _redact(payload)
    url = str(request.url.replace(query=""))
    duration = int((monotonic() - started_at) * 1000)
    success = status < 400 and "error" not in payload
    response_headers = {"Content-Type": "application/json"}
    await ApiLogger.log_request(request_id, endpoint, request.method, url, headers, body, query)
    await ApiLogger.log_response(
        request_id,
        endpoint,
        status,
        response_headers,
        response_body,
        duration,
        success=success,
        error_message=payload.get("error"),
    )
    db.add(
        ApiLog(
            request_id=request_id,
            endpoint=endpoint,
            method=request.method,
            url=url,
            headers=headers,
            body=body,
            query_params=query,
            response_status_code=status,
            response_headers=response_headers,
            response_body=response_body,
            response_time_ms=duration,
            success=success,
            error_message=payload.get("error"),
        )
    )
    db.commit()


async def _check_simulated_error(request, db, endpoint):
    simulation = ErrorSimulationService.get_active_simulation(db, endpoint)
    if simulation and ErrorSimulationService.should_raise_error(simulation):
        ErrorSimulationService.increment_error_count(db, simulation)
        await _record(request, db, {"error": f"Simulated {simulation.error_type}"}, 500, monotonic())
        ErrorSimulationService.raise_simulated_error(simulation.error_type, str(request.url))


async def _json(request, db, payload, started_at, status=200, form=None):
    await _record(request, db, payload, status, started_at, form)
    return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})


def _authorization_error(params):
    if params.get("client_id") != OAUTH_CLIENT_ID:
        return "invalid_client"
    if params.get("redirect_uri") != OAUTH_REDIRECT_URI:
        return "invalid_redirect_uri"
    if params.get("response_type") != "code":
        return "unsupported_response_type"
    if set(params.get("scope", "").split(",")) != SCOPES:
        return "invalid_scope"
    if not params.get("state"):
        return "invalid_state"
    return ""


@router.get("/oauth/v2/auth")
async def authorization(request: Request, db: Session = Depends(get_db)):
    started_at = monotonic()
    params = dict(request.query_params)
    error = _authorization_error(params)
    if error:
        return await _json(request, db, {"error": error}, started_at, status=400)
    fields = "".join(
        f'<input type="hidden" name="{escape(key, quote=True)}" value="{escape(value, quote=True)}">'
        for key, value in params.items()
    )
    await _record(request, db, {"consent": "pending"}, 200, started_at)
    return HTMLResponse(
        '<!doctype html><html lang="en"><title>Zoho Mock consent</title>'
        "<body><h1>Authorize Holbran in Zoho Mock</h1>"
        "<p>Local test account: Mock User &lt;mock.user@example.com&gt;.</p>"
        "<p>Allow read access to the CRM organization and current user.</p>"
        f'<form method="post" action="/oauth/v2/auth">{fields}'
        '<button name="decision" value="approve">Authorize</button> '
        '<button name="decision" value="deny">Cancel</button></form></body></html>',
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/oauth/v2/auth")
async def consent(request: Request, db: Session = Depends(get_db)):
    started_at = monotonic()
    params = dict(await request.form())
    error = _authorization_error(params)
    if error:
        return await _json(request, db, {"error": error}, started_at, status=400, form=params)
    result = {"state": params["state"], "accounts-server": OAUTH_API_DOMAIN}
    if params.get("decision") == "approve":
        code = token_urlsafe(32)
        db.add(
            OAuthAuthorizationCode(
                code_hash=sha256(code.encode()).hexdigest(),
                client_id=OAUTH_CLIENT_ID,
                redirect_uri=OAUTH_REDIRECT_URI,
                expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5),
            )
        )
        db.commit()
        result["code"] = code
    else:
        result["error"] = "access_denied"
    await _record(request, db, {"decision": params.get("decision", "deny")}, 303, started_at, params)
    return RedirectResponse(
        f"{OAUTH_REDIRECT_URI}?{urlencode(result)}",
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post("/oauth/v2/token")
async def token(request: Request, db: Session = Depends(get_db)):
    started_at = monotonic()
    form = dict(await request.form())
    if form.get("client_id") != OAUTH_CLIENT_ID:
        return await _json(request, db, {"error": "invalid_client"}, started_at, form=form)
    if not compare_digest(str(form.get("client_secret", "")).encode(), OAUTH_CLIENT_SECRET.encode()):
        return await _json(request, db, {"error": "invalid_client_secret"}, started_at, form=form)
    await _check_simulated_error(request, db, "/token")
    now = datetime.now(UTC).replace(tzinfo=None)
    grant = form.get("grant_type")
    if grant == "authorization_code":
        if form.get("redirect_uri") != OAUTH_REDIRECT_URI:
            return await _json(request, db, {"error": "invalid_redirect_uri"}, started_at, form=form)
        claimed = (
            db.query(OAuthAuthorizationCode)
            .filter(
                OAuthAuthorizationCode.code_hash == sha256(str(form.get("code", "")).encode()).hexdigest(),
                OAuthAuthorizationCode.client_id == OAUTH_CLIENT_ID,
                OAuthAuthorizationCode.redirect_uri == OAUTH_REDIRECT_URI,
                OAuthAuthorizationCode.consumed_at.is_(None),
                OAuthAuthorizationCode.expires_at > now,
            )
            .update({"consumed_at": now}, synchronize_session=False)
        )
        if claimed != 1:
            db.rollback()
            return await _json(request, db, {"error": "invalid_code"}, started_at, form=form)
        credential = ApiToken(
            access_token=token_urlsafe(32),
            refresh_token=token_urlsafe(32),
            token_type="Zoho-oauthtoken",
            expires_in=3600,
            expires_at=now + timedelta(hours=1),
            is_active=True,
        )
        db.add(credential)
    elif grant == "refresh_token":
        refresh = str(form.get("refresh_token", ""))
        credential = (
            db.query(ApiToken)
            .filter(
                ApiToken.refresh_token == refresh,
                ApiToken.is_active.is_(True),
            )
            .first()
            if refresh
            else None
        )
        if credential is None:
            return await _json(request, db, {"error": "invalid_code"}, started_at, form=form)
        credential.access_token = token_urlsafe(32)
        credential.expires_at = now + timedelta(hours=1)
    else:
        return await _json(request, db, {"error": "unsupported_grant_type"}, started_at, form=form)
    db.commit()
    payload = {
        "access_token": credential.access_token,
        "api_domain": OAUTH_API_DOMAIN,
        "expires_in": credential.expires_in,
        "token_type": credential.token_type,
    }
    if grant == "authorization_code":
        payload["refresh_token"] = credential.refresh_token
    return await _json(request, db, payload, started_at, form=form)


def _authorized(request, db):
    prefix = "Zoho-oauthtoken "
    header = request.headers.get("authorization", "")
    if not header.startswith(prefix) or not header[len(prefix) :]:
        return False
    return (
        db.query(ApiToken)
        .filter(
            ApiToken.access_token == header[len(prefix) :],
            ApiToken.is_active.is_(True),
            ApiToken.expires_at > datetime.now(UTC).replace(tzinfo=None),
        )
        .first()
        is not None
    )


@router.get("/crm/v8/users")
async def users(request: Request, db: Session = Depends(get_db)):
    started_at = monotonic()
    if not _authorized(request, db):
        return await _json(request, db, {"error": "INVALID_TOKEN"}, started_at, status=401)
    if request.query_params.get("type") != "CurrentUser":
        return await _json(request, db, {"error": "INVALID_DATA"}, started_at, status=400)
    await _check_simulated_error(request, db, "/crm/v8/users")
    return await _json(
        request,
        db,
        {
            "users": [
                {
                    "id": "7000000000001",
                    "full_name": "Mock User",
                    "email": "mock.user@example.com",
                }
            ]
        },
        started_at,
    )


@router.get("/crm/v8/org")
async def organization(request: Request, db: Session = Depends(get_db)):
    started_at = monotonic()
    if not _authorized(request, db):
        return await _json(request, db, {"error": "INVALID_TOKEN"}, started_at, status=401)
    await _check_simulated_error(request, db, "/crm/v8/org")
    return await _json(
        request,
        db,
        {
            "org": [
                {
                    "id": "7000001",
                    "zgid": "7000001",
                    "company_name": "Zoho Mock Organization",
                }
            ]
        },
        started_at,
    )
