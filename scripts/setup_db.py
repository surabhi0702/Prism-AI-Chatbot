#!/usr/bin/env python3
"""PRISM — Database Setup & Seed Script
Run: python scripts/setup_db.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.models import create_tables, AsyncSession, User, SystemAlert
from backend.middleware.auth import hash_password
import uuid
from datetime import datetime


DEMO_USERS = [
    {"email": "admin@prism.ai",   "name": "PRISM Admin",       "password": "admin123",   "role": "admin",   "subscription": "enterprise", "diseases": ["CA","DM","CV","MH","RS"]},
    {"email": "patient@prism.ai", "name": "Maria González",    "password": "demo123",    "role": "patient", "subscription": "premium",    "diseases": ["DM","CV","MH"]},
    {"email": "demo@prism.ai",    "name": "Dr. Ravi Kumar",    "password": "demo123",    "role": "patient", "subscription": "basic",      "diseases": ["CA","DM"]},
]

DEMO_ALERTS = [
    {"level": "warning", "title": "Pre-RAG Gate Warning", "message": "3 documents scored below SILVER threshold. Review required.", "component": "pre_rag"},
    {"level": "info",    "title": "Crawl Complete",       "message": "PubMed crawl for DM1 completed: 12 articles indexed.",     "component": "crawler"},
]


async def main():
    print("[SETUP] PRISM Database Setup")
    print("=" * 40)

    print("[INFO] Creating database tables...")
    await create_tables()
    print("[SUCCESS] Tables created")

    print("[INFO] Seeding demo users...")
    async with AsyncSession() as session:
        for u in DEMO_USERS:
            from sqlalchemy import select
            res = await session.execute(select(User).where(User.email == u["email"]))
            existing = res.scalar_one_or_none()
            if not existing:
                user = User(
                    id=str(uuid.uuid4()), email=u["email"], name=u["name"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"], subscription=u["subscription"],
                    subscribed_diseases=u["diseases"],
                )
                session.add(user)
                print(f"  [OK] {u['email']} ({u['role']})")
            else:
                if u["role"] == "admin" and existing.role != "admin":
                    existing.role = "admin"
                    print(f"  [FIX] {u['email']} role corrected to admin")
                else:
                    print(f"  [SKIP] {u['email']} already exists")

        for a in DEMO_ALERTS:
            session.add(SystemAlert(id=str(uuid.uuid4()), **a))

        await session.commit()

    print("\n[SUCCESS] Database setup complete!")
    print("\nDemo accounts:")
    print("  Admin:   admin@prism.ai    / admin123")
    print("  Patient: patient@prism.ai  / demo123")
    print("  Demo:    demo@prism.ai     / demo123")


if __name__ == "__main__":
    asyncio.run(main())
