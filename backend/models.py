"""
Database models for AI Virtual Classroom
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import enum

from config import DATABASE_URL
import os
import shutil

if DATABASE_URL == "sqlite:////tmp/ai_classroom.db":
    src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai_classroom.db")
    dst = "/tmp/ai_classroom.db"
    if os.path.exists(src) and not os.path.exists(dst):
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print("Successfully transferred database to writable /tmp volume on module load.")
        except Exception as e:
            print(f"CRITICAL SQLITE COPY ERROR: {e}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Use standard pooling for Postgres/Supabase
    engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    PARENT = "parent"


class LessonStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TutorState(str, enum.Enum):
    TEACHING = "teaching"
    ASKING_QUESTION = "asking_question"
    WAITING_RESPONSE = "waiting_response"
    GIVING_FEEDBACK = "giving_feedback"
    SHOWING_EXAMPLE = "showing_example"
    QUIZ_MODE = "quiz_mode"


# ─── User Models ────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), default="")
    role = Column(String(20), default=UserRole.STUDENT.value)
    avatar = Column(String(20), default="🧑‍🎓")
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    # Relationships
    xp_record = relationship("UserXP", back_populates="user", uselist=False)
    badges = relationship("UserBadge", back_populates="user")
    progress = relationship("StudentProgress", back_populates="user")
    conversations = relationship("ConversationHistory", back_populates="user")
    quiz_results = relationship("QuizResult", back_populates="user")
    homework_submissions = relationship("HomeworkSubmission", back_populates="user")
    insights = relationship("StudentInsight", back_populates="user")
    study_sessions = relationship("StudySession", back_populates="user")
    children = relationship("User", backref="parent", remote_side=[id], foreign_keys=[parent_id])


# ─── Course & Lesson Models ────────────────────────────────────
class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="📘")
    category = Column(String(50), default="Programming")
    difficulty = Column(String(20), default="beginner")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    lessons = relationship("Lesson", back_populates="course", order_by="Lesson.order_num")


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    key_concepts = Column(Text, default="")  # JSON list of concepts
    examples = Column(Text, default="")  # JSON list of code examples
    order_num = Column(Integer, default=0)
    difficulty = Column(String(20), default="beginner")
    estimated_minutes = Column(Integer, default=15)

    course = relationship("Course", back_populates="lessons")


# ─── Progress & Conversation ───────────────────────────────────
class StudentProgress(Base):
    __tablename__ = "student_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    status = Column(String(20), default=LessonStatus.NOT_STARTED.value)
    score = Column(Float, default=0.0)
    understanding_level = Column(Float, default=0.0)  # 0-100
    tutor_state = Column(String(30), default=TutorState.TEACHING.value)
    current_concept_index = Column(Integer, default=0)
    questions_asked = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="progress")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    role = Column(String(20), nullable=False)  # system, assistant, user
    content = Column(Text, nullable=False)
    message_type = Column(String(30), default="chat")  # chat, question, answer, feedback, code
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="conversations")


# ─── Gamification ──────────────────────────────────────────────
class UserXP(Base):
    __tablename__ = "user_xp"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    xp_total = Column(Integer, default=0)
    level = Column(Integer, default=1)
    streak_days = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_active_date = Column(String(10), default="")
    lessons_completed = Column(Integer, default=0)
    quizzes_passed = Column(Integer, default=0)
    homework_completed = Column(Integer, default=0)

    user = relationship("User", back_populates="xp_record")


class Badge(Base):
    __tablename__ = "badges"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), default="")
    icon = Column(String(10), default="🏅")
    criteria_type = Column(String(50), default="")  # xp, lessons, streak, quiz
    criteria_value = Column(Integer, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    earned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="badges")
    badge = relationship("Badge")


# ─── Quiz ──────────────────────────────────────────────────────
class QuizResult(Base):
    __tablename__ = "quiz_results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    question = Column(Text, nullable=False)
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    is_correct = Column(Boolean, default=False)
    xp_earned = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="quiz_results")


# ─── Homework ──────────────────────────────────────────────────
class Homework(Base):
    __tablename__ = "homework"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    difficulty = Column(String(20), default="medium")
    max_score = Column(Integer, default=100)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    submissions = relationship("HomeworkSubmission", back_populates="homework")


class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"
    id = Column(Integer, primary_key=True, index=True)
    homework_id = Column(Integer, ForeignKey("homework.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, default="")
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    grade = Column(Float, nullable=True)
    feedback = Column(Text, default="")
    is_graded = Column(Boolean, default=False)

    homework = relationship("Homework", back_populates="submissions")
    user = relationship("User", back_populates="homework_submissions")


# ─── Recommendations ──────────────────────────────────────────
class LessonRecommendation(Base):
    __tablename__ = "lesson_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    reason = Column(String(255), default="")
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── JARVIS Intelligence Models ────────────────────────────────
class StudentInsight(Base):
    __tablename__ = "student_insights"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    insight_type = Column(String(50), nullable=False)  # strength, weakness, pattern, motivation
    content = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="insights")


class StudySession(Base):
    __tablename__ = "study_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    duration_minutes = Column(Integer, default=0)
    focus_score = Column(Integer, default=100)  # 0-100
    concepts_mastered = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="study_sessions")


# ─── Database Initialization ──────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_data():
    """Seed the database with initial courses, lessons and badges."""
    db = SessionLocal()
    try:
        # Seed test user for ephemeral serverless environments
        if db.query(User).filter(User.username == "test").count() == 0:
            import bcrypt
            pwd = "test".encode('utf-8')
            hashed = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')
            test_user = User(
                username="test",
                email="test@example.com",
                password_hash=hashed,
                full_name="Dissertation Tester",
                role="student",
                avatar="🧑‍🎓"
            )
            db.add(test_user)
            db.flush()
            xp = UserXP(user_id=test_user.id)
            db.add(xp)
            db.commit()
            print("✅ Test user seeded successfully.")

        # Check if already seeded with content
        if db.query(Course).count() > 0:
            return

        # ── Courses ──
        courses_data = [
            {
                "title": "Python Programming",
                "description": "Learn Python from scratch - variables, loops, functions, OOP and real-world projects!",
                "icon": "🐍",
                "category": "Programming",
                "difficulty": "beginner",
                "lessons": [
                    {"title": "What is Python? - Your First Program", "order_num": 1, "difficulty": "beginner", "estimated_minutes": 15,
                     "key_concepts": '["What is Python", "Why learn Python", "Installing Python", "Hello World program", "print() function"]',
                     "content": "Welcome to Python! Python is one of the most popular programming languages in the world. It was created by Guido van Rossum in 1991. Python is known for being easy to read and write - it's almost like writing in English! Companies like Google, Netflix, Instagram, and NASA use Python. Let's write your very first program!",
                     "examples": '["print(\\"Hello, World!\\")", "print(\\"My name is Python!\\")", "print(3 + 5)", "print(\\"I am\\", 10, \\"years old\\")"]'},
                    {"title": "Variables & Data Types", "order_num": 2, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["Variables", "Strings", "Integers", "Floats", "Booleans", "type() function", "Variable naming rules"]',
                     "content": "Variables are like labeled boxes where you store information. In Python, you don't need to declare a type - Python figures it out! There are several data types: strings (text), integers (whole numbers), floats (decimal numbers), and booleans (True/False).",
                     "examples": '["name = \\"Alice\\"\\nprint(name)", "age = 12\\nprint(type(age))", "height = 4.5\\nprint(height)", "is_student = True\\nprint(is_student)"]'},
                    {"title": "Input & Output", "order_num": 3, "difficulty": "beginner", "estimated_minutes": 15,
                     "key_concepts": '["input() function", "String concatenation", "f-strings", "Type conversion", "int()", "float()"]',
                     "content": "Programs become interactive when they can take input from users! The input() function lets us ask questions and store answers. We can combine strings using + or f-strings for cleaner output.",
                     "examples": '["name = input(\\"What is your name? \\")\\nprint(\\"Hello, \\" + name)", "age = int(input(\\"Your age: \\"))\\nprint(f\\"Next year you\'ll be {age + 1}\\")", "a = float(input(\\"Enter a number: \\"))\\nprint(f\\"Double: {a * 2}\\")"]'},
                    {"title": "Conditionals - If/Else", "order_num": 4, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["if statement", "else statement", "elif statement", "Comparison operators", "Logical operators", "Nested conditions"]',
                     "content": "Conditionals let your program make decisions! Just like you decide what to wear based on weather, Python can make choices using if, elif, and else. We use comparison operators (==, !=, >, <, >=, <=) and logical operators (and, or, not).",
                     "examples": '["age = 15\\nif age >= 18:\\n    print(\\"You can vote!\\")\\nelse:\\n    print(\\"Too young to vote\\")", "score = 85\\nif score >= 90:\\n    print(\\"Grade: A\\")\\nelif score >= 80:\\n    print(\\"Grade: B\\")\\nelse:\\n    print(\\"Keep trying!\\")"]'},
                    {"title": "Loops - For & While", "order_num": 5, "difficulty": "beginner", "estimated_minutes": 25,
                     "key_concepts": '["for loop", "while loop", "range() function", "break statement", "continue statement", "Loop patterns"]',
                     "content": "Loops let you repeat code without writing it over and over! The for loop iterates over a sequence, and the while loop runs as long as a condition is true. These are super powerful tools in programming!",
                     "examples": '["for i in range(5):\\n    print(f\\"Count: {i}\\")", "fruits = [\\"apple\\", \\"banana\\", \\"cherry\\"]\\nfor fruit in fruits:\\n    print(fruit)", "count = 0\\nwhile count < 5:\\n    print(count)\\n    count += 1"]'},
                    {"title": "Lists & Tuples", "order_num": 6, "difficulty": "intermediate", "estimated_minutes": 25,
                     "key_concepts": '["Creating lists", "List indexing", "List methods", "append(), remove(), sort()", "Tuples", "List slicing", "List comprehension"]',
                     "content": "Lists are ordered collections that can hold multiple items. Think of a list like a shopping list - you can add items, remove items, and organize them. Tuples are similar but immutable (can't be changed after creation).",
                     "examples": '["colors = [\\"red\\", \\"green\\", \\"blue\\"]\\ncolors.append(\\"yellow\\")\\nprint(colors)", "numbers = [3, 1, 4, 1, 5, 9]\\nnumbers.sort()\\nprint(numbers)", "squares = [x**2 for x in range(10)]\\nprint(squares)"]'},
                    {"title": "Functions", "order_num": 7, "difficulty": "intermediate", "estimated_minutes": 25,
                     "key_concepts": '["def keyword", "Parameters", "Return values", "Default arguments", "Scope", "Docstrings"]',
                     "content": "Functions are reusable blocks of code that perform specific tasks. Instead of writing the same code multiple times, you create a function and call it whenever needed. Think of functions like recipes - they have ingredients (parameters) and produce results (return values).",
                     "examples": '["def greet(name):\\n    return f\\"Hello, {name}!\\"\\n\\nprint(greet(\\"Alice\\"))", "def add(a, b):\\n    return a + b\\n\\nresult = add(3, 5)\\nprint(result)", "def is_even(n):\\n    return n % 2 == 0\\n\\nprint(is_even(4))"]'},
                    {"title": "Dictionaries", "order_num": 8, "difficulty": "intermediate", "estimated_minutes": 20,
                     "key_concepts": '["Key-value pairs", "Creating dictionaries", "Accessing values", "Dictionary methods", "Nested dictionaries", "Looping through dicts"]',
                     "content": "Dictionaries store data in key-value pairs, like a real dictionary where words (keys) have definitions (values). They're incredibly useful for organizing related data!",
                     "examples": '["student = {\\"name\\": \\"Alice\\", \\"age\\": 15, \\"grade\\": \\"A\\"}\\nprint(student[\\"name\\"])", "student[\\"school\\"] = \\"ABC High\\"\\nprint(student)", "for key, value in student.items():\\n    print(f\\"{key}: {value}\\")"]'},
                    {"title": "File Handling", "order_num": 9, "difficulty": "intermediate", "estimated_minutes": 20,
                     "key_concepts": '["open() function", "Reading files", "Writing files", "with statement", "File modes", "CSV basics"]',
                     "content": "Programs often need to read from and write to files. Python makes file handling easy! You can read text files, write data, and even work with CSV files. The 'with' statement ensures files are properly closed.",
                     "examples": '["with open(\\"hello.txt\\", \\"w\\") as f:\\n    f.write(\\"Hello World!\\")", "with open(\\"hello.txt\\", \\"r\\") as f:\\n    content = f.read()\\n    print(content)"]'},
                    {"title": "Object-Oriented Programming", "order_num": 10, "difficulty": "advanced", "estimated_minutes": 30,
                     "key_concepts": '["Classes", "Objects", "self keyword", "__init__ method", "Methods", "Attributes", "Inheritance"]',
                     "content": "OOP lets you create your own data types called classes. Think of a class as a blueprint - like a blueprint for a car. Each car (object) made from that blueprint has the same features but different specific values (color, speed, etc).",
                     "examples": '["class Dog:\\n    def __init__(self, name, breed):\\n        self.name = name\\n        self.breed = breed\\n\\n    def bark(self):\\n        return f\\"{self.name} says Woof!\\"\\n\\nrex = Dog(\\"Rex\\", \\"Labrador\\")\\nprint(rex.bark())"]'},
                    {"title": "Real-World Project: Quiz Game", "order_num": 11, "difficulty": "advanced", "estimated_minutes": 35,
                     "key_concepts": '["Project planning", "Combining concepts", "Error handling", "User experience", "Code organization"]',
                     "content": "Now let's put everything together! We'll build a real quiz game that uses variables, lists, dictionaries, functions, loops, and conditionals. This is how real programmers work - combining all the tools they've learned!",
                     "examples": '["# Full Quiz Game Project\\ndef run_quiz():\\n    questions = [\\n        {\\"q\\": \\"What is 2+2?\\", \\"a\\": \\"4\\"},\\n        {\\"q\\": \\"Capital of France?\\", \\"a\\": \\"Paris\\"}\\n    ]\\n    score = 0\\n    for item in questions:\\n        answer = input(item[\\"q\\"] + \\" \\")\\n        if answer.lower() == item[\\"a\\"].lower():\\n            score += 1\\n            print(\\"Correct! ✅\\")\\n        else:\\n            print(f\\"Wrong! Answer: {item[\\"a\\"]}\\")\\n    print(f\\"Score: {score}/{len(questions)}\\")"]'},
                ]
            },
            {
                "title": "Machine Learning Basics",
                "description": "Introduction to ML concepts, supervised/unsupervised learning, and building your first model!",
                "icon": "🤖",
                "category": "AI/ML",
                "difficulty": "intermediate",
                "lessons": [
                    {"title": "What is Machine Learning?", "order_num": 1, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["What is ML", "Types of ML", "Supervised learning", "Unsupervised learning", "Reinforcement learning", "Real-world applications"]',
                     "content": "Machine Learning is a type of AI that lets computers learn from data without being explicitly programmed. Instead of writing rules, we show the computer examples and it figures out the patterns!",
                     "examples": '["# Conceptual example\\n# Traditional: if email contains \\"free money\\" -> spam\\n# ML: Show 1000 spam & 1000 good emails -> model learns patterns"]'},
                    {"title": "Data & Features", "order_num": 2, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["Datasets", "Features", "Labels", "Training data", "Test data", "Data cleaning", "NumPy basics"]',
                     "content": "Data is the fuel of ML! Features are the input variables (like height, weight) and labels are what we're trying to predict (like healthy/unhealthy). Good data = good model!",
                     "examples": '["import numpy as np\\n\\n# Features: [height, weight]\\ndata = np.array([[170, 70], [160, 55], [180, 85]])\\nlabels = np.array([\\"medium\\", \\"light\\", \\"heavy\\"])"]'},
                    {"title": "Your First ML Model", "order_num": 3, "difficulty": "intermediate", "estimated_minutes": 25,
                     "key_concepts": '["scikit-learn", "Train/test split", "Model training", "Predictions", "Accuracy"]',
                     "content": "Let's build your first ML model! We'll use scikit-learn to create a simple classifier. The process is: prepare data → split into train/test → train model → make predictions → check accuracy.",
                     "examples": '["from sklearn.model_selection import train_test_split\\nfrom sklearn.tree import DecisionTreeClassifier\\n\\nX_train, X_test, y_train, y_test = train_test_split(X, y)\\nmodel = DecisionTreeClassifier()\\nmodel.fit(X_train, y_train)\\nprint(f\\"Accuracy: {model.score(X_test, y_test)}\\")"]'},
                    {"title": "Neural Networks Introduction", "order_num": 4, "difficulty": "intermediate", "estimated_minutes": 30,
                     "key_concepts": '["Neurons", "Layers", "Activation functions", "Forward pass", "PyTorch basics"]',
                     "content": "Neural networks are inspired by the human brain! They have layers of 'neurons' that process information. Input goes in one side, gets transformed through hidden layers, and predictions come out the other side.",
                     "examples": '["import torch\\nimport torch.nn as nn\\n\\nmodel = nn.Sequential(\\n    nn.Linear(2, 8),\\n    nn.ReLU(),\\n    nn.Linear(8, 1),\\n    nn.Sigmoid()\\n)\\nprint(model)"]'},
                    {"title": "Reinforcement Learning", "order_num": 5, "difficulty": "advanced", "estimated_minutes": 30,
                     "key_concepts": '["Agent", "Environment", "State", "Action", "Reward", "Policy", "Q-Learning basics"]',
                     "content": "RL is how robots and game AIs learn! An agent takes actions in an environment and receives rewards. Over time, it learns which actions lead to the best outcomes - just like training a pet with treats!",
                     "examples": '["# Simple Q-Learning concept\\nimport numpy as np\\n\\nQ = np.zeros((5, 3))  # 5 states, 3 actions\\n# Agent explores, gets rewards, updates Q-table\\n# Q[state, action] += lr * (reward + gamma * max(Q[next_state]) - Q[state, action])"]'},
                ]
            },
            {
                "title": "Web Development",
                "description": "Build websites from scratch with HTML, CSS, JavaScript and modern frameworks!",
                "icon": "🌐",
                "category": "Web Development",
                "difficulty": "beginner",
                "lessons": [
                    {"title": "HTML - The Skeleton of the Web", "order_num": 1, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["What is HTML", "Tags", "Elements", "Attributes", "Page structure", "Common tags"]',
                     "content": "HTML (HyperText Markup Language) is the foundation of every website. Think of it as the skeleton - it provides the structure. Everything you see on a webpage starts with HTML!",
                     "examples": '["<!DOCTYPE html>\\n<html>\\n<head>\\n    <title>My Page</title>\\n</head>\\n<body>\\n    <h1>Hello World!</h1>\\n    <p>This is my first webpage.</p>\\n</body>\\n</html>"]'},
                    {"title": "CSS - Making Things Beautiful", "order_num": 2, "difficulty": "beginner", "estimated_minutes": 25,
                     "key_concepts": '["What is CSS", "Selectors", "Properties", "Colors", "Box model", "Flexbox basics"]',
                     "content": "CSS (Cascading Style Sheets) is what makes websites look beautiful! If HTML is the skeleton, CSS is the skin, clothes, and makeup. You can change colors, fonts, sizes, layouts and so much more!",
                     "examples": '["body {\\n    background-color: #1a1a2e;\\n    color: white;\\n    font-family: Arial;\\n}\\n\\nh1 {\\n    color: #e94560;\\n    text-align: center;\\n}"]'},
                    {"title": "JavaScript - Making Things Interactive", "order_num": 3, "difficulty": "beginner", "estimated_minutes": 25,
                     "key_concepts": '["What is JavaScript", "Variables (let, const)", "Functions", "DOM manipulation", "Events"]',
                     "content": "JavaScript brings websites to life! It's the programming language of the web that makes things interactive - click buttons, show animations, update content without refreshing the page.",
                     "examples": '["document.getElementById(\\"btn\\").addEventListener(\\"click\\", () => {\\n    alert(\\"You clicked me!\\");\\n});"]'},
                    {"title": "Building a FastAPI Backend", "order_num": 4, "difficulty": "intermediate", "estimated_minutes": 30,
                     "key_concepts": '["What is an API", "REST concepts", "FastAPI basics", "Routes", "Request/Response"]',
                     "content": "A backend is the server-side of a web application. FastAPI is a modern Python framework for building APIs quickly. It's fast, easy to learn, and perfect for connecting your frontend to databases and AI!",
                     "examples": '["from fastapi import FastAPI\\n\\napp = FastAPI()\\n\\n@app.get(\\"/\\")\\ndef read_root():\\n    return {\\"message\\": \\"Hello World!\\"}\\n\\n@app.get(\\"/users/{user_id}\\")\\ndef read_user(user_id: int):\\n    return {\\"user_id\\": user_id}"]'},
                ]
            },
            {
                "title": "Data Science with Python",
                "description": "Analyze data, create visualizations, and tell stories with numbers!",
                "icon": "📊",
                "category": "Data Science",
                "difficulty": "intermediate",
                "lessons": [
                    {"title": "NumPy - The Foundation", "order_num": 1, "difficulty": "beginner", "estimated_minutes": 20,
                     "key_concepts": '["Arrays", "Array operations", "Shapes", "Mathematical functions", "Broadcasting"]',
                     "content": "NumPy is the fundamental package for numerical computing in Python. It provides powerful array objects that are much faster than Python lists for mathematical operations.",
                     "examples": '["import numpy as np\\n\\narr = np.array([1, 2, 3, 4, 5])\\nprint(arr * 2)  # [2, 4, 6, 8, 10]\\nprint(np.mean(arr))  # 3.0"]'},
                    {"title": "Pandas - Data Wrangling", "order_num": 2, "difficulty": "intermediate", "estimated_minutes": 25,
                     "key_concepts": '["DataFrames", "Reading CSV", "Filtering", "Grouping", "Missing data"]',
                     "content": "Pandas is the most popular data manipulation library. DataFrames are like spreadsheets in Python - you can filter, sort, group, and transform data easily!",
                     "examples": '["import pandas as pd\\n\\ndf = pd.DataFrame({\\"name\\": [\\"Alice\\", \\"Bob\\"], \\"score\\": [95, 87]})\\nprint(df[df[\\"score\\"] > 90])"]'},
                    {"title": "Data Visualization", "order_num": 3, "difficulty": "intermediate", "estimated_minutes": 25,
                     "key_concepts": '["Matplotlib", "Bar charts", "Line plots", "Scatter plots", "Customization"]',
                     "content": "Visualization turns numbers into pictures! A good chart can tell a story that a table of numbers can't. We'll learn to create beautiful charts with Matplotlib.",
                     "examples": '["import matplotlib.pyplot as plt\\n\\nplt.bar([\\"Python\\", \\"Java\\", \\"JS\\"], [85, 70, 90])\\nplt.title(\\"Language Popularity\\")\\nplt.show()"]'},
                ]
            },
        ]

        for course_data in courses_data:
            lessons_data = course_data.pop("lessons")
            course = Course(**course_data)
            db.add(course)
            db.flush()

            for lesson_data in lessons_data:
                lesson = Lesson(course_id=course.id, **lesson_data)
                db.add(lesson)

        # ── Badges ──
        badges_data = [
            {"name": "First Steps", "description": "Complete your first lesson", "icon": "👣", "criteria_type": "lessons", "criteria_value": 1},
            {"name": "Fast Learner", "description": "Complete 5 lessons", "icon": "⚡", "criteria_type": "lessons", "criteria_value": 5},
            {"name": "Knowledge Seeker", "description": "Complete 10 lessons", "icon": "📖", "criteria_type": "lessons", "criteria_value": 10},
            {"name": "Scholar", "description": "Complete 25 lessons", "icon": "🎓", "criteria_type": "lessons", "criteria_value": 25},
            {"name": "Quiz Whiz", "description": "Pass 5 quizzes", "icon": "🧠", "criteria_type": "quiz", "criteria_value": 5},
            {"name": "Quiz Master", "description": "Pass 20 quizzes", "icon": "🏆", "criteria_type": "quiz", "criteria_value": 20},
            {"name": "Streak Starter", "description": "3-day learning streak", "icon": "🔥", "criteria_type": "streak", "criteria_value": 3},
            {"name": "Week Warrior", "description": "7-day learning streak", "icon": "💪", "criteria_type": "streak", "criteria_value": 7},
            {"name": "Dedicated Learner", "description": "30-day learning streak", "icon": "🌟", "criteria_type": "streak", "criteria_value": 30},
            {"name": "XP Hunter", "description": "Earn 500 XP", "icon": "💎", "criteria_type": "xp", "criteria_value": 500},
            {"name": "XP Champion", "description": "Earn 2000 XP", "icon": "👑", "criteria_type": "xp", "criteria_value": 2000},
            {"name": "Homework Hero", "description": "Complete 10 homework assignments", "icon": "📝", "criteria_type": "homework", "criteria_value": 10},
            {"name": "Python Beginner", "description": "Complete first Python lesson", "icon": "🐍", "criteria_type": "lessons", "criteria_value": 1},
            {"name": "AI Explorer", "description": "Start an ML course", "icon": "🤖", "criteria_type": "lessons", "criteria_value": 1},
        ]

        for badge_data in badges_data:
            db.add(Badge(**badge_data))

        # ── Homework Assignments ──
        # Get course IDs for linking
        python_course = db.query(Course).filter(Course.title == "Python Programming").first()
        ml_course = db.query(Course).filter(Course.title == "Machine Learning Basics").first()
        web_course = db.query(Course).filter(Course.title == "Web Development").first()

        homework_data = [
            {"title": "Python Variables Challenge", "description": "Create a program that stores your name, age, and favorite subject in variables, then prints a formatted introduction using f-strings.", "difficulty": "easy", "max_score": 100, "course_id": python_course.id if python_course else None, "assigned_by": 1},
            {"title": "Loop Patterns", "description": "Write a program that prints a triangle pattern using nested for loops. The triangle should have 5 rows, with each row having an increasing number of stars (*).  ", "difficulty": "medium", "max_score": 100, "course_id": python_course.id if python_course else None, "assigned_by": 1},
            {"title": "Build a Calculator", "description": "Create a simple calculator that takes two numbers and an operator (+, -, *, /) from the user. Handle division by zero gracefully and use functions for each operation.", "difficulty": "medium", "max_score": 100, "course_id": python_course.id if python_course else None, "assigned_by": 1},
            {"title": "ML Concepts Essay", "description": "Write a short essay (200-300 words) explaining the difference between supervised and unsupervised learning. Include at least 2 real-world examples for each type.", "difficulty": "easy", "max_score": 100, "course_id": ml_course.id if ml_course else None, "assigned_by": 1},
            {"title": "Personal Portfolio Page", "description": "Create a simple HTML page with CSS styling that serves as your personal portfolio. Include: a header with your name, an about section, a skills list, and a contact section.", "difficulty": "medium", "max_score": 100, "course_id": web_course.id if web_course else None, "assigned_by": 1},
        ]

        for hw_data in homework_data:
            db.add(Homework(**hw_data))

        db.commit()
        print("✅ Database seeded with courses, lessons, badges, and homework!")

    except Exception as e:
        db.rollback()
        print(f"⚠️ Seed error: {e}")
    finally:
        db.close()
