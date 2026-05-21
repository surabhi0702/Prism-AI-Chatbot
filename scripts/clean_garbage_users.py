#!/usr/bin/env python3
"""PRISM — Database Cleanup Script
Removes duplicate/garbage test accounts and fixes the Maria González character encoding.
Run: python scripts/clean_garbage_users.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.models import AsyncSession, User, Conversation, Message, PatientFeedback, ImageUpload, VideoGeneration
from sqlalchemy import select, delete

# The set of emails we want to preserve in the database
PRESERVED_EMAILS = {
    "admin@prism.ai",
    "patient@prism.ai",
    "demo@prism.ai",
    "sumit@prism.ai",
    "maria@prism.ai",
    "test_v2@example.com"
}

async def clean_database():
    print("[CLEANUP] Starting database pruning...")
    async with AsyncSession() as session:
        # 1. Fetch all users
        res = await session.execute(select(User))
        all_users = res.scalars().all()
        
        users_to_delete = []
        for u in all_users:
            email_lower = u.email.lower()
            
            # Identify garbage users
            if email_lower not in PRESERVED_EMAILS:
                users_to_delete.append(u)
            else:
                # Fix the encoding issue for Maria González if detected
                if email_lower == "patient@prism.ai" and ("Gonz" in u.name or "" in u.name):
                    print(f"  [FIX] Fixing name for {u.email}: '{u.name}' -> 'Maria González'")
                    u.name = "Maria González"
        
        print(f"  [INFO] Found {len(users_to_delete)} users to delete out of {len(all_users)} total users.")
        
        # 2. Delete associated tables first to prevent Foreign Key constraints
        for u in users_to_delete:
            print(f"  [DEL] Processing garbage user: {u.name} ({u.email})")
            
            # A. Fetch all user conversations
            res_convs = await session.execute(select(Conversation).where(Conversation.user_id == u.id))
            convs = res_convs.scalars().all()
            conv_ids = [c.id for c in convs]
            
            if conv_ids:
                # B. Delete messages in those conversations
                await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
                print(f"    - Deleted messages for {len(conv_ids)} conversations")
                
                # C. Delete conversations
                await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
                print(f"    - Deleted {len(conv_ids)} conversations")
            
            # D. Delete patient feedback
            await session.execute(delete(PatientFeedback).where(PatientFeedback.user_id == u.id))
            
            # E. Delete image uploads
            await session.execute(delete(ImageUpload).where(ImageUpload.user_id == u.id))
            
            # F. Delete video generations
            await session.execute(delete(VideoGeneration).where(VideoGeneration.user_id == u.id))
            
            # G. Delete user
            await session.delete(u)
            print(f"    - User record deleted successfully.")
            
        await session.commit()
        print("[SUCCESS] Database cleanup completed!")

if __name__ == "__main__":
    asyncio.run(clean_database())
