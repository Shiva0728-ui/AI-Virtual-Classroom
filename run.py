"""
🎓 AI Virtual Classroom - Launch Script
Run this file to start the application!
"""
import os
import sys
import webbrowser
import time
import threading

def main():
    print("=" * 60)
    print("🎓 AI Virtual Classroom")
    print("=" * 60)
    print()
    
    # Check for .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        print("✅ .env file found")
        with open(env_path, encoding='utf-8') as f:
            content = f.read()
            if "your-openai-api-key-here" in content:
                print("⚠️  OpenAI API key not set! Edit .env to add your key.")
                print("   The app will work but AI tutor will use fallback mode.")
            else:
                print("✅ OpenAI API key configured")
    else:
        print("⚠️  No .env file found. Creating default...")
    
    print()
    print("🚀 Starting server on http://localhost:8000")
    print("   Press Ctrl+C to stop")
    print()
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8000")
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Change to backend directory and run
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)
    
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
