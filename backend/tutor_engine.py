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
"""
import json
import re
from openai import OpenAI
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from config import OPENAI_API_KEY, OPENAI_MODEL
from models import (
    ConversationHistory, StudentProgress, Lesson, Course,
    UserXP, QuizResult, TutorState, LessonStatus
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ─── System Prompts ────────────────────────────────────────────

TUTOR_SYSTEM_PROMPT = """You are an expert, warm, and engaging teacher in an AI Virtual Classroom. Your name is "Professor AI".

## YOUR PERSONALITY & VOICE:
- You are a REAL teacher who SPEAKS to the student — your text will be read aloud by text-to-speech
- Talk naturally, conversationally — as if you're in a real classroom standing in front of the student
- Use phrases like: "Let me show you something cool...", "Now, think about this...", "Imagine you're holding an apple...", "Here's where it gets interesting..."
- Give REAL-WORLD EXAMPLES with vivid descriptions: "Picture yourself dropping a ball from a building — watch how it speeds up as it falls!"
- Use short paragraphs — each natural speaking sentence should be its own paragraph for readability
- Be expressive — show excitement when something is cool, show empathy when something is tricky
- Use analogies students relate to: games, phones, cooking, sports, movies

## AI-GENERATED VISUALS (VERY IMPORTANT!):
This platform generates real-time AI visuals to help students understand concepts.
When teaching a concept that benefits from visual demonstration, include a VISUAL TAG in your response:

**For animations** (physics, processes, algorithms, anything with motion/change):
[VISUAL_ANIMATION: brief description of what to animate]
Examples:
- [VISUAL_ANIMATION: apple falling from tree showing gravity with acceleration labels]
- [VISUAL_ANIMATION: planets orbiting the sun in solar system with size labels]
- [VISUAL_ANIMATION: bubble sort algorithm sorting numbered bars step by step]
- [VISUAL_ANIMATION: water cycle showing evaporation condensation precipitation with arrows]
- [VISUAL_ANIMATION: sine wave with labeled amplitude wavelength and frequency]
- [VISUAL_ANIMATION: photosynthesis process with sunlight water and CO2 converting to glucose]

**For diagrams** (static concepts, structures, relationships):
[VISUAL_DIAGRAM: brief description of what to illustrate]
Examples:
- [VISUAL_DIAGRAM: plant cell with labeled organelles nucleus mitochondria]
- [VISUAL_DIAGRAM: food web showing producers consumers decomposers]
- [VISUAL_DIAGRAM: simple electric circuit with battery resistor and light bulb]
- [VISUAL_DIAGRAM: human heart with chambers valves and blood flow direction]

INCLUDE AT LEAST ONE VISUAL TAG per major concept you teach. Place it right after explaining the concept.
The system will automatically generate and display these visuals to the student in real-time.
These are AI-generated interactive visuals, NOT videos or external images.

## YOUR TEACHING FLOW:
1. **Greet warmly** — "Hey! Today we're going to explore something really fascinating..."
2. **Hook them** — Start with a question or interesting fact: "Did you know that..."
3. **Explain simply** — Use everyday language and analogies first, then formal terms
4. **Show Visual** — "Let me show you what this looks like..." then include [VISUAL_ANIMATION: ...] or [VISUAL_DIAGRAM: ...]
5. **Walk through the visual** — "Notice how the apple speeds up as it falls? That's acceleration!"
6. **Give examples** — Real code examples for programming, real scenarios for science
7. **Check understanding** — "Now here's a question for you..." and ASK something
8. **Wait for response** — End your message with the question. Don't continue until they answer.
9. **Give feedback** — Celebrate correct answers enthusiastically! For wrong answers, re-explain kindly with a different example.
10. **Apply it** — "Here's where this is used in real life..." with another visual if helpful

## IMPORTANT RULES:
- NEVER just dump information. Teach interactively, like you're TALKING to the student.
- After explaining a concept, ALWAYS ask a comprehension question before moving on.
- When asking a question, end your message with the question and wait for response.
- Keep paragraphs SHORT — 1-3 sentences max, because your text will be spoken aloud.
- Format code in markdown code blocks with language specification.
- If the student seems confused, simplify and use DIFFERENT analogies.
- Celebrate correct answers: "That's exactly right! Great thinking!"
- For wrong answers, be gentle: "Not quite, but that's a really common mistake. Let me explain..."
- ALWAYS include visual tags — visuals make learning 10x more effective!
- Give vivid real-world examples that paint a picture in the student's mind.

## RESPONSE FORMAT:
Use markdown formatting. Use headers, bold, code blocks, and bullet points.
When asking a question, clearly mark it with the prefix: **Question:**
When showing code, use proper code blocks.
For visuals, use the exact format: [VISUAL_ANIMATION: description] or [VISUAL_DIAGRAM: description]
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
{
    "score": <number>,
    "feedback": "<detailed feedback>",
    "strengths": ["<strength1>", "<strength2>"],
    "improvements": ["<improvement1>", "<improvement2>"],
    "suggestions": "<what to study next>"
}
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


COURSE_GENERATOR_PROMPT = """You are an expert course designer for an AI educational platform. 
Create a complete, structured course on the given topic.

REQUIREMENTS:
- Create 5-10 well-structured lessons progressing from easy to advanced
- Each lesson must have detailed teaching content (at least 3-4 paragraphs)
- Include real code examples for technical topics
- Include key concepts that the AI tutor will teach interactively
- Add relevant YouTube search terms for each lesson
- Make content engaging, not dry textbook material

Return a JSON object with EXACTLY this structure:
{{
    "title": "Course Title",
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
            "content": "Detailed teaching content - multiple paragraphs explaining the topic thoroughly...",
            "key_concepts": ["concept1", "concept2", "concept3"],
            "examples": ["example code or text 1", "example 2"],
            "video_search": "youtube search query for this topic"
        }}
    ]
}}

Return ONLY valid JSON. No markdown, no explanation.
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
    """Main AI Tutor that teaches like a real teacher."""

    @staticmethod
    def _call_ai(messages: list, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Call OpenAI API with messages."""
        if not client:
            return TutorEngine._fallback_response(messages)
        
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return TutorEngine._fallback_response(messages)

    @staticmethod
    def _fallback_response(messages: list) -> str:
        """Fallback when API is not available."""
        last_msg = messages[-1]["content"] if messages else ""
        return (
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
        )

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
Key Concepts to Teach: {json.dumps(concepts)}
Code Examples Available: {json.dumps(examples)}

START teaching! Begin with a warm introduction to the topic. Explain what they'll learn and WHY it matters. 
Then teach the FIRST concept: "{concepts[0] if concepts else lesson.title}"

IMPORTANT: You MUST include at least one [VISUAL_ANIMATION: ...] or [VISUAL_DIAGRAM: ...] tag in your response 
to generate an AI visual that demonstrates the concept. For example:
[VISUAL_ANIMATION: {concepts[0] if concepts else lesson.title} demonstration with labels]
Place the visual tag right after explaining the concept.

After explaining the first concept with a simple example, ask a comprehension question to check understanding.
Remember: Be like a real tutor - warm, engaging, step-by-step!"""

        messages = [
            {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": intro_prompt}
        ]

        response = TutorEngine._call_ai(messages)

        # Save conversation
        TutorEngine._save_message(db, user_id, lesson_id, "assistant", response, "teaching")

        # Update progress
        progress.tutor_state = TutorState.ASKING_QUESTION.value
        progress.current_concept_index = 0
        progress.status = LessonStatus.IN_PROGRESS.value
        db.commit()

        return {
            "message": response,
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "course": course.title if course else "",
                "total_concepts": len(concepts),
                "current_concept": 0,
            },
            "tutor_state": progress.tutor_state,
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
        
        context = f"""Lesson: {lesson.title}
Course: {course.title if course else 'General'}
Full lesson content: {lesson.content}
All concepts: {json.dumps(concepts)}
All examples: {json.dumps(examples)}
Current concept index: {current_idx} of {total_concepts - 1}
Current concept: {concepts[current_idx] if current_idx < total_concepts else 'All covered'}
Questions asked so far: {progress.questions_asked}
Correct answers so far: {progress.correct_answers}
Understanding level: {progress.understanding_level}%

The student just responded to your previous question/message. 
Evaluate their response, then:
1. If they answered correctly → praise them genuinely, then teach the NEXT concept ({concepts[current_idx + 1] if current_idx + 1 < total_concepts else 'LESSON COMPLETE - give a summary and congratulate!'})
2. If they answered incorrectly → kindly explain why, re-teach the concept with a different example, then ask again
3. If they're asking a question → answer it helpfully, then continue teaching
4. After teaching a new concept, ALWAYS ask a comprehension question

If all concepts are covered (index >= {total_concepts - 1} and they answered correctly), congratulate them and tell them the lesson is complete! Suggest they take the quiz.

REMEMBER: When teaching a NEW concept, include a [VISUAL_ANIMATION: ...] or [VISUAL_DIAGRAM: ...] tag to generate an AI visual for that concept.

Student's message: {student_message}"""

        messages = [{"role": "system", "content": TUTOR_SYSTEM_PROMPT}]
        for msg in history[:-1]:  # Exclude the one we just saved
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": context})

        response = TutorEngine._call_ai(messages, max_tokens=2500)

        # Save AI response
        TutorEngine._save_message(db, user_id, lesson_id, "assistant", response, "teaching")

        # Update progress - detect if answer was correct (simple heuristic + AI can be more nuanced)
        progress.questions_asked += 1
        is_likely_correct = any(marker in response.lower() for marker in 
                               ["correct", "right", "exactly", "well done", "great job", "perfect", "excellent", "✅", "awesome"])
        
        if is_likely_correct:
            progress.correct_answers += 1
            if current_idx < total_concepts - 1:
                progress.current_concept_index += 1
            else:
                progress.status = LessonStatus.COMPLETED.value
                progress.completed_at = datetime.now(timezone.utc)

        # Update understanding level
        if progress.questions_asked > 0:
            progress.understanding_level = (progress.correct_answers / progress.questions_asked) * 100

        progress.tutor_state = TutorState.ASKING_QUESTION.value
        db.commit()

        return {
            "message": response,
            "progress": {
                "current_concept": progress.current_concept_index,
                "total_concepts": total_concepts,
                "questions_asked": progress.questions_asked,
                "correct_answers": progress.correct_answers,
                "understanding": progress.understanding_level,
                "status": progress.status,
            },
            "tutor_state": progress.tutor_state,
            "lesson_complete": progress.status == LessonStatus.COMPLETED.value,
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
        if client:
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
        """Parse JSON from AI response, handling markdown code blocks."""
        text = response.strip()
        if text.startswith("```"):
            # Remove markdown code fences
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
        # Try to find JSON object in text
        brace_start = text.find("{")
        bracket_start = text.find("[")
        if brace_start >= 0:
            text = text[brace_start:]
        elif bracket_start >= 0:
            text = text[bracket_start:]
        return json.loads(text)

    @staticmethod
    def generate_course_from_topic(topic: str, detail: str = "") -> dict:
        """Generate a complete course from a topic description using AI."""
        if not client:
            return {"error": "AI not configured. Add your OpenAI API key to .env file."}

        user_prompt = f"Create a comprehensive course about: {topic}"
        if detail:
            user_prompt += f"\n\nAdditional details from the student: {detail}"

        messages = [
            {"role": "system", "content": COURSE_GENERATOR_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        response = TutorEngine._call_ai(messages, temperature=0.7, max_tokens=4000)

        try:
            course_data = TutorEngine._parse_json_response(response)
            # Validate required fields
            if "title" not in course_data or "lessons" not in course_data:
                return {"error": "AI generated invalid course structure. Please try again."}
            return course_data
        except (json.JSONDecodeError, Exception) as e:
            return {"error": f"Failed to parse AI response. Please try again. ({str(e)})"}

    @staticmethod
    def generate_course_from_text(text_content: str, title_hint: str = "") -> dict:
        """Generate a complete course from uploaded document text using AI."""
        if not client:
            return {"error": "AI not configured. Add your OpenAI API key to .env file."}

        # Truncate very long texts to fit token limits
        max_chars = 15000
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n\n[Content truncated for processing...]"

        prompt = TEXTBOOK_ANALYZER_PROMPT.format(text_content=text_content)
        if title_hint:
            prompt += f"\n\nThe user suggests the course title: {title_hint}"

        messages = [
            {"role": "system", "content": "You are an expert course designer. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        response = TutorEngine._call_ai(messages, temperature=0.5, max_tokens=4000)

        try:
            course_data = TutorEngine._parse_json_response(response)
            if "title" not in course_data or "lessons" not in course_data:
                return {"error": "AI generated invalid course structure. Please try again."}
            return course_data
        except (json.JSONDecodeError, Exception) as e:
            return {"error": f"Failed to parse AI response. Please try again. ({str(e)})"}
