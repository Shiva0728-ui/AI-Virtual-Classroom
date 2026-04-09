"""
JARVIS Brain - Proactive Smart Assistant Engine
Acts as the intelligent core that analyzes student behavior,
detects confusion, and generates proactive suggestions.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
import json
import logging

from models import User, UserXP, StudentProgress, StudentInsight, StudySession, Lesson, Course

logger = logging.getLogger(__name__)


class JarvisBrain:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def get_jarvis_status(self) -> Dict[str, Any]:
        """
        Generates the current HUD status for JARVIS.
        Analyzes recent activity to determine mood and message.
        """
        xp_record = self.user.xp_record
        
        # Default state
        mood = "neutral"
        message = f"Ready to learn, {self.user.username}? I'm here to help."
        
        if not xp_record:
            return {"mood": mood, "message": message, "suggestions": []}

        # Analyze streak and activity
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_active_today = xp_record.last_active_date == today
        
        if xp_record.streak_days > 0 and not is_active_today:
            mood = "encouraging"
            message = f"You're on a {xp_record.streak_days}-day streak! Let's keep the momentum going today."
        elif is_active_today and xp_record.streak_days > 3:
            mood = "happy"
            message = f"Amazing work keeping up that {xp_record.streak_days}-day streak! What's next?"
        elif xp_record.level > 1:
            mood = "thinking"
            message = f"Level {xp_record.level} already! Let's tackle something challenging today."

        # Check for lingering incomplete lessons
        recent_progress = self.db.query(StudentProgress).filter(
            StudentProgress.user_id == self.user.id,
            StudentProgress.status == "in_progress"
        ).order_by(StudentProgress.started_at.desc()).first()

        if recent_progress:
            lesson = self.db.query(Lesson).filter(Lesson.id == recent_progress.lesson_id).first()
            if lesson:
                mood = "suggestive"
                message = f"You were studying '{lesson.title}'. Want to pick up where we left off?"

        # Get top 2 suggestions
        suggestions = self._generate_suggestions(limit=2)

        return {
            "mood": mood,
            "message": message,
            "suggestions": suggestions
        }

    def _generate_suggestions(self, limit: int = 3) -> List[Dict[str, str]]:
        """Generates proactive suggestions based on user history"""
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
                    "title": f"Review: {lesson.title}",
                    "message": "You had some trouble with this recently. I can explain it differently!",
                    "action": f"/classroom/{lesson.course_id}/{lesson.id}"
                })

        # 2. Daily goal suggestion
        xp = self.user.xp_record
        if xp and not xp.last_active_date == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            suggestions.append({
                "id": "daily_goal",
                "type": "goal",
                "title": "Daily Goal",
                "message": "Complete any lesson today to extend your streak!",
                "action": "/courses"
            })

        # 3. New course suggestion
        if not suggestions:
            suggestions.append({
                "id": "explore",
                "type": "explore",
                "title": "Explore Something New",
                "message": "Why not try creating a new course with AI today?",
                "action": "/create-course"
            })

        return suggestions[:limit]

    def record_study_session(self, duration_minutes: int, concepts_mastered: int):
        """Records a study session for analytics"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        session = self.db.query(StudySession).filter(
            StudySession.user_id == self.user.id,
            StudySession.session_date == today
        ).first()
        
        if session:
            session.duration_minutes += duration_minutes
            session.concepts_mastered += concepts_mastered
        else:
            session = StudySession(
                user_id=self.user.id,
                session_date=today,
                duration_minutes=duration_minutes,
                concepts_mastered=concepts_mastered,
                focus_score=100
            )
            self.db.add(session)
            
        self.db.commit()

    @staticmethod
    def detect_confusion(student_message: str, time_taken_seconds: int = 0) -> bool:
        """
        Analyzes a student's message to detect likely confusion or frustration.
        """
        msg_lower = student_message.strip().lower()
        
        confusion_phrases = [
            "i don't know", "idk", "not sure", "confused", "lost",
            "doesn't make sense", "why", "how", "what does that mean",
            "i don't get it", "too hard", "explain again", "help"
        ]
        
        # Direct keyword match
        if any(phrase in msg_lower for phrase in confusion_phrases):
            return True
            
        # Very short responses to complex questions might indicate guessing/giving up
        if len(msg_lower) < 5 and time_taken_seconds > 60:
            return True
            
        return False
