"""
AI Virtual Classroom - Main FastAPI Application
Complete backend with all routes for the educational platform.
"""
import json
import os
import sys
import tempfile
import traceback
import shutil
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from config import APP_NAME, APP_VERSION
from models import (
    init_db, get_db, seed_data,
    User, Course, Lesson, StudentProgress, ConversationHistory,
    UserXP, Badge, UserBadge, QuizResult, Homework, HomeworkSubmission,
    LessonRecommendation, LessonStatus, TutorState
)
from auth import (
    register_user, login_user, get_current_user,
    hash_password, verify_password, create_access_token
)
from tutor_engine import TutorEngine
from visual_engine import VisualEngine
from nova_brain import NovaBrain

# ─── App Setup ─────────────────────────────────────────────────

app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.on_event("startup")
def startup():
    init_db()
    seed_data()
    # Sync persisted data from Firestore into ephemeral SQLite
    try:
        from firebase_client import get_all_users, get_all_courses
        from models import SessionLocal, User
        import logging
        
        logger_startup = logging.getLogger('startup')
        
        db = SessionLocal()
        users = get_all_users()
        for u_data in users:
            if not db.query(User).filter(User.id == u_data.get('id')).first():
                u = User(
                    id=u_data.get('id'),
                    username=u_data.get('username'),
                    email=u_data.get('email'),
                    password_hash=u_data.get('password_hash'),
                    full_name=u_data.get('full_name', ''),
                    role=u_data.get('role', 'student'),
                    avatar=u_data.get('avatar', '🧑‍🎓'),
                    parent_id=u_data.get('parent_id')
                )
                db.add(u)
        db.commit()
        db.close()
        
        # Firestore sync happens silently — if no credentials, it's a no-op
        logger_startup.info('Firestore sync completed on startup.')
    except Exception as e:
        print(f'Firestore startup sync skipped: {e}')

import logging


# ─── Pydantic Models ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str = ""
    role: str = "student"
    parent_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class TutorMessageRequest(BaseModel):
    lesson_id: int
    message: str = ""

class QuizAnswerRequest(BaseModel):
    lesson_id: int
    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool

class HomeworkCreateRequest(BaseModel):
    title: str
    description: str
    course_id: Optional[int] = None
    lesson_id: Optional[int] = None
    difficulty: str = "medium"
    max_score: int = 100
    due_date: Optional[str] = None

class HomeworkSubmitRequest(BaseModel):
    homework_id: int
    content: str

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    avatar: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class GenerateCourseRequest(BaseModel):
    topic: str
    detail: str = ""

class GenerateCourseFromTextRequest(BaseModel):
    text_content: str
    title_hint: str = ""

class VisualRequest(BaseModel):
    concept: str
    context: str = ""
    visual_type: str = "auto"

class NovaAskRequest(BaseModel):
    question: str
    screen_context: str = ""


# ─── Root & Frontend ──────────────────────────────────────────

@app.get("/")
def serve_frontend():
    index_path = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": f"Welcome to {APP_NAME} v{APP_VERSION}"}


# ─── AUTH ROUTES ──────────────────────────────────────────────

@app.post("/api/auth/register")
def api_register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, req.username, req.email, req.password, req.full_name, req.role, req.parent_id)
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "avatar": user.avatar,
        }
    }


@app.post("/api/auth/login")
def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    return login_user(db, req.username, req.password)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global Exception: {exc}")
    trace = traceback.format_exc()
    return JSONResponse(
        status_code=400,
        content={"error": "Internal Backend Error", "detail": str(exc), "traceback": trace}
    )


@app.get("/api/auth/me")
def api_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "avatar": user.avatar,
    }


@app.put("/api/auth/profile")
def update_profile(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.full_name is not None:
        user.full_name = req.full_name
    if req.avatar is not None:
        user.avatar = req.avatar
    db.commit()
    return {"message": "Profile updated", "user": {"id": user.id, "username": user.username, "full_name": user.full_name, "avatar": user.avatar}}


@app.put("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ─── COURSE ROUTES ────────────────────────────────────────────

@app.get("/api/courses")
def get_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    courses = db.query(Course).filter(Course.is_active == True).all()
    result = []
    for c in courses:
        lesson_count = db.query(Lesson).filter(Lesson.course_id == c.id).count()
        # Get user's progress for this course
        completed = db.query(StudentProgress).filter(
            StudentProgress.user_id == user.id,
            StudentProgress.course_id == c.id,
            StudentProgress.status == LessonStatus.COMPLETED.value
        ).count()
        result.append({
            "id": c.id, "title": c.title, "description": c.description,
            "icon": c.icon, "category": c.category, "difficulty": c.difficulty,
            "total_lessons": lesson_count, "completed_lessons": completed,
            "progress_percent": round((completed / lesson_count * 100) if lesson_count > 0 else 0),
        })
    return result


@app.get("/api/courses/{course_id}")
def get_course_detail(course_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.order_num).all()
    lessons_data = []
    for l in lessons:
        prog = db.query(StudentProgress).filter(
            StudentProgress.user_id == user.id,
            StudentProgress.lesson_id == l.id
        ).first()
        lessons_data.append({
            "id": l.id, "title": l.title, "order_num": l.order_num,
            "difficulty": l.difficulty, "estimated_minutes": l.estimated_minutes,
            "status": prog.status if prog else "not_started",
            "understanding": prog.understanding_level if prog else 0,
        })
    
    return {
        "id": course.id, "title": course.title, "description": course.description,
        "icon": course.icon, "category": course.category, "difficulty": course.difficulty,
        "lessons": lessons_data,
    }


# ─── COURSE CREATION / AI GENERATION ─────────────────────────

@app.post("/api/courses/generate")
def generate_course(req: GenerateCourseRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a complete course from a topic description using AI."""
    result = TutorEngine.generate_course_from_topic(req.topic, req.detail)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Save generated course to database
    course = Course(
        title=result["title"],
        description=result.get("description", ""),
        icon=result.get("icon", "📘"),
        category=result.get("category", "Custom"),
        difficulty=result.get("difficulty", "beginner"),
        created_by=user.id,
    )
    db.add(course)
    db.flush()

    lessons_created = []
    for lesson_data in result.get("lessons", []):
        concepts = lesson_data.get("key_concepts", [])
        examples = lesson_data.get("examples", [])
        lesson = Lesson(
            course_id=course.id,
            title=lesson_data.get("title", "Untitled"),
            content=lesson_data.get("content", ""),
            key_concepts=json.dumps(concepts) if isinstance(concepts, list) else concepts,
            examples=json.dumps(examples) if isinstance(examples, list) else examples,
            order_num=lesson_data.get("order_num", 0),
            difficulty=lesson_data.get("difficulty", "beginner"),
            estimated_minutes=lesson_data.get("estimated_minutes", 15),
        )
        db.add(lesson)
        db.flush()
        lessons_created.append({
            "id": lesson.id,
            "title": lesson.title,
            "order_num": lesson.order_num,
        })

    db.commit()

    _award_xp(db, user.id, 30, "Created a custom course")

    return {
        "message": "Course generated successfully!",
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "icon": course.icon,
            "lessons_count": len(lessons_created),
            "lessons": lessons_created,
        }
    }


@app.post("/api/courses/generate-from-file")
async def generate_course_from_file(
    file: UploadFile = File(...),
    title_hint: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a file (PDF, TXT, MD) and generate a course from its content."""
    # Validate file type
    allowed_extensions = {".txt", ".md", ".pdf", ".text", ".rst"}
    filename = file.filename or "upload.txt"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: {', '.join(allowed_extensions)}")

    # Read file content
    content_bytes = await file.read()
    text_content = ""

    if ext == ".pdf":
        try:
            import PyPDF2
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
            pages = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            text_content = "\n\n".join(pages)
        except ImportError:
            # Fallback: try to read as text
            try:
                text_content = content_bytes.decode("utf-8", errors="ignore")
            except:
                raise HTTPException(status_code=400, detail="PDF support requires PyPDF2. Please upload a TXT file instead.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")
    else:
        # Text-based files
        try:
            text_content = content_bytes.decode("utf-8", errors="ignore")
        except:
            text_content = content_bytes.decode("latin-1", errors="ignore")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty or unreadable.")

    if len(text_content) < 50:
        raise HTTPException(status_code=400, detail="File content is too short to generate a course from.")

    # Generate course from text using AI
    result = TutorEngine.generate_course_from_text(text_content, title_hint)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Save to database
    course = Course(
        title=result["title"],
        description=result.get("description", f"Generated from {filename}"),
        icon=result.get("icon", "📄"),
        category=result.get("category", "Custom"),
        difficulty=result.get("difficulty", "beginner"),
        created_by=user.id,
    )
    db.add(course)
    db.flush()

    lessons_created = []
    for lesson_data in result.get("lessons", []):
        concepts = lesson_data.get("key_concepts", [])
        examples = lesson_data.get("examples", [])
        lesson = Lesson(
            course_id=course.id,
            title=lesson_data.get("title", "Untitled"),
            content=lesson_data.get("content", ""),
            key_concepts=json.dumps(concepts) if isinstance(concepts, list) else concepts,
            examples=json.dumps(examples) if isinstance(examples, list) else examples,
            order_num=lesson_data.get("order_num", 0),
            difficulty=lesson_data.get("difficulty", "beginner"),
            estimated_minutes=lesson_data.get("estimated_minutes", 15),
        )
        db.add(lesson)
        db.flush()
        lessons_created.append({
            "id": lesson.id,
            "title": lesson.title,
            "order_num": lesson.order_num,
        })

    db.commit()

    _award_xp(db, user.id, 30, "Created course from file")

    return {
        "message": f"Course generated from '{filename}'!",
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "icon": course.icon,
            "lessons_count": len(lessons_created),
            "lessons": lessons_created,
        }
    }


@app.delete("/api/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a user-created course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.created_by != user.id and user.role != "teacher":
        raise HTTPException(status_code=403, detail="You can only delete courses you created")

    # Delete lessons and related data
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).all()
    for lesson in lessons:
        db.query(StudentProgress).filter(StudentProgress.lesson_id == lesson.id).delete()
        db.query(ConversationHistory).filter(ConversationHistory.lesson_id == lesson.id).delete()
        db.query(QuizResult).filter(QuizResult.lesson_id == lesson.id).delete()
    db.query(Lesson).filter(Lesson.course_id == course_id).delete()
    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}


# ─── VISUAL GENERATION ROUTES ─────────────────────────────────

@app.post("/api/visuals/generate")
def generate_visual(req: VisualRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate an AI visual (animation or image) for a concept."""
    result = VisualEngine.generate_concept_visual(req.concept, req.context, req.visual_type)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    _award_xp(db, user.id, 5, "Generated a visual")
    return result

@app.post("/api/visuals/animation")
def generate_animation(req: VisualRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate an HTML5/CSS/JS animation for a concept."""
    result = VisualEngine.generate_animation(req.concept, req.context)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    _award_xp(db, user.id, 5, "Generated animation")
    return result

@app.post("/api/visuals/image")
def generate_image_visual(req: VisualRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a DALL-E educational image for a concept."""
    result = VisualEngine.generate_image(req.concept, req.context)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    _award_xp(db, user.id, 5, "Generated image")
    return result

@app.post("/api/visuals/quick-svg")
def generate_quick_svg(req: VisualRequest, user: User = Depends(get_current_user)):
    """Generate a quick inline SVG diagram for a concept."""
    result = VisualEngine.generate_quick_visual(req.concept)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    course = db.query(Course).filter(Course.id == lesson.course_id).first()
    
    prog = db.query(StudentProgress).filter(
        StudentProgress.user_id == user.id,
        StudentProgress.lesson_id == lesson_id
    ).first()

    return {
        "id": lesson.id, "title": lesson.title, "content": lesson.content,
        "key_concepts": json.loads(lesson.key_concepts) if lesson.key_concepts else [],
        "examples": json.loads(lesson.examples) if lesson.examples else [],
        "order_num": lesson.order_num, "difficulty": lesson.difficulty,
        "estimated_minutes": lesson.estimated_minutes,
        "course": {"id": course.id, "title": course.title, "icon": course.icon} if course else None,
        "progress": {
            "status": prog.status if prog else "not_started",
            "understanding": prog.understanding_level if prog else 0,
            "current_concept": prog.current_concept_index if prog else 0,
        } if prog else None,
    }


# ─── TUTOR / CLASSROOM ROUTES ────────────────────────────────

@app.post("/api/tutor/start-lesson")
def start_lesson(req: TutorMessageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start a new lesson - tutor begins teaching."""
    result = TutorEngine.start_lesson(db, user.id, req.lesson_id)
    
    # Update streak
    _update_streak(db, user.id)
    # Award XP for starting
    # Sync initial progress to Firebase
    try:
        from firebase_client import save_progress
        save_progress({
            "user_id": user.id,
            "lesson_id": req.lesson_id,
            "course_id": result.get("progress", {}).get("course_id", 0),
            "status": "in_progress",
            "current_concept_index": 0,
            "questions_asked": 0,
            "correct_answers": 0,
            "understanding_level": 0.0,
            "tutor_state": "teaching",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"Firebase start progress sync error: {e}")

    _award_xp(db, user.id, 10, "Started a lesson")

    return result


@app.post("/api/tutor/respond")
def tutor_respond(req: TutorMessageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a response to the tutor during a lesson."""
    result = TutorEngine.handle_student_response(db, user.id, req.lesson_id, req.message)
    
    # Award XP based on performance
    if result.get("lesson_complete"):
        _award_xp(db, user.id, 50, "Completed a lesson")
        _check_badges(db, user.id)
    elif result.get("progress", {}).get("correct_answers", 0) > 0:
        _award_xp(db, user.id, 5, "Correct answer")
    
    # Sync progress to Firebase
    try:
        from firebase_client import save_progress
        save_progress({
            "user_id": user.id,
            "lesson_id": req.lesson_id,
            "course_id": result.get("progress", {}).get("course_id", 0),
            "status": result.get("progress", {}).get("status", "in_progress"),
            "current_concept_index": result.get("progress", {}).get("current_concept", 0),
            "questions_asked": result.get("progress", {}).get("questions_asked", 0),
            "correct_answers": result.get("progress", {}).get("correct_answers", 0),
            "understanding_level": result.get("progress", {}).get("understanding", 0.0),
            "tutor_state": result.get("tutor_state", "teaching"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"Firebase progress sync error: {e}")

    return result


@app.get("/api/tutor/conversation/{lesson_id}")
def get_conversation(lesson_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get conversation history for a lesson."""
    messages = db.query(ConversationHistory).filter(
        ConversationHistory.user_id == user.id,
        ConversationHistory.lesson_id == lesson_id,
    ).order_by(ConversationHistory.timestamp).all()
    

    return [{"role": m.role, "content": m.content, "type": m.message_type, 
             "timestamp": m.timestamp.isoformat()} for m in messages]


# ─── QUIZ ROUTES ──────────────────────────────────────────────

@app.get("/api/quiz/{lesson_id}")
def get_quiz(lesson_id: int, count: int = 5, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a quiz for a lesson."""
    questions = TutorEngine.generate_quiz(db, lesson_id, count)
    return {"lesson_id": lesson_id, "questions": questions}


@app.post("/api/quiz/submit")
def submit_quiz_answer(req: QuizAnswerRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Submit a quiz answer."""
    xp = 20 if req.is_correct else 5  # XP for attempting
    
    result = QuizResult(
        user_id=user.id,
        lesson_id=req.lesson_id,
        question=req.question,
        user_answer=req.user_answer,
        correct_answer=req.correct_answer,
        is_correct=req.is_correct,
        xp_earned=xp,
    )
    db.add(result)
    db.commit()
    
    _award_xp(db, user.id, xp, "Completed a quiz question")
    
    # Sync quiz result to Firebase
    try:
        from firebase_client import save_quiz_result
        save_quiz_result({
            "user_id": user.id,
            "lesson_id": req.lesson_id,
            "question": req.question,
            "user_answer": req.user_answer,
            "correct_answer": req.correct_answer,
            "is_correct": req.is_correct,
            "xp_earned": xp,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        print(f"Firebase quiz sync error: {e}")
        
    _check_badges(db, user.id)
    
    return {"is_correct": req.is_correct, "xp_earned": xp, "message": "Great job! ✅" if req.is_correct else "Keep trying! 💪"}


@app.get("/api/quiz/results/{lesson_id}")
def get_quiz_results(lesson_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get quiz results for a lesson."""
    results = db.query(QuizResult).filter(
        QuizResult.user_id == user.id,
        QuizResult.lesson_id == lesson_id
    ).all()
    
    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    
    return {
        "total": total,
        "correct": correct,
        "score": round((correct / total * 100) if total > 0 else 0),
        "results": [{"question": r.question, "user_answer": r.user_answer, 
                      "correct_answer": r.correct_answer, "is_correct": r.is_correct} for r in results]
    }


# ─── GAMIFICATION ROUTES ─────────────────────────────────────

@app.get("/api/gamification/stats")
def get_gamification_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get XP, level, streaks, badges for current user."""
    xp_record = db.query(UserXP).filter(UserXP.user_id == user.id).first()
    if not xp_record:
        xp_record = UserXP(user_id=user.id)
        db.add(xp_record)
        db.commit()
    
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.id).all()
    badge_details = []
    for ub in badges:
        badge = db.query(Badge).filter(Badge.id == ub.badge_id).first()
        if badge:
            badge_details.append({
                "name": badge.name, "description": badge.description,
                "icon": badge.icon, "earned_at": ub.earned_at.isoformat()
            })
    
    # Level calculation: every 200 XP = 1 level
    level = max(1, xp_record.xp_total // 200 + 1)
    xp_for_next = level * 200
    xp_progress = xp_record.xp_total - ((level - 1) * 200)
    
    return {
        "xp_total": xp_record.xp_total,
        "level": level,
        "xp_for_next_level": xp_for_next,
        "xp_progress": xp_progress,
        "streak_days": xp_record.streak_days,
        "longest_streak": xp_record.longest_streak,
        "lessons_completed": xp_record.lessons_completed,
        "quizzes_passed": xp_record.quizzes_passed,
        "badges": badge_details,
    }


@app.get("/api/gamification/all-badges")
def get_all_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all available badges."""
    badges = db.query(Badge).all()
    earned = db.query(UserBadge).filter(UserBadge.user_id == user.id).all()
    earned_ids = {ub.badge_id for ub in earned}
    
    return [{
        "id": b.id, "name": b.name, "description": b.description,
        "icon": b.icon, "criteria_type": b.criteria_type,
        "criteria_value": b.criteria_value, "earned": b.id in earned_ids
    } for b in badges]


# ─── LEADERBOARD ──────────────────────────────────────────────

@app.get("/api/leaderboard")
def get_leaderboard(limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get the leaderboard - top students by XP."""
    top_users = db.query(UserXP).order_by(desc(UserXP.xp_total)).limit(limit).all()
    
    leaderboard = []
    for i, xp in enumerate(top_users):
        u = db.query(User).filter(User.id == xp.user_id).first()
        if u:
            leaderboard.append({
                "rank": i + 1,
                "user_id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "avatar": u.avatar,
                "xp_total": xp.xp_total,
                "level": max(1, xp.xp_total // 200 + 1),
                "streak_days": xp.streak_days,
                "is_me": u.id == user.id,
            })
    
    return leaderboard


# ─── HOMEWORK ROUTES ─────────────────────────────────────────

@app.get("/api/homework")
def get_homework_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get homework list - teachers see all, students see assigned."""
    homeworks = db.query(Homework).order_by(desc(Homework.created_at)).all()
    result = []
    for h in homeworks:
        submission = db.query(HomeworkSubmission).filter(
            HomeworkSubmission.homework_id == h.id,
            HomeworkSubmission.user_id == user.id
        ).first() if user.role == "student" else None
        
        course = db.query(Course).filter(Course.id == h.course_id).first() if h.course_id else None
        
        result.append({
            "id": h.id, "title": h.title, "description": h.description,
            "course": course.title if course else "General",
            "difficulty": h.difficulty, "max_score": h.max_score,
            "due_date": h.due_date.isoformat() if h.due_date else None,
            "created_at": h.created_at.isoformat(),
            "submitted": submission is not None if submission is not None else False,
            "grade": submission.grade if submission and submission.is_graded else None,
            "feedback": submission.feedback if submission and submission.is_graded else None,
        })
    return result


@app.post("/api/homework/create")
def create_homework(req: HomeworkCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create homework (teachers only)."""
    if user.role not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Only teachers can create homework")
    
    hw = Homework(
        title=req.title,
        description=req.description,
        course_id=req.course_id,
        lesson_id=req.lesson_id,
        assigned_by=user.id,
        difficulty=req.difficulty,
        max_score=req.max_score,
        due_date=datetime.fromisoformat(req.due_date) if req.due_date else None,
    )
    db.add(hw)
    db.commit()
    return {"id": hw.id, "message": "Homework created successfully!"}


@app.post("/api/homework/submit")
def submit_homework(req: HomeworkSubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Submit homework and get AI grading."""
    hw = db.query(Homework).filter(Homework.id == req.homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Check if already submitted
    existing = db.query(HomeworkSubmission).filter(
        HomeworkSubmission.homework_id == hw.id,
        HomeworkSubmission.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already submitted")
    
    # AI grading
    course = db.query(Course).filter(Course.id == hw.course_id).first() if hw.course_id else None
    topic = course.title if course else "General"
    grading = TutorEngine.grade_homework(topic, hw.description, req.content)
    
    submission = HomeworkSubmission(
        homework_id=hw.id,
        user_id=user.id,
        content=req.content,
        grade=grading.get("score", 0),
        feedback=json.dumps(grading),
        is_graded=True,
    )
    db.add(submission)
    db.commit()
    
    # Award XP
    xp = int(grading.get("score", 0) / 5)  # Up to 20 XP
    _award_xp(db, user.id, xp, "Homework submitted")
    _check_badges(db, user.id)
    
    return {"grade": grading.get("score", 0), "feedback": grading, "xp_earned": xp}


# ─── TEACHER DASHBOARD ───────────────────────────────────────

@app.get("/api/dashboard/teacher")
def teacher_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Teacher dashboard with student stats."""
    students = db.query(User).filter(User.role == "student").all()
    
    student_stats = []
    for s in students:
        xp = db.query(UserXP).filter(UserXP.user_id == s.id).first()
        completed = db.query(StudentProgress).filter(
            StudentProgress.user_id == s.id,
            StudentProgress.status == LessonStatus.COMPLETED.value
        ).count()
        avg_score = db.query(func.avg(StudentProgress.understanding_level)).filter(
            StudentProgress.user_id == s.id,
            StudentProgress.status == LessonStatus.COMPLETED.value
        ).scalar() or 0
        
        hw_done = db.query(HomeworkSubmission).filter(HomeworkSubmission.user_id == s.id).count()
        hw_avg = db.query(func.avg(HomeworkSubmission.grade)).filter(
            HomeworkSubmission.user_id == s.id,
            HomeworkSubmission.is_graded == True
        ).scalar() or 0
        
        student_stats.append({
            "id": s.id, "username": s.username, "full_name": s.full_name,
            "avatar": s.avatar,
            "xp": xp.xp_total if xp else 0,
            "level": max(1, (xp.xp_total if xp else 0) // 200 + 1),
            "streak": xp.streak_days if xp else 0,
            "lessons_completed": completed,
            "avg_understanding": round(avg_score, 1),
            "homework_completed": hw_done,
            "homework_avg_grade": round(hw_avg, 1),
        })
    
    # Overall stats
    total_students = len(students)
    total_lessons_completed = sum(s["lessons_completed"] for s in student_stats)
    avg_understanding = round(sum(s["avg_understanding"] for s in student_stats) / total_students, 1) if total_students > 0 else 0
    
    return {
        "total_students": total_students,
        "total_lessons_completed": total_lessons_completed,
        "avg_understanding": avg_understanding,
        "students": student_stats,
    }


# ─── PARENT REPORT ────────────────────────────────────────────

@app.get("/api/dashboard/parent")
def parent_report(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Parent report - see children's progress."""
    # Find children
    children = db.query(User).filter(User.parent_id == user.id).all()
    
    # If no linked children, show a helpful message
    if not children and user.role == "parent":
        return {"message": "No children linked to your account yet.", "children": []}
    
    # If student is viewing their own report (or parent viewing children)
    targets = children if children else [user]
    
    reports = []
    for child in targets:
        xp = db.query(UserXP).filter(UserXP.user_id == child.id).first()
        
        # Course-wise progress
        courses = db.query(Course).all()
        course_progress = []
        for c in courses:
            total = db.query(Lesson).filter(Lesson.course_id == c.id).count()
            completed = db.query(StudentProgress).filter(
                StudentProgress.user_id == child.id,
                StudentProgress.course_id == c.id,
                StudentProgress.status == LessonStatus.COMPLETED.value
            ).count()
            if total > 0:
                course_progress.append({
                    "course": c.title, "icon": c.icon,
                    "total_lessons": total, "completed": completed,
                    "progress": round(completed / total * 100),
                })
        
        # Recent activity
        recent = db.query(StudentProgress).filter(
            StudentProgress.user_id == child.id
        ).order_by(desc(StudentProgress.started_at)).limit(5).all()
        
        recent_activity = []
        for r in recent:
            lesson = db.query(Lesson).filter(Lesson.id == r.lesson_id).first()
            recent_activity.append({
                "lesson": lesson.title if lesson else "Unknown",
                "status": r.status,
                "understanding": r.understanding_level,
                "date": r.started_at.isoformat(),
            })
        
        # Quiz performance
        quiz_total = db.query(QuizResult).filter(QuizResult.user_id == child.id).count()
        quiz_correct = db.query(QuizResult).filter(QuizResult.user_id == child.id, QuizResult.is_correct == True).count()
        
        reports.append({
            "child": {"id": child.id, "username": child.username, "full_name": child.full_name, "avatar": child.avatar},
            "xp": xp.xp_total if xp else 0,
            "level": max(1, (xp.xp_total if xp else 0) // 200 + 1),
            "streak": xp.streak_days if xp else 0,
            "courses": course_progress,
            "recent_activity": recent_activity,
            "quiz_stats": {"total": quiz_total, "correct": quiz_correct, "accuracy": round(quiz_correct / quiz_total * 100) if quiz_total > 0 else 0},
        })
    
    return {"children": reports}


# ─── RECOMMENDATIONS ─────────────────────────────────────────

@app.get("/api/recommendations")
def get_recommendations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get personalized lesson recommendations."""
    recs = TutorEngine.get_recommendations(db, user.id)
    
    # Enrich with lesson details
    enriched = []
    for r in recs:
        lesson = db.query(Lesson).filter(Lesson.id == r.get("lesson_id")).first()
        if lesson:
            course = db.query(Course).filter(Course.id == lesson.course_id).first()
            enriched.append({
                "lesson_id": lesson.id,
                "lesson_title": lesson.title,
                "course_title": course.title if course else "",
                "course_icon": course.icon if course else "📘",
                "difficulty": lesson.difficulty,
                "reason": r.get("reason", ""),
                "priority": r.get("priority", 0),
            })
    
    return enriched


# ─── STUDENT OVERALL PROGRESS ────────────────────────────────

@app.get("/api/progress/overview")
def get_progress_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get overall progress for the student dashboard."""
    xp = db.query(UserXP).filter(UserXP.user_id == user.id).first()
    
    # Courses progress
    courses = db.query(Course).filter(Course.is_active == True).all()
    course_stats = []
    total_completed = 0
    total_lessons = 0
    
    for c in courses:
        lesson_count = db.query(Lesson).filter(Lesson.course_id == c.id).count()
        completed = db.query(StudentProgress).filter(
            StudentProgress.user_id == user.id,
            StudentProgress.course_id == c.id,
            StudentProgress.status == LessonStatus.COMPLETED.value
        ).count()
        total_completed += completed
        total_lessons += lesson_count
        
        if lesson_count > 0:
            course_stats.append({
                "id": c.id, "title": c.title, "icon": c.icon,
                "total": lesson_count, "completed": completed,
                "progress": round(completed / lesson_count * 100),
            })
    
    # Recent lessons
    recent = db.query(StudentProgress).filter(
        StudentProgress.user_id == user.id
    ).order_by(desc(StudentProgress.started_at)).limit(5).all()
    
    recent_lessons = []
    for r in recent:
        lesson = db.query(Lesson).filter(Lesson.id == r.lesson_id).first()
        if lesson:
            recent_lessons.append({
                "lesson_id": lesson.id,
                "title": lesson.title,
                "status": r.status,
                "understanding": r.understanding_level,
            })
    
    return {
        "xp_total": xp.xp_total if xp else 0,
        "level": max(1, (xp.xp_total if xp else 0) // 200 + 1),
        "streak": xp.streak_days if xp else 0,
        "total_lessons": total_lessons,
        "completed_lessons": total_completed,
        "overall_progress": round(total_completed / total_lessons * 100) if total_lessons > 0 else 0,
        "courses": course_stats,
        "recent_lessons": recent_lessons,
    }

# ─── HELPER FUNCTIONS ────────────────────────────────────────

def _award_xp(db: Session, user_id: int, amount: int, reason: str = ""):
    """Award XP to a user."""
    xp = db.query(UserXP).filter(UserXP.user_id == user_id).first()
    if not xp:
        xp = UserXP(user_id=user_id)
        db.add(xp)
    
    xp.xp_total += amount
    xp.level = max(1, xp.xp_total // 200 + 1)
    db.commit()

    # Sync to Firebase for persistence
    try:
        from firebase_client import save_user_xp
        save_user_xp({
            "user_id": user_id,
            "xp_total": xp.xp_total,
            "level": xp.level,
            "streak_days": xp.streak_days,
            "longest_streak": xp.longest_streak,
            "last_active_date": xp.last_active_date,
            "lessons_completed": xp.lessons_completed,
            "quizzes_passed": xp.quizzes_passed,
            "homework_completed": xp.homework_completed
        })
    except Exception as e:
        print(f"Firebase XP sync error: {e}")

def _update_streak(db: Session, user_id: int):
    """Update daily streak."""
    xp = db.query(UserXP).filter(UserXP.user_id == user_id).first()
    if not xp:
        xp = UserXP(user_id=user_id)
        db.add(xp)
    
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if xp.last_active_date == today:
        return
    elif xp.last_active_date == yesterday:
        xp.streak_days += 1
    else:
        xp.streak_days = 1
    
    xp.last_active_date = today
    if xp.streak_days > xp.longest_streak:
        xp.longest_streak = xp.streak_days
    db.commit()
    
    # Sync streak to Firebase
    try:
        from firebase_client import save_user_xp
        save_user_xp({
            "user_id": user_id,
            "xp_total": xp.xp_total,
            "level": xp.level,
            "streak_days": xp.streak_days,
            "longest_streak": xp.longest_streak,
            "last_active_date": xp.last_active_date
        })
    except Exception as e:
        print(f"Firebase streak sync error: {e}")

def _check_badges(db: Session, user_id: int):
    """Check and award badges based on criteria."""
    xp = db.query(UserXP).filter(UserXP.user_id == user_id).first()
    if not xp:
        return
    
    badges = db.query(Badge).all()
    earned = {ub.badge_id for ub in db.query(UserBadge).filter(UserBadge.user_id == user_id).all()}
    
    lessons_completed = db.query(StudentProgress).filter(
        StudentProgress.user_id == user_id,
        StudentProgress.status == LessonStatus.COMPLETED.value
    ).count()
    
    quizzes_passed = db.query(QuizResult).filter(
        QuizResult.user_id == user_id,
        QuizResult.is_correct == True
    ).count()
    
    hw_completed = db.query(HomeworkSubmission).filter(
        HomeworkSubmission.user_id == user_id
    ).count()
    
    for badge in badges:
        if badge.id in earned:
            continue
        
        award = False
        if badge.criteria_type == "lessons" and lessons_completed >= badge.criteria_value:
            award = True
        elif badge.criteria_type == "xp" and xp.xp_total >= badge.criteria_value:
            award = True
        elif badge.criteria_type == "streak" and xp.streak_days >= badge.criteria_value:
            award = True
        elif badge.criteria_type == "quiz" and quizzes_passed >= badge.criteria_value:
            award = True
        elif badge.criteria_type == "homework" and hw_completed >= badge.criteria_value:
            award = True
        
        if award:
            ub = UserBadge(user_id=user_id, badge_id=badge.id)
            db.add(ub)
    
    xp.lessons_completed = lessons_completed
    xp.quizzes_passed = quizzes_passed
    xp.homework_completed = hw_completed
    db.commit()

# ─── NOVA AI Teacher API ──────────────────────────────────────

@app.get("/api/nova/status")
def get_nova_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns NOVA's current analysis and proactive suggestions."""
    try:
        status = NovaBrain.analyze_student(db, current_user.id)
        return status
    except Exception as e:
        print(f"NOVA Status Error: {e}")
        return {"mood": "neutral", "message": "NOVA is initializing...", "suggestions": []}


@app.post("/api/nova/ask")
def ask_nova(req: NovaAskRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Conversational AI endpoint — ask NOVA anything."""
    try:
        result = NovaBrain.ask(db, current_user.id, req.question, req.screen_context)
        return result
    except Exception as e:
        print(f"NOVA Ask Error: {e}")
        return {"response": "I encountered an error. Please try again!", "mood": "confused"}


# Keep legacy endpoint for backward compat
@app.get("/api/jarvis/status")
def get_jarvis_status_legacy(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_nova_status(current_user, db)

@app.get("/api/rl/stats")
def get_rl_stats():
    """Returns the pre-trained RL convergence plots/data."""
    import os, json
    data_path = os.path.join(os.path.dirname(__file__), "rl_engine", "results", "training_data.json")
    
    dqn, ppo, baseline = [], [], 0.0
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r') as f:
                data = json.load(f)
                dqn = data.get("dqn", [])
                ppo = data.get("ppo", [])
                baseline = data.get("rule_based", 0.0)
        except Exception:
            pass

    # Simulate Learner State Evolution (Mastery, Engagement, Frustration)
    import math
    episodes = max(len(dqn), len(ppo), 100)
    mastery = []
    engagement = []
    frustration = []
    
    m_val = 10.0
    for i in range(episodes):
        # Mastery is a logarithmic curve climbing upwards
        m_val += (95.0 - m_val) * 0.03
        mastery.append(round(m_val, 2))
        
        # Engagement starts high, dips slightly, recovers as mastery improves
        eng_base = 80 + 15 * math.sin(i / 10.0)
        engagement.append(round(max(0, min(100, eng_base)), 2))
        
        # Frustration spikes when engagement dips
        frust_base = max(0, 100 - eng_base - (m_val * 0.5)) + (10 * math.cos(i / 5.0))
        frustration.append(round(max(0, min(100, frust_base)), 2))
        
    return {
        "dqn": dqn,
        "ppo": ppo,
        "rule_based": baseline,
        "learner_state": {
            "mastery": mastery,
            "engagement": engagement,
            "frustration": frustration
        }
    }

@app.get("/api/debug/users")
def debug_users(db: Session = Depends(get_db)):
    """Secret debug endpoint to check sqlite vs firebase state."""
    from models import User
    sqlite_users = db.query(User).all()
    
    try:
        from firebase_client import get_all_users
        firebase_users = get_all_users()
    except Exception as e:
        firebase_users = f"Error: {e}"
        
    return {
        "sqlite_count": len(sqlite_users),
        "sqlite_users": [{"id": u.id, "username": u.username} for u in sqlite_users],
        "firebase_users": [{"id": u.get("id"), "username": u.get("username")} for u in firebase_users] if isinstance(firebase_users, list) else firebase_users
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
