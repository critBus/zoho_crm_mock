"""OAuth compatibility checks with an isolated SQLite database and log directory."""

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import OAUTH_REDIRECT_URI
from app.database import Base, get_db
from app.models import ApiLog, ApiToken, OAuthAuthorizationCode
from app.routes import oauth


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)
        app = FastAPI()
        app.include_router(oauth.router)

        def database():
            with self.session() as db:
                yield db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.directory = tempfile.TemporaryDirectory()
        log_path = Path(self.directory.name)
        self.patches = [
            patch("app.services.logger.REQUESTS_LOG_DIR", log_path),
            patch("app.services.logger.RESPONSES_LOG_DIR", log_path),
        ]
        for item in self.patches:
            item.start()
        self.params = {
            "client_id": "secret",
            "redirect_uri": OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "ZohoCRM.org.READ,ZohoCRM.users.READ",
            "state": "test-state",
            "access_type": "offline",
        }

    def tearDown(self):
        self.client.close()
        for item in self.patches:
            item.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def grant(self):
        page = self.client.get("/oauth/v2/auth", params=self.params)
        self.assertEqual(page.status_code, 200)
        response = self.client.post(
            "/oauth/v2/auth", data={**self.params, "decision": "approve"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query["state"], ["test-state"])
        return query["code"][0]

    def exchange(self, code, **overrides):
        return self.client.post(
            "/oauth/v2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "secret",
                "client_secret": "secret",
                "redirect_uri": OAUTH_REDIRECT_URI,
                "code": code,
                **overrides,
            },
        ).json()

    def test_authorization_identity_and_refresh(self):
        code = self.grant()
        payload = self.exchange(code)
        self.assertIn("refresh_token", payload)
        self.assertEqual(payload["api_domain"], "http://localhost:7002")
        headers = {"Authorization": "Zoho-oauthtoken " + payload["access_token"]}
        self.assertEqual(self.client.get("/crm/v8/org", headers=headers).json()["org"][0]["zgid"], "7000001")
        self.assertEqual(
            self.client.get("/crm/v8/users?type=CurrentUser", headers=headers).json()["users"][0]["email"],
            "mock.user@example.com",
        )
        refreshed = self.client.post(
            "/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": "secret",
                "client_secret": "secret",
                "refresh_token": payload["refresh_token"],
            },
        ).json()
        self.assertIn("access_token", refreshed)
        new_headers = {"Authorization": "Zoho-oauthtoken " + refreshed["access_token"]}
        self.assertEqual(self.client.get("/crm/v8/org", headers=new_headers).status_code, 200)
        self.assertEqual(self.client.get("/crm/v8/org", headers=headers).status_code, 401)
        with self.session() as db:
            evidence = "\n".join(json.dumps(row.__dict__, default=str) for row in db.query(ApiLog).all())
        for value in (code, payload["access_token"], payload["refresh_token"], refreshed["access_token"]):
            self.assertNotIn(value, evidence)
            for path in Path(self.directory.name).iterdir():
                self.assertNotIn(value, path.read_text())

    def test_credentials_and_single_use_code(self):
        code = self.grant()
        self.assertEqual(self.exchange(code, client_id="wrong")["error"], "invalid_client")
        self.assertEqual(self.exchange(code, client_secret="wrong")["error"], "invalid_client_secret")
        self.assertEqual(self.exchange(code, redirect_uri="http://evil.test/")["error"], "invalid_redirect_uri")
        self.assertIn("access_token", self.exchange(code))
        self.assertEqual(self.exchange(code)["error"], "invalid_code")

    def test_expired_code_and_missing_access(self):
        code = self.grant()
        with self.session() as db:
            db.query(OAuthAuthorizationCode).update(
                {"expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)}
            )
            db.commit()
        self.assertEqual(self.exchange(code)["error"], "invalid_code")
        self.assertEqual(self.client.get("/crm/v8/org").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/crm/v8/users?type=CurrentUser", headers={"Authorization": "Zoho-oauthtoken invalid"}
            ).status_code,
            401,
        )

    def test_consent_rejects_unknown_client_redirect_and_scope(self):
        for override in (
            {"client_id": "wrong"},
            {"redirect_uri": "http://evil.test/"},
            {"scope": "ZohoCRM.modules.ALL"},
        ):
            response = self.client.get("/oauth/v2/auth", params={**self.params, **override})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("location", response.headers)
        denied = self.client.post("/oauth/v2/auth", data={**self.params, "decision": "deny"}, follow_redirects=False)
        self.assertEqual(parse_qs(urlsplit(denied.headers["location"]).query)["error"], ["access_denied"])
        with self.session() as db:
            self.assertEqual(db.query(OAuthAuthorizationCode).count(), 0)

    def test_refresh_rejects_invalid_or_revoked_grants_and_expired_access(self):
        payload = self.exchange(self.grant())
        request = {
            "grant_type": "refresh_token",
            "client_id": "secret",
            "client_secret": "secret",
            "refresh_token": "wrong",
        }
        self.assertEqual(self.client.post("/oauth/v2/token", data=request).json()["error"], "invalid_code")
        with self.session() as db:
            db.query(ApiToken).update({"expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)})
            db.commit()
        headers = {"Authorization": "Zoho-oauthtoken " + payload["access_token"]}
        self.assertEqual(self.client.get("/crm/v8/org", headers=headers).status_code, 401)
        request["refresh_token"] = payload["refresh_token"]
        self.assertIn("access_token", self.client.post("/oauth/v2/token", data=request).json())
        with self.session() as db:
            db.query(ApiToken).update({"is_active": False})
            db.commit()
        self.assertEqual(self.client.post("/oauth/v2/token", data=request).json()["error"], "invalid_code")


if __name__ == "__main__":
    unittest.main()
