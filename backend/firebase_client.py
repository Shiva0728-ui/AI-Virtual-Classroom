"""
Firebase Firestore Client for AI Virtual Classroom
Provides persistent cloud storage to survive Vercel cold starts.
Uses Firebase Admin SDK with Firestore.
"""
import os
import json
from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Lazy initialization
_db = None
_initialized = False


def _get_firestore():
    """Lazy-initialize Firebase and return Firestore client."""
    global _db, _initialized
    if _initialized:
        return _db

    _initialized = True

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        # Check for credentials
        cred_json = os.getenv("FIREBASE_CREDENTIALS")
        if not cred_json:
            logger.warning("FIREBASE_CREDENTIALS not set — Firestore disabled.")
            return None

        # Parse credentials from environment variable (JSON string)
        try:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid FIREBASE_CREDENTIALS JSON: {e}")
            return None

        # Initialize Firebase app (only once)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        logger.info("✅ Firebase Firestore connected successfully.")
        return _db

    except ImportError:
        logger.warning("firebase-admin not installed — Firestore disabled.")
        return None
    except Exception as e:
        logger.error(f"Firebase initialization error: {e}")
        return None


# ─── User Persistence ────────────────────────────────────────────

def save_user(user_data: Dict[str, Any]):
    """Persist a user record to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        doc_ref = db.collection("users").document(str(user_data["id"]))
        doc_ref.set(user_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_user error: {e}")


def get_all_users() -> List[Dict[str, Any]]:
    """Retrieve all user records from Firestore."""
    db = _get_firestore()
    if not db:
        return []
    try:
        docs = db.collection("users").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore get_all_users error: {e}")
        return []


# ─── Course Persistence ──────────────────────────────────────────

def save_course(course_data: Dict[str, Any]):
    """Persist a course (with lessons) to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        doc_ref = db.collection("courses").document(str(course_data.get("id", course_data.get("title"))))
        doc_ref.set(course_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_course error: {e}")


def get_all_courses() -> List[Dict[str, Any]]:
    """Retrieve all courses from Firestore."""
    db = _get_firestore()
    if not db:
        return []
    try:
        docs = db.collection("courses").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore get_all_courses error: {e}")
        return []


# ─── Homework Persistence ────────────────────────────────────────

def save_homework(hw_data: Dict[str, Any]):
    """Persist a homework record to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        doc_ref = db.collection("homework").document(str(hw_data.get("id", "")))
        doc_ref.set(hw_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_homework error: {e}")


def get_all_homework() -> List[Dict[str, Any]]:
    """Retrieve all homework from Firestore."""
    db = _get_firestore()
    if not db:
        return []
    try:
        docs = db.collection("homework").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore get_all_homework error: {e}")
        return []


# ─── Progress Persistence ────────────────────────────────────────

def save_progress(progress_data: Dict[str, Any]):
    """Persist student progress to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        key = f"{progress_data.get('user_id')}_{progress_data.get('lesson_id')}"
        doc_ref = db.collection("progress").document(key)
        doc_ref.set(progress_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_progress error: {e}")


def get_user_progress(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve progress records for a specific user."""
    db = _get_firestore()
    if not db:
        return []
    try:
        # Use simple collection query
        docs = db.collection("progress").where("user_id", "==", int(user_id)).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore get_user_progress error: {e}")
        return []


def get_all_user_progress(user_id: int) -> List[Dict[str, Any]]:
    """Alias for get_user_progress to maintain clear naming in sync logic."""
    return get_user_progress(user_id)


# ─── XP Persistence ─────────────────────────────────────────────

def save_user_xp(xp_data: Dict[str, Any]):
    """Persist student XP/Level/Streak data to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        doc_ref = db.collection("user_xp").document(str(xp_data.get("user_id")))
        doc_ref.set(xp_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_user_xp error: {e}")


def get_user_xp(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve XP record for a specific user."""
    db = _get_firestore()
    if not db:
        return None
    try:
        doc = db.collection("user_xp").document(str(user_id)).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"Firestore get_user_xp error: {e}")
        return None


# ─── Quiz & Badge Persistence ────────────────────────────────────

def save_quiz_result(quiz_data: Dict[str, Any]):
    """Persist a quiz result record to Firestore."""
    db = _get_firestore()
    if not db:
        return
    try:
        # Generate a unique key for the quiz result
        key = f"quiz_{quiz_data.get('user_id')}_{int(datetime.now().timestamp())}"
        doc_ref = db.collection("quiz_results").document(key)
        doc_ref.set(quiz_data, merge=True)
    except Exception as e:
        logger.error(f"Firestore save_quiz_result error: {e}")


def get_user_quiz_results(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all quiz results for a user."""
    db = _get_firestore()
    if not db:
        return []
    try:
        docs = db.collection("quiz_results").where("user_id", "==", int(user_id)).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Firestore get_user_quiz_results error: {e}")
        return []


# ─── Generic Sync Helper ─────────────────────────────────────────

def sync_collection_to_firestore(collection_name: str, records: List[Dict[str, Any]], id_field: str = "id"):
    """Bulk sync a list of records to a Firestore collection."""
    db = _get_firestore()
    if not db:
        return
    try:
        batch = db.batch()
        for record in records:
            doc_id = str(record.get(id_field, ""))
            if doc_id:
                ref = db.collection(collection_name).document(doc_id)
                batch.set(ref, record, merge=True)
        batch.commit()
        logger.info(f"✅ Synced {len(records)} records to Firestore/{collection_name}")
    except Exception as e:
        logger.error(f"Firestore bulk sync error ({collection_name}): {e}")
