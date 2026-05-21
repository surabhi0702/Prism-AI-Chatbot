
import asyncio
import uuid
from backend.database.models import AsyncSession, AgentQuestion, create_tables
from backend.config.agent_registry import ALL_AGENTS
from sqlalchemy import select

# Additional backup questions for each domain
BACKUP_QUESTIONS = {
    "CA": [
        "How do I manage chemotherapy side effects at home?",
        "What are the signs that my cancer treatment is working?",
        "How do I talk to my employer about my cancer diagnosis?",
        "Are there specific exercises safe for cancer patients?",
        "What clinical trials are currently open for my cancer type?"
    ],
    "DM": [
        "How to manage blood sugar during illness (sick day rules)?",
        "What are the best snacks for preventing nighttime hypoglycemia?",
        "How does stress affect my blood glucose levels?",
        "Travel checklist for insulin-dependent patients.",
        "Understanding the difference between Type 1 and Type 2 diabetes."
    ],
    "CV": [
        "Recognizing symptoms of a heart attack vs panic attack.",
        "Salt reduction guide for managing hypertension.",
        "Importance of medication adherence in heart failure.",
        "Traveling with a pacemaker or ICD: what to know.",
        "How to start a heart-healthy exercise routine safely."
    ],
    "MH": [
        "Building a sleep-friendly bedroom environment.",
        "Techniques for managing workplace anxiety.",
        "Digital detox plan for better mental health.",
        "Journaling for emotional regulation: where to start?",
        "Understanding the side effects of common antidepressants."
    ],
    "RS": [
        "Using a peak flow meter to monitor my asthma.",
        "Breathing techniques for anxiety-related breathlessness.",
        "Protecting lungs during high pollution or wildfire days.",
        "Nutrition tips for patients with COPD.",
        "Travel with oxygen: what you need to prepare."
    ]
}

async def seed_questions():
    print("Starting seeding of agent questions...")
    await create_tables()
    
    async with AsyncSession() as session:
        # Check if we already have questions
        res = await session.execute(select(AgentQuestion).limit(1))
        if res.scalar_one_or_none():
            print("Questions already exist in database. Skipping seeding.")
            return

        for agent_id, agent in ALL_AGENTS.items():
            if agent.role != "primary":
                continue
                
            domain_code = agent.disease_code
            
            # Initial questions (active)
            for q_text in agent.top5_questions:
                q = AgentQuestion(
                    agent_id=agent_id,
                    text=q_text,
                    is_active=True
                )
                session.add(q)
            
            # Backup questions (inactive)
            backups = BACKUP_QUESTIONS.get(domain_code, [])
            for q_text in backups:
                q = AgentQuestion(
                    agent_id=agent_id,
                    text=q_text,
                    is_active=False
                )
                session.add(q)
                
        await session.commit()
        print("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_questions())
