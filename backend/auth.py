"""
Authentication helpers for AI Virtual Classroom
"""
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from models import get_db, User, UserXP

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    # Dynamic Firebase fallback - Vercel instances might be missing this user
    if not user:
        try:
            from firebase_client import get_all_users
            users = get_all_users()
            for u_data in users:
                if u_data.get('id') == int(user_id):
                    user = User(
                        id=u_data.get('id'),
                        username=u_data.get('username'),
                        email=u_data.get('email'),
                        password_hash=u_data.get('password_hash'),
                        full_name=u_data.get('full_name', ''),
                        role=u_data.get('role', 'student'),
                        avatar=u_data.get('avatar', '🧑‍🎓'),
                        parent_id=u_data.get('parent_id')
                    )
                    db.add(user)
                    db.commit()
                    break
        except Exception:
            pass

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def register_user(db: Session, username: str, email: str, password: str, full_name: str = "", role: str = "student", parent_id: int = None) -> User:
    # Check existing
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate globally unique integer ID for serverless environments
    import random
    user_id = random.randint(100000000, 2147483647)
    while db.query(User).filter(User.id == user_id).first():
        user_id = random.randint(100000000, 2147483647)

    avatars = {"student": "🧑‍🎓", "teacher": "👨‍🏫", "parent": "👨‍👩‍👧"}
    user = User(
        id=user_id,
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        avatar=avatars.get(role, "🧑‍🎓"),
        parent_id=parent_id,
    )
    db.add(user)
    db.flush()

    # Create XP record for students
    if role == "student":
        xp = UserXP(user_id=user.id)
        db.add(xp)

    db.commit()
    db.refresh(user)

    # Sync to Firebase
    try:
        from firebase_client import save_user as fb_save_user
        fb_save_user({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "password_hash": user.password_hash,
            "full_name": user.full_name,
            "role": user.role,
            "avatar": user.avatar,
            "parent_id": user.parent_id
        })
    except Exception as e:
        import logging
        logging.error(f"Firebase sync logic failed: {e}")

    return user


def login_user(db: Session, username: str, password: str) -> dict:
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    # Dynamic Firebase fallback
    if not user:
        try:
            from firebase_client import get_all_users
            users = get_all_users()
            for u_data in users:
                if u_data.get('username') == username or u_data.get('email') == username:
                    if not db.query(User).filter(User.id == u_data.get('id')).first():
                        user = User(
                            id=u_data.get('id'),
                            username=u_data.get('username'),
                            email=u_data.get('email'),
                            password_hash=u_data.get('password_hash'),
                            full_name=u_data.get('full_name', ''),
                            role=u_data.get('role', 'student'),
                            avatar=u_data.get('avatar', '🧑‍🎓'),
                            parent_id=u_data.get('parent_id')
                        )
                        db.add(user)
                        db.commit()
                        break
        except Exception:
            pass

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

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
