# AI Virtual Classroom 🎓

An AI-powered virtual classroom with interactive lessons, voice teaching, visual animations, quizzes, and gamification.

## Features
- 🤖 AI Tutor powered by GPT-4o-mini
- 🎨 AI-generated educational animations (HTML5 Canvas)
- 🎤 Voice-interactive teaching (Jarvis-like)
- 📚 Auto-generated courses from any topic
- 🧪 Visual Lab for concept visualization
- 📝 Quizzes & Homework
- 🏆 Gamification (XP, levels, achievements, leaderboard)
- 👤 Profile management with password change
- 👨‍🏫 Teacher & Parent dashboards

## Quick Start

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your-key-here
   SECRET_KEY=your-secret-key
   ```
4. Run: `python run.py`
5. Open: http://localhost:8000

## Deployment on Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: `OPENAI_API_KEY`, `SECRET_KEY`
6. Deploy!

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: Vanilla HTML/CSS/JS
- **AI**: OpenAI GPT-4o-mini, DALL-E 3
- **Voice**: Web Speech API
