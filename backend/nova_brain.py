"""
NOVA Brain - Neural Oriented Virtual Assistant
Full AI teacher engine: contextual awareness, conversational teaching,
proactive insights, and real-time student analysis.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import json
import logging
import os

from models import User, UserXP, StudentProgress, StudentInsight, StudySession, Lesson, Course

logger = logging.getLogger(__name__)


class NovaBrain:
    """NOVA — the AI teacher that knows your learning journey."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # ─── Status / HUD ────────────────────────────────────────────

    @classmethod
    def analyze_student(cls, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Static entry point called by the API route.
        Creates an instance and returns the full status payload.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"mood": "neutral", "message": "Welcome to AI Virtual Classroom!", "suggestions": []}
        brain = cls(db, user)
        return brain.get_status()

    def get_status(self) -> Dict[str, Any]:
        """
        Generates the current status for NOVA.
        Analyzes recent activity to determine mood and message.
        """
        xp_record = self.db.query(UserXP).filter(UserXP.user_id == self.user.id).first()

        # Default state
        mood = "neutral"
        message = f"Hello {self.user.username}! I'm NOVA, your AI learning companion. How can I help you today?"

        if not xp_record:
            return {"mood": mood, "message": message, "suggestions": self._generate_suggestions()}

        # Analyze streak and activity
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_active_today = xp_record.last_active_date == today

        if xp_record.streak_days > 0 and not is_active_today:
            mood = "encouraging"
            message = f"You're on a {xp_record.streak_days}-day streak! Let's keep it going today, {self.user.username}."
        elif is_active_today and xp_record.streak_days > 3:
            mood = "happy"
            message = f"Amazing {xp_record.streak_days}-day streak! You're in the zone. What shall we tackle next?"
        elif xp_record.level > 1:
            mood = "thinking"
            message = f"Level {xp_record.level} already! Let's push for something more challenging today."

        # Check for incomplete lessons
        recent_progress = self.db.query(StudentProgress).filter(
            StudentProgress.user_id == self.user.id,
            StudentProgress.status == "in_progress"
        ).order_by(StudentProgress.started_at.desc()).first()

        if recent_progress:
            lesson = self.db.query(Lesson).filter(Lesson.id == recent_progress.lesson_id).first()
            if lesson:
                mood = "suggestive"
                message = f"You were studying '{lesson.title}'. Want to continue where you left off?"

        suggestions = self._generate_suggestions()

        return {
            "mood": mood,
            "message": message,
            "suggestions": suggestions,
            "stats": {
                "xp": xp_record.xp_total if xp_record else 0,
                "level": xp_record.level if xp_record else 1,
                "streak": xp_record.streak_days if xp_record else 0,
            }
        }

    # ─── Conversational AI ────────────────────────────────────────

    @classmethod
    def ask(cls, db: Session, user_id: int, question: str, screen_context: str = "") -> Dict[str, Any]:
        """
        Handle a conversational question from the student.
        Uses GPT with full student context + current screen awareness.
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"response": "I couldn't find your profile. Please try logging in again.", "mood": "confused"}

        brain = cls(db, user)
        return brain._ask_gpt(question, screen_context)

    def _ask_gpt(self, question: str, screen_context: str = "") -> Dict[str, Any]:
        """Send a context-aware question to GPT and return the response."""
        try:
            from openai import OpenAI
            from config import OPENAI_API_KEY, OPENAI_MODEL

            if not OPENAI_API_KEY:
                return {
                    "response": "I'm currently in offline mode. My AI capabilities need an API key to be configured. But I can still help you navigate — try asking about courses or your progress!",
                    "mood": "neutral"
                }

            client = OpenAI(api_key=OPENAI_API_KEY)

            # Build student context
            xp = self.db.query(UserXP).filter(UserXP.user_id == self.user.id).first()
            progress_records = self.db.query(StudentProgress).filter(
                StudentProgress.user_id == self.user.id
            ).order_by(StudentProgress.started_at.desc()).limit(10).all()

            completed_lessons = []
            for p in progress_records:
                lesson = self.db.query(Lesson).filter(Lesson.id == p.lesson_id).first()
                if lesson:
                    completed_lessons.append(f"- {lesson.title} ({p.status}, understanding: {p.understanding_level}%)")

            student_context = f"""Student Profile:
- Name: {self.user.full_name or self.user.username}
- Level: {xp.level if xp else 1}
- XP: {xp.xp_total if xp else 0}
- Streak: {xp.streak_days if xp else 0} days
- Recent Lessons:
{chr(10).join(completed_lessons) if completed_lessons else '  No lessons started yet.'}
"""

            screen_info = f"\nCurrent Screen Context: {screen_context}" if screen_context else ""

            system_prompt = f"""You are NOVA (Neural Oriented Virtual Assistant), an advanced AI teacher in a virtual classroom. You are warm, encouraging, and knowledgeable. You adapt your teaching style to each student.

{student_context}{screen_info}

Guidelines:
- Be concise but helpful (2-4 sentences for simple questions, more for explanations)
- Use emoji sparingly for warmth (1-2 per response max)
- If the student asks about a topic, teach it clearly with examples
- If they seem confused, break concepts down simply
- Reference their progress to personalize responses
- If they ask about their progress, give specific stats
- Be encouraging and celebrate their achievements
- If asked about something outside education, gently redirect to learning topics"""

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                max_tokens=500,
                temperature=0.7,
            )

            answer = response.choices[0].message.content.strip()
            mood = self._detect_mood(question, answer)

            return {"response": answer, "mood": mood}

        except Exception as e:
            logger.error(f"NOVA GPT error: {e}")
            return {
                "response": f"I had a momentary glitch processing that. Could you rephrase your question? 🤔",
                "mood": "confused"
            }

    def _detect_mood(self, question: str, answer: str) -> str:
        """Detect NOVA's mood based on conversation context."""
        q_lower = question.lower()
        a_lower = answer.lower()

        if any(w in q_lower for w in ["help", "confused", "don't understand", "stuck"]):
            return "helping"
        elif any(w in a_lower for w in ["great job", "amazing", "excellent", "congratulations", "well done"]):
            return "celebrating"
        elif any(w in q_lower for w in ["explain", "what is", "how does", "teach"]):
            return "teaching"
        elif any(w in q_lower for w in ["progress", "stats", "level", "streak"]):
            return "analytical"
        return "speaking"

    # ─── Suggestions Engine ───────────────────────────────────────

    def _generate_suggestions(self, limit: int = 3) -> List[Dict[str, str]]:
        """Generate proactive suggestions based on user history."""
        suggestions = []

        # 1. Check for weak spots (low understanding)
        struggles = self.db.query(StudentProgress).filter(
            StudentProgress.user_id == self.user.id,
            StudentProgress.status == "completed",
            StudentProgress.understanding_level < 60.0
        ).limit(1).all()

        for struggle in struggles:
            lesson = self.db.query(Lesson).filter(Lesson.id == struggle.lesson_id).first()
            if lesson:
                suggestions.append({
                    "id": f"review_{lesson.id}",
                    "type": "review",
                    "icon": "🔄",
                    "title": f"Review: {lesson.title}",
                    "message": "Your understanding was below 60%. Let me explain it differently!",
                    "action": f"/classroom/{lesson.course_id}/{lesson.id}"
                })

        # 2. Daily goal suggestion
        xp = self.db.query(UserXP).filter(UserXP.user_id == self.user.id).first()
        if xp and xp.last_active_date != datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            suggestions.append({
                "id": "daily_goal",
                "type": "goal",
                "icon": "🎯",
                "title": "Daily Goal",
                "message": "Complete any lesson today to keep your streak alive!",
                "action": "/courses"
            })

        # 3. New course suggestion
        if len(suggestions) < 2:
            suggestions.append({
                "id": "explore",
                "type": "explore",
                "icon": "🧭",
                "title": "Explore Something New",
                "message": "Try creating a custom AI-generated course on any topic!",
                "action": "/create-course"
            })

        return suggestions[:limit]

    # ─── Confusion Detection ──────────────────────────────────────

    @staticmethod
    def detect_confusion(student_message: str, time_taken_seconds: int = 0) -> bool:
        """Detect if a student is confused or frustrated."""
        msg_lower = student_message.strip().lower()

        confusion_phrases = [
            "i don't know", "idk", "not sure", "confused", "lost",
            "doesn't make sense", "why", "how", "what does that mean",
            "i don't get it", "too hard", "explain again", "help"
        ]

        if any(phrase in msg_lower for phrase in confusion_phrases):
            return True

        if len(msg_lower) < 5 and time_taken_seconds > 60:
            return True

        return False
