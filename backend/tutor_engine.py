"""
AI Tutor Engine - The brain of the Virtual Classroom

This engine simulates a REAL teacher:
1. Starts from scratch with a topic
2. Teaches progressively (basics → advanced)
3. Uses examples and real-world scenarios
4. Asks comprehension questions during teaching
5. Evaluates student answers with appreciation or correction
6. Adapts difficulty based on understanding
7. Gives quizzes at the end of lessons
8. Generates custom courses from topics or uploaded files
9. Includes video and image resources in teaching
10. Returns STRUCTURED JSON for reliable progress tracking
"""
import json
import os
import re
from openai import OpenAI
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from config import OPENAI_API_KEY, OPENAI_MODEL
from models import (
    ConversationHistory, StudentProgress, Lesson, Course,
    UserXP, QuizResult, TutorState, LessonStatus
)
from jarvis_brain import JarvisBrain
from rl_engine.rl_inference import RLEngineInference

rl_engine = RLEngineInference.get_instance()

# Lazy OpenAI client — reads key at request time (not module import time)
_openai_client = None
_openai_client_key = None

def _get_client():
    """Lazily create / refresh OpenAI client, reading key from env each call."""
    global _openai_client, _openai_client_key
    key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY
    if not key or not key.strip() or key.startswith("your-"):
        return None
    # Recreate client if key changed
    if key != _openai_client_key:
        _openai_client = OpenAI(api_key=key.strip())
        _openai_client_key = key
    return _openai_client

# ─── System Prompts ────────────────────────────────────────────

TUTOR_SYSTEM_PROMPT = """You are "JARVIS" — a brilliant, witty, and highly proactive smart teaching assistant.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR PERSONALITY (JARVIS MODE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- You are an advanced AI assistant tailored to the student. You don't just teach; you OBSERVE and ADAPT.
- Tone: Warm, highly intelligent, slightly witty (like JARVIS from Iron Man or a friendly mentor).
- You are a REAL teacher who SPEAKS to the student — your text will be read aloud by text-to-speech
- Talk naturally, conversationally — as if standing in front of the student.
- Use phrases like: "Sir/Miss, if I may suggest...", "Fascinating progress here...", "Let me project an example..."
- Give vivid REAL-WORLD examples that paint a picture in the student's mind.
- If the student seems confused, be incredibly patient and offer a completely different analogy.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TEACHING FLOW (FOLLOW STRICTLY!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You MUST follow this structured flow for EVERY concept:

**Phase 1 — HOOK** (first message of a lesson):
  "Hey [name]! Today we're going to explore something fascinating..."
  Start with a SURPRISING fact, question, or real-world scenario that grabs attention.

**Phase 2 — TEACH**:
  - Explain ONE concept using everyday language and analogies FIRST
  - Then give the formal/technical definition
  - Show a code example or real scenario to demonstrate
  - Include a [VISUAL_ANIMATION: ...] or [VISUAL_DIAGRAM: ...] tag
  - Walk through the visual: "Notice how... That's because..."

**Phase 3 — CHECK UNDERSTANDING**:
  - Ask an OPEN-ENDED question: "Okay, now tell me — in your own words, what does X do?"
  - Or a scenario: "If I gave you Y, what would happen?"
  - DO NOT give options. Let the student think and answer freely.
  - END your message with the question. STOP. Wait for their answer.

**Phase 4 — FEEDBACK** (after student responds):
  - If CORRECT: "That's EXACTLY right! Great thinking! 🌟" — genuinely celebrate, then show a real-world application
  - If PARTIALLY correct: "You're on the right track! Let me add to that..." — acknowledge what's right, fill in the gaps
  - If INCORRECT: "That's a really common misconception! Let me explain it differently..." — be GENTLE, re-explain with a DIFFERENT analogy, then ask a simpler version of the question
  - If student asks their own question: Answer it helpfully, then continue the flow

**Phase 5 — ADVANCE**:
  - After correct understanding, move to the NEXT concept and repeat phases 2-4
  - If all concepts are covered, give a SUMMARY of everything learned, congratulate warmly, and suggest the quiz

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI-GENERATED VISUALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Include visual tags to generate real-time AI visuals:
**For animations**: [VISUAL_ANIMATION: brief description]
**For diagrams**: [VISUAL_DIAGRAM: brief description]
Include at least ONE visual per concept. Place it right after explaining the concept.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NEVER dump information. Teach ONE concept at a time, interactively.
- After explaining a concept, ALWAYS ask a question before moving on.
- When asking a question, END your message there. DO NOT continue.
- Keep paragraphs SHORT (1-3 sentences) because text is spoken aloud.
- Format code in markdown code blocks with language spec.
- Use markdown: headers, bold, code blocks, bullet points.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE FORMAT (MANDATORY!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You MUST respond with valid JSON in this exact format:
```json
{
  "message": "Your full teaching message in markdown...",
  "phase": "teaching|questioning|feedback|summary",
  "is_correct": true | false | null,
  "concept_mastered": true | false,
  "encouragement": "high|medium|low",
  "next_action": "wait_for_answer|continue_teaching|lesson_complete"
}
```

- `message`: Your full teaching response (markdown formatted)
- `phase`: Current teaching phase
- `is_correct`: Whether the student's last answer was correct (null if not evaluating an answer)
- `concept_mastered`: Whether the current concept is now understood
- `encouragement`: How much encouragement the student needs
- `next_action`: What happens next

Return ONLY the JSON object. No other text outside the JSON.
"""


QUIZ_GENERATOR_PROMPT = """You are a quiz generator for an educational platform. Generate quiz questions based on the lesson content provided.

Return a JSON array of quiz questions. Each question should have:
- "question": The question text
- "options": Array of 4 options (strings)
- "correct": Index of correct option (0-3)  
- "explanation": Brief explanation of the correct answer
- "difficulty": "easy", "medium", or "hard"

Generate exactly {count} questions. Mix difficulties. Make questions test real understanding, not just memorization.
Return ONLY the JSON array, no other text.
"""


HOMEWORK_GRADER_PROMPT = """You are an AI homework grader. Evaluate the student's homework submission.

Lesson Topic: {topic}
Homework Assignment: {assignment}
Student's Submission: {submission}

Provide:
1. A score from 0-100
2. Detailed feedback (what was good, what needs improvement)
3. Suggestions for further learning

Return as JSON:
{{
    "score": <number>,
    "feedback": "<detailed feedback>",
    "strengths": ["<strength1>", "<strength2>"],
    "improvements": ["<improvement1>", "<improvement2>"],
    "suggestions": "<what to study next>"
}}
"""


RECOMMENDATION_PROMPT = """Based on the student's learning history, recommend the next best lessons.

Student Profile:
- Completed lessons: {completed}
- Current performance: {performance}%
- Weak areas: {weak_areas}
- Strong areas: {strong_areas}

Available courses and lessons:
{available}

Recommend 3-5 lessons with reasons. Return as JSON array:
[{{"lesson_id": <id>, "reason": "<why this is recommended>", "priority": <1-5>}}]
Return ONLY the JSON array.
"""


COURSE_GENERATOR_PROMPT = """You are a course designer. Create a concise structured course on the given topic.

CREATE EXACTLY 3-4 LESSONS. Keep content brief but educational.

Return a JSON object with EXACTLY this structure (no extra text, no markdown):
{{"title": "Course Title", "description": "1-2 sentence description.", "icon": "emoji", "category": "Category", "difficulty": "beginner", "lessons": [{{"title": "Lesson Title", "order_num": 1, "difficulty": "beginner", "estimated_minutes": 15, "content": "2-3 paragraph explanation of the topic.", "key_concepts": ["concept1", "concept2", "concept3"], "examples": ["example1", "example2"], "video_search": "youtube search query"}}]}}

Return ONLY the JSON. No markdown fences. No extra text.
"""


TEXTBOOK_ANALYZER_PROMPT = """You are an expert course designer. Analyze the following document/textbook content and create a structured educational course from it.

DOCUMENT CONTENT:
{text_content}

INSTRUCTIONS:
- Identify the major topics and create 5-10 lessons from them
- Each lesson should cover one major topic/section from the document
- Include the key concepts, examples, and teaching content derived from the text
- Make lessons progressive (easy to hard)
- Add engaging descriptions and real-world context
- If the document is about a technical topic, include code examples where relevant

Return a JSON object with EXACTLY this structure:
{{
    "title": "Course Title (derived from document)",
    "description": "2-3 sentence course description",
    "icon": "single relevant emoji", 
    "category": "Category Name",
    "difficulty": "beginner",
    "lessons": [
        {{
            "title": "Lesson Title",
            "order_num": 1,
            "difficulty": "beginner",
            "estimated_minutes": 15,
            "content": "Detailed teaching content derived from the document...",
            "key_concepts": ["concept1", "concept2", "concept3"],
            "examples": ["example 1", "example 2"],
            "video_search": "youtube search query for this topic"
        }}
    ]
}}

Return ONLY valid JSON. No markdown, no explanation.
"""


# ─── Tutor Engine Class ───────────────────────────────────────

class TutorEngine:
    """Main AI Tutor that teaches like a real teacher with structured JSON responses."""

    @staticmethod
    def _call_ai(messages: list, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Call OpenAI API with messages."""
        client = _get_client()
        if not client:
            return TutorEngine._fallback_response(messages)
        
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=55,  # Increased to match 60s limit with 5s buffer
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                print("[AI] Warning: Empty response from OpenAI")
                return TutorEngine._fallback_response(messages)
            return content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return TutorEngine._fallback_response(messages)

    @staticmethod
    def _fallback_response(messages: list) -> str:
        """Fallback when API is not available — returns structured JSON."""
        return json.dumps({
            "message": (
                "🎓 **Professor AI is here!**\n\n"
                "I'd love to teach you, but my AI brain needs an API key to work at full power! "
                "Please add your OpenAI API key in the `.env` file:\n\n"
                "```\nOPENAI_API_KEY=your-key-here\n```\n\n"
                "Once configured, I'll be able to:\n"
                "- 📚 Teach you interactively\n"
                "- ❓ Ask comprehension questions\n"
                "- ✅ Grade your answers\n"
                "- 🧠 Adapt to your learning pace\n\n"
                "*In the meantime, the lesson content and quizzes still work!*"
            ),
            "phase": "teaching",
            "is_correct": None,
            "concept_mastered": False,
            "encouragement": "medium",
            "next_action": "continue_teaching"
        })

    @staticmethod
    def _parse_tutor_response(raw: str) -> dict:
        """Parse the structured JSON response from the tutor AI.
        Falls back gracefully if the AI returns plain text instead of JSON."""
        try:
            text = raw.strip()
            # Remove markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:]  # Remove opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            
            # Try to find JSON object
            brace_start = text.find("{")
            if brace_start >= 0:
                # Find the matching closing brace
                depth = 0
                for i in range(brace_start, len(text)):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            json_str = text[brace_start:i + 1]
                            return json.loads(json_str)
            
            return json.loads(text)
        except (json.JSONDecodeError, Exception):
            # Fallback: wrap plain text in structured format
            # Use heuristics for phase detection
            is_correct = None
            phase = "teaching"
            concept_mastered = False
            next_action = "continue_teaching"
            
            lower = raw.lower()
            
            # Detect if this is feedback on a correct answer
            correct_markers = ["exactly right", "correct", "great job", "well done", 
                             "perfect", "excellent", "that's right", "spot on", "nice work",
                             "absolutely", "you got it", "brilliant", "🌟", "✅"]
            incorrect_markers = ["not quite", "not exactly", "incorrect", "wrong",
                               "common mistake", "close but", "try again", "let me explain",
                               "actually", "misconception"]
            
            if any(m in lower for m in correct_markers):
                is_correct = True
                phase = "feedback"
                concept_mastered = True
            elif any(m in lower for m in incorrect_markers):
                is_correct = False
                phase = "feedback"
                concept_mastered = False
            
            # Detect if asking a question
            if raw.rstrip().endswith("?"):
                phase = "questioning"
                next_action = "wait_for_answer"
            
            # Detect lesson complete
            if "lesson complete" in lower or "lesson is complete" in lower or "completed the lesson" in lower:
                next_action = "lesson_complete"
                phase = "summary"
            
            return {
                "message": raw,
                "phase": phase,
                "is_correct": is_correct,
                "concept_mastered": concept_mastered,
                "encouragement": "high" if is_correct else ("medium" if is_correct is None else "low"),
                "next_action": next_action
            }

    @staticmethod
    def start_lesson(db: Session, user_id: int, lesson_id: int) -> dict:
        """Start a new lesson - the tutor introduces the topic."""
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return {"error": "Lesson not found"}

        course = db.query(Course).filter(Course.id == lesson.course_id).first()
        
        # Get or create progress
        progress = db.query(StudentProgress).filter(
            StudentProgress.user_id == user_id,
            StudentProgress.lesson_id == lesson_id
        ).first()

        if not progress:
            progress = StudentProgress(
                user_id=user_id,
                course_id=lesson.course_id,
                lesson_id=lesson_id,
                status=LessonStatus.IN_PROGRESS.value,
                tutor_state=TutorState.TEACHING.value,
            )
            db.add(progress)
            db.commit()

        # Get student's name
        from models import User
        user = db.query(User).filter(User.id == user_id).first()
        student_name = user.full_name or user.username if user else "Student"

        # Build the teaching prompt
        concepts = json.loads(lesson.key_concepts) if lesson.key_concepts else []
        examples = json.loads(lesson.examples) if lesson.examples else []

        intro_prompt = f"""You are starting a NEW lesson with {student_name}.

Course: {course.title if course else 'General'}
Lesson: {lesson.title}
Lesson Content: {lesson.content}
Key Concepts to Teach (in order): {json.dumps(concepts)}
Code Examples Available: {json.dumps(examples)}

START teaching! Follow the structured flow:
1. Give a warm, exciting introduction — hook them with WHY this topic matters
2. Teach the FIRST concept: "{concepts[0] if concepts else lesson.title}" using a real-world analogy
3. Include a [VISUAL_ANIMATION: ...] or [VISUAL_DIAGRAM: ...] tag to demonstrate visually
4. Walk through a simple example
5. End with an open-ended comprehension question — then STOP and wait

Remember: You are a real teacher, not a textbook. Make it conversational and fun!

RESPOND WITH THE MANDATORY JSON FORMAT."""

        messages = [
            {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": intro_prompt}
        ]

        raw_response = TutorEngine._call_ai(messages, max_tokens=1000)
        parsed = TutorEngine._parse_tutor_response(raw_response)

        # Save conversation (store just the message text)
        TutorEngine._save_message(db, user_id, lesson_id, "assistant", parsed["message"], "teaching")

        # Update progress
        progress.tutor_state = TutorState.ASKING_QUESTION.value
        progress.current_concept_index = 0
        progress.status = LessonStatus.IN_PROGRESS.value
        db.commit()

        return {
            "message": parsed["message"],
            "phase": parsed.get("phase", "teaching"),
            "next_action": parsed.get("next_action", "wait_for_answer"),
            "encouragement": parsed.get("encouragement", "high"),
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "course": course.title if course else "",
                "total_concepts": len(concepts),
                "current_concept": 0,
                "concepts": concepts,
            },
            "tutor_state": progress.tutor_state,
            "understanding": 0,
        }

    @staticmethod
    def handle_student_response(db: Session, user_id: int, lesson_id: int, student_message: str) -> dict:
        """Process student's response and continue teaching."""
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return {"error": "Lesson not found"}

        progress = db.query(StudentProgress).filter(
            StudentProgress.user_id == user_id,
            StudentProgress.lesson_id == lesson_id
        ).first()

        if not progress:
            return TutorEngine.start_lesson(db, user_id, lesson_id)

        concepts = json.loads(lesson.key_concepts) if lesson.key_concepts else []
        examples = json.loads(lesson.examples) if lesson.examples else []
        course = db.query(Course).filter(Course.id == lesson.course_id).first()

        # Save student message
        TutorEngine._save_message(db, user_id, lesson_id, "user", student_message, "answer")

        # Get conversation history
        history = TutorEngine._get_conversation(db, user_id, lesson_id, limit=20)

        # Build context for AI
        current_idx = progress.current_concept_index
        total_concepts = len(concepts)
        
        next_concept = concepts[current_idx + 1] if current_idx + 1 < total_concepts else "ALL CONCEPTS COVERED"
        current_concept = concepts[current_idx] if current_idx < total_concepts else "All covered"
        
        # --- Reinforcement Learning Engine Action ---
        progress_dict = {
            "understanding": progress.understanding_level,
            "questions_asked": progress.questions_asked,
            "correct_answers": progress.correct_answers
        }
        rl_action, rl_mode, rl_action_idx = rl_engine.get_instructional_action(progress_dict, current_idx)
        
        context = f"""LESSON CONTEXT:
- Lesson: {lesson.title}
- Course: {course.title if course else 'General'}
- Full lesson content: {lesson.content}
- All concepts (in teaching order): {json.dumps(concepts)}
- Code examples: {json.dumps(examples)}
- Currently teaching concept #{current_idx + 1} of {total_concepts}: "{current_concept}"
- Next concept after this: "{next_concept}"
- Student's track record: {progress.correct_answers} correct out of {progress.questions_asked} questions
- Current understanding: {progress.understanding_level}%

THE STUDENT JUST SAID: "{student_message}"

*** RL ENGINE MANDATE ({rl_mode.upper()} Agent selected Action {rl_action_idx}) ***
{rl_action}
**********************************

YOUR JOB:
1. EVALUATE their response — is it correct, partially correct, or incorrect?
2. Observe the RL ENGINE MANDATE above and perform that instructional action exactly.
3. If they're asking their own question → Answer it helpfully, then return to the mandated action.
4. If ALL concepts are now mastered (concept #{current_idx + 1} is correct AND it's the last concept) → Give a warm LESSON SUMMARY, congratulate them, and tell them to take the quiz! Set next_action to "lesson_complete".

RESPOND WITH THE MANDATORY JSON FORMAT."""

        messages = [{"role": "system", "content": TUTOR_SYSTEM_PROMPT}]
        for msg in history[:-1]:  # Exclude the one we just saved
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": context})

        raw_response = TutorEngine._call_ai(messages, max_tokens=1200)
        parsed = TutorEngine._parse_tutor_response(raw_response)

        # Save AI response
        TutorEngine._save_message(db, user_id, lesson_id, "assistant", parsed["message"], "teaching")

        # Update progress based on structured response
        progress.questions_asked += 1
        
        is_correct = parsed.get("is_correct", None)
        concept_mastered = parsed.get("concept_mastered", False)
        
        if is_correct is True:
            progress.correct_answers += 1
            if concept_mastered and current_idx < total_concepts - 1:
                progress.current_concept_index += 1
            elif concept_mastered and current_idx >= total_concepts - 1:
                progress.status = LessonStatus.COMPLETED.value
                progress.completed_at = datetime.now(timezone.utc)

        # Update understanding level
        if progress.questions_asked > 0:
            progress.understanding_level = (progress.correct_answers / progress.questions_asked) * 100

        # Update tutor state based on phase
        phase = parsed.get("phase", "teaching")
        if phase == "questioning":
            progress.tutor_state = TutorState.ASKING_QUESTION.value
        elif phase == "feedback":
            progress.tutor_state = TutorState.GIVING_FEEDBACK.value
        elif phase == "teaching":
            progress.tutor_state = TutorState.TEACHING.value
        
        db.commit()

        lesson_complete = (
            parsed.get("next_action") == "lesson_complete" or 
            progress.status == LessonStatus.COMPLETED.value
        )

        return {
            "message": parsed["message"],
            "phase": parsed.get("phase", "teaching"),
            "is_correct": is_correct,
            "concept_mastered": concept_mastered,
            "encouragement": parsed.get("encouragement", "medium"),
            "next_action": parsed.get("next_action", "continue_teaching"),
            "progress": {
                "current_concept": progress.current_concept_index,
                "total_concepts": total_concepts,
                "questions_asked": progress.questions_asked,
                "correct_answers": progress.correct_answers,
                "understanding": progress.understanding_level,
                "status": progress.status,
            },
            "tutor_state": progress.tutor_state,
            "lesson_complete": lesson_complete,
        }

    @staticmethod
    def generate_quiz(db: Session, lesson_id: int, count: int = 5) -> list:
        """Generate a quiz for the lesson."""
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            return []

        prompt = QUIZ_GENERATOR_PROMPT.format(count=count)
        concepts = json.loads(lesson.key_concepts) if lesson.key_concepts else []
        examples = json.loads(lesson.examples) if lesson.examples else []

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Lesson: {lesson.title}\nContent: {lesson.content}\nKey Concepts: {json.dumps(concepts)}\nExamples: {json.dumps(examples)}"}
        ]

        response = TutorEngine._call_ai(messages, temperature=0.5)
        
        try:
            # Try to extract JSON from response
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            questions = json.loads(text)
            return questions
        except (json.JSONDecodeError, IndexError):
            # Fallback quiz
            return TutorEngine._generate_fallback_quiz(lesson, concepts)

    @staticmethod
    def _generate_fallback_quiz(lesson, concepts: list) -> list:
        """Generate a basic fallback quiz without API."""
        questions = []
        for i, concept in enumerate(concepts[:5]):
            questions.append({
                "question": f"What do you understand about '{concept}' in {lesson.title}?",
                "options": [
                    f"It is a core concept of {lesson.title}",
                    "It is not related to programming",
                    "It is only used in advanced scenarios",
                    "It is deprecated and no longer used"
                ],
                "correct": 0,
                "explanation": f"'{concept}' is indeed a key concept in {lesson.title}.",
                "difficulty": "easy"
            })
        return questions if questions else [{
            "question": f"What is the main topic of this lesson?",
            "options": [lesson.title, "Cooking", "Sports", "Music"],
            "correct": 0,
            "explanation": f"This lesson is about {lesson.title}.",
            "difficulty": "easy"
        }]

    @staticmethod
    def _fallback_course(topic: str) -> dict:
        """Generate a basic demo course when AI is unavailable or times out."""
        return {
            "title": f"Introduction to {topic}",
            "description": f"A foundational course covering the core concepts of {topic}. This course was auto-generated as a demo — connect your OpenAI key for fully AI-written lessons.",
            "icon": "📘",
            "category": "General",
            "difficulty": "beginner",
            "lessons": [
                {
                    "title": f"What is {topic}?",
                    "order_num": 1,
                    "difficulty": "beginner",
                    "estimated_minutes": 15,
                    "content": f"{topic} is an important subject with many real-world applications. In this lesson, we explore the foundational ideas and why {topic} matters. Understanding the basics helps you build a strong foundation before diving into more complex areas.",
                    "key_concepts": [f"Definition of {topic}", "History and context", "Why it matters"],
                    "examples": [f"Example 1: Real-world use of {topic}", f"Example 2: {topic} in everyday life"],
                    "video_search": f"introduction to {topic} for beginners"
                },
                {
                    "title": f"Core Principles of {topic}",
                    "order_num": 2,
                    "difficulty": "beginner",
                    "estimated_minutes": 20,
                    "content": f"Now that we understand what {topic} is, let's examine its core principles. These principles form the building blocks of everything else in {topic}. Mastering them gives you the tools to solve real problems.",
                    "key_concepts": ["Principle 1", "Principle 2", "Principle 3"],
                    "examples": [f"Applying Principle 1 in {topic}", f"Combining principles to solve problems"],
                    "video_search": f"{topic} core concepts explained"
                },
                {
                    "title": f"Practical Applications of {topic}",
                    "order_num": 3,
                    "difficulty": "intermediate",
                    "estimated_minutes": 25,
                    "content": f"This lesson bridges theory and practice. We look at how {topic} is applied in real-world scenarios. You'll learn to think critically and apply what you know to solve authentic challenges.",
                    "key_concepts": ["Real-world use cases", "Problem-solving techniques", "Common mistakes to avoid"],
                    "examples": [f"Case study: {topic} in industry", "Step-by-step walkthrough"],
                    "video_search": f"{topic} practical examples tutorial"
                },
                {
                    "title": f"Advanced {topic} Techniques",
                    "order_num": 4,
                    "difficulty": "intermediate",
                    "estimated_minutes": 30,
                    "content": f"Building on the fundamentals, we now explore more advanced aspects of {topic}. This is where the power of {topic} truly shines — enabling you to tackle complex, multi-step problems with confidence.",
                    "key_concepts": ["Advanced concept 1", "Advanced concept 2", "Optimization strategies"],
                    "examples": ["Advanced example 1", "Integration with other systems"],
                    "video_search": f"advanced {topic} techniques"
                },
                {
                    "title": f"Mastering {topic}: Review and Next Steps",
                    "order_num": 5,
                    "difficulty": "intermediate",
                    "estimated_minutes": 20,
                    "content": f"In this final lesson, we review everything covered in the course and map out a clear path forward. You now have a solid understanding of {topic} — the journey to mastery is just beginning!",
                    "key_concepts": ["Course summary", "Self-assessment", "Resources for continued learning"],
                    "examples": ["Putting it all together", "Building your own project"],
                    "video_search": f"{topic} complete course summary"
                }
            ]
        }



    @staticmethod
    def grade_homework(topic: str, assignment: str, submission: str) -> dict:
        """Grade a homework submission."""
        prompt = HOMEWORK_GRADER_PROMPT.format(
            topic=topic, assignment=assignment, submission=submission
        )
        messages = [
            {"role": "system", "content": "You are an AI homework grader. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        response = TutorEngine._call_ai(messages, temperature=0.3)
        
        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except:
            return {
                "score": 70,
                "feedback": "Your submission has been received. Please check with your teacher for detailed feedback.",
                "strengths": ["Submitted on time"],
                "improvements": ["Add more detail"],
                "suggestions": "Review the lesson material again."
            }

    @staticmethod
    def get_recommendations(db: Session, user_id: int) -> list:
        """Get personalized lesson recommendations."""
        # Get student's completed lessons
        completed = db.query(StudentProgress).filter(
            StudentProgress.user_id == user_id,
            StudentProgress.status == LessonStatus.COMPLETED.value
        ).all()

        completed_ids = [p.lesson_id for p in completed]
        avg_score = sum(p.understanding_level for p in completed) / len(completed) if completed else 0

        # Get all available lessons
        all_lessons = db.query(Lesson).all()
        available = []
        for l in all_lessons:
            if l.id not in completed_ids:
                course = db.query(Course).filter(Course.id == l.course_id).first()
                available.append({
                    "lesson_id": l.id,
                    "title": l.title,
                    "course": course.title if course else "",
                    "difficulty": l.difficulty,
                    "order": l.order_num,
                })

        if not available:
            return []

        # Try AI recommendations
        if _get_client():
            try:
                prompt = RECOMMENDATION_PROMPT.format(
                    completed=json.dumps([{"id": p.lesson_id, "score": p.understanding_level} for p in completed]),
                    performance=round(avg_score, 1),
                    weak_areas="[]",
                    strong_areas="[]",
                    available=json.dumps(available[:20])
                )
                messages = [
                    {"role": "system", "content": "Return valid JSON array only."},
                    {"role": "user", "content": prompt}
                ]
                response = TutorEngine._call_ai(messages, temperature=0.3)
                text = response.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                return json.loads(text)
            except:
                pass

        # Fallback: recommend next uncompleted lessons
        return [{"lesson_id": l["lesson_id"], "reason": f"Next in {l['course']}", "priority": 5 - i}
                for i, l in enumerate(available[:5])]

    @staticmethod
    def _save_message(db: Session, user_id: int, lesson_id: int, role: str, content: str, msg_type: str):
        """Save a message to conversation history."""
        msg = ConversationHistory(
            user_id=user_id,
            lesson_id=lesson_id,
            role=role,
            content=content,
            message_type=msg_type,
        )
        db.add(msg)
        db.commit()

    @staticmethod
    def _get_conversation(db: Session, user_id: int, lesson_id: int, limit: int = 20) -> list:
        """Get recent conversation history."""
        messages = db.query(ConversationHistory).filter(
            ConversationHistory.user_id == user_id,
            ConversationHistory.lesson_id == lesson_id,
        ).order_by(ConversationHistory.timestamp.desc()).limit(limit).all()

        return [{"role": m.role, "content": m.content, "type": m.message_type}
                for m in reversed(messages)]

    # ─── Course Generation ─────────────────────────────────────

    @staticmethod
    def _parse_json_response(response: str) -> dict:
        """Parse JSON from AI response, handling markdown code blocks and extra text."""
        text = response.strip()

        # Strip ```json ... ``` or ``` ... ``` fences
        import re
        fenced = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if fenced:
            text = fenced.group(1).strip()

        # Find first { and last matching }
        brace_start = text.find("{")
        if brace_start >= 0:
            # Walk to find matching closing brace
            depth = 0
            end = -1
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end >= 0:
                return json.loads(text[brace_start:end + 1])

        # Fallback: try the whole text
        return json.loads(text)

    @staticmethod
    def generate_course_from_topic(topic: str, detail: str = "") -> dict:
        """Generate a complete course from a topic description using AI."""
        if not _get_client():
            return TutorEngine._fallback_course(topic)

        user_prompt = f"Create a comprehensive course about: {topic}"
        if detail:
            user_prompt += f"\n\nAdditional details from the student: {detail}"

        messages = [
            {"role": "system", "content": COURSE_GENERATOR_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        # Retry up to 2 times
        last_error = ""
        for attempt in range(2):
            response = TutorEngine._call_ai(messages, temperature=0.7, max_tokens=1500)
            print(f"[Course Gen] Attempt {attempt+1} raw response length: {len(response)}")
            print(f"[Course Gen] Response preview: {response[:300]}")

            # If fallback response was returned (no API / empty), use demo course
            if '"phase"' in response and '"message"' in response:
                print("[Course Gen] Got fallback teaching response instead of course JSON - using demo course")
                return TutorEngine._fallback_course(topic)

            try:
                course_data = TutorEngine._parse_json_response(response)
                if "title" not in course_data or "lessons" not in course_data:
                    last_error = f"Missing required fields. Keys found: {list(course_data.keys())}"
                    print(f"[Course Gen] Validation failed: {last_error}")
                    continue
                return course_data
            except (json.JSONDecodeError, Exception) as e:
                last_error = str(e)
                print(f"[Course Gen] Parse error on attempt {attempt+1}: {e}")
                print(f"[Course Gen] Full response: {response}")

        print(f"[Course Gen] All attempts failed, returning demo course.")
        return TutorEngine._fallback_course(topic)


    @staticmethod
    def generate_course_from_text(text_content: str, title_hint: str = "") -> dict:
        """Generate a complete course from uploaded document text using AI."""
        if not _get_client():
            return {"error": "AI not configured. Add your OpenAI API key to .env file."}

        # Truncate very long texts to fit token limits
        max_chars = 15000
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n\n[Content truncated for processing...]"

        prompt = TEXTBOOK_ANALYZER_PROMPT.format(text_content=text_content)
        if title_hint:
            prompt += f"\n\nThe user suggests the course title: {title_hint}"

        messages = [
            {"role": "system", "content": "You are an expert course designer. Return ONLY valid JSON, no other text."},
            {"role": "user", "content": prompt}
        ]

        last_error = ""
        for attempt in range(2):
            response = TutorEngine._call_ai(messages, temperature=0.5, max_tokens=4000)
            print(f"[Textbook Gen] Attempt {attempt+1} raw length: {len(response)}")
            try:
                course_data = TutorEngine._parse_json_response(response)
                if "title" not in course_data or "lessons" not in course_data:
                    last_error = f"Missing fields: {list(course_data.keys())}"
                    continue
                return course_data
            except (json.JSONDecodeError, Exception) as e:
                last_error = str(e)
                print(f"[Textbook Gen] Parse error on attempt {attempt+1}: {e}")
                print(f"[Textbook Gen] Full response: {response}")

        return {"error": f"AI generated invalid course structure after 2 attempts. Error: {last_error}"}

