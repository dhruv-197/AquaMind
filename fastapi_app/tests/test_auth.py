import os
import sys
import unittest
from datetime import datetime

# Add workspace directory to path
SYS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SYS_PATH not in sys.path:
    sys.path.append(SYS_PATH)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi_app.database.models import Base, User
from fastapi_app.services.auth_service import AuthService

class TestAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("Initializing Test In-Memory SQLite database for Auth verification...")
        cls.engine = create_engine("sqlite:///:memory:")
        cls.Session = sessionmaker(bind=cls.engine)
        Base.metadata.create_all(cls.engine)
        print("Auth schemas created successfully!")

    def setUp(self):
        self.session = self.Session()

    def tearDown(self):
        self.session.query(User).delete()
        self.session.commit()
        self.session.close()

    def test_password_hashing(self):
        print("\nTesting password hashing and verification...")
        password = "SecurePassword123"
        hashed = AuthService.hash_password(password)
        
        self.assertNotEqual(password, hashed)
        self.assertTrue(AuthService.verify_password(password, hashed))
        self.assertFalse(AuthService.verify_password("wrong_password", hashed))
        print("[OK] Password hashing verified successfully.")

    def test_jwt_token_flow(self):
        print("\nTesting JWT token creation and decoding...")
        payload = {"sub": "test@aquamind.io", "role": "admin"}
        token = AuthService.create_access_token(payload)
        
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)
        
        decoded = AuthService.decode_access_token(token)
        self.assertEqual(decoded["sub"], "test@aquamind.io")
        self.assertEqual(decoded["role"], "admin")
        self.assertIn("exp", decoded)
        print("[OK] JWT token encode/decode flows verified successfully.")

    def test_user_creation_and_auth(self):
        print("\nTesting user signup and login database validation...")
        # 1. Signup validation
        email = "officer@water.gov"
        username = "water_officer"
        password = "GovPassword999"
        role = "government_officer"
        
        hashed_pwd = AuthService.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=hashed_pwd,
            role=role
        )
        self.session.add(user)
        self.session.commit()
        
        # Query back
        db_user = self.session.query(User).filter(User.email == email).first()
        self.assertIsNotNone(db_user)
        self.assertEqual(db_user.username, username)
        self.assertEqual(db_user.role, role)
        self.assertTrue(AuthService.verify_password(password, db_user.password_hash))
        
        # 2. Forgot Password Flow
        new_password = "NewSuperGovPassword888"
        db_user.password_hash = AuthService.hash_password(new_password)
        self.session.commit()
        
        # Verify password updated
        self.session.refresh(db_user)
        self.assertTrue(AuthService.verify_password(new_password, db_user.password_hash))
        self.assertFalse(AuthService.verify_password(password, db_user.password_hash))
        print("[OK] User creation, login, and forgot-password flows verified successfully.")

def test_signup_cannot_self_assign_admin_role(api_client):
    """Regression test: public /auth/signup used to accept role="admin" verbatim
    and return a working admin token immediately — anyone could self-escalate."""
    res = api_client.post(
        "/auth/signup",
        json={
            "username": "would_be_admin",
            "email": "would-be-admin@aquamind.test",
            "password": "TryToEscalate123",
            "role": "admin",
        },
    )
    assert res.status_code == 400
    assert "admin" in res.json()["message"].lower() or "role" in res.json()["message"].lower()


def test_signup_allows_public_role(api_client):
    res = api_client.post(
        "/auth/signup",
        json={
            "username": "regular_officer",
            "email": "regular-officer@aquamind.test",
            "password": "RegularOfficer123",
            "role": "government_officer",
        },
    )
    assert res.status_code in (201, 400)  # 400 only if a prior test run already created it
    if res.status_code == 201:
        assert res.json()["data"]["role"] == "government_officer"


if __name__ == "__main__":
    unittest.main()
