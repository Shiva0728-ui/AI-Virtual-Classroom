"""
AI Visual Engine - Generates educational visuals for teaching concepts

Two generation modes:
1. DALL-E 3 Image Generation: Creates illustrative images for concepts
2. AI Animation Generation: Creates HTML5/CSS/SVG interactive animations
   that demonstrate concepts visually (e.g., apple falling for gravity)
"""
import json
import re
import base64
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

def _get_client():
    """Lazy initialize the OpenAI client to pick up API keys from env at request time."""
    from config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)

# ──────────────────────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────────────────────

ANIMATION_GENERATOR_PROMPT = """You are an ELITE educational animation engineer. You create STUNNING, REALISTIC, self-contained HTML5 Canvas animations that visually demonstrate educational concepts with near-professional quality.

CRITICAL RULES:
1. Output ONLY a complete, self-contained HTML document — NO external dependencies
2. Use HTML5 Canvas with requestAnimationFrame for SMOOTH 60fps rendering
3. The animation MUST be deeply educational — show cause and effect clearly
4. Body style: `margin:0; padding:0; overflow:hidden; background:#0f0f1e;`
5. Do NOT include markdown fences — output raw HTML only

VISUAL QUALITY — MAKE IT LOOK REAL:
6. Use GRADIENTS and SHADOWS for realistic lighting: `ctx.createRadialGradient()`, `ctx.shadowBlur`, `ctx.shadowColor`
7. Use PARTICLE EFFECTS for trails, dust, sparks, water droplets etc. — create a particles array and animate them
8. Apply GLOW EFFECTS: set `ctx.shadowBlur = 15; ctx.shadowColor = '#color';` before drawing bright objects
9. Use PROPER PHYSICS: gravity=9.8m/s², use delta-time for frame-independent animation
10. Anti-alias with `ctx.imageSmoothingEnabled = true;`
11. Stars/background: for space scenes, draw 200+ small random dots as stars. For earth scenes, draw a gradient sky
12. Use REALISTIC COLORS: Sun=#FDB813 with orange glow, Earth=#4B82C4, Mars=#C1440E, water=#2196F3, plants=#4CAF50, metal=#9E9E9E
13. Add MOTION BLUR / TRAILS: draw previous positions with decreasing opacity for moving objects
14. 3D FEEL: Use slight perspective, size-based depth (farther = smaller), and overlapping elements

FULLSCREEN & RESPONSIVE:
15. Canvas fills the ENTIRE viewport: `canvas.width = window.innerWidth; canvas.height = window.innerHeight;` + resize listener
16. All positions calculated as PERCENTAGES of canvas size. No hardcoded pixel values
17. Elements should use the FULL available space, not cluster in a tiny area

ANIMATION SPEED & CONTROLS:
18. Animations must be SLOW and EASY TO FOLLOW — students need time to read
19. Global speed variable: `let speed = 1; let paused = false;`
20. You MUST add a control bar at the bottom (HTML overlay, not canvas-drawn):
```html
<div id="controls" style="position:fixed;bottom:0;left:0;width:100%;padding:14px;background:rgba(0,0,0,0.9);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;gap:12px;z-index:1000;">
  <button onclick="togglePause()" id="pauseBtn" style="background:#6366f1;color:#fff;border:none;padding:10px 22px;border-radius:10px;cursor:pointer;font-size:15px;font-weight:700;">⏸ Pause</button>
  <button onclick="restart()" style="background:#6366f1;color:#fff;border:none;padding:10px 22px;border-radius:10px;cursor:pointer;font-size:15px;font-weight:700;">🔄 Replay</button>
  <button onclick="setSpeed(0.5)" id="sp05" style="background:#334155;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">0.5x</button>
  <button onclick="setSpeed(1)" id="sp1" style="background:#22c55e;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">1x</button>
  <button onclick="setSpeed(2)" id="sp2" style="background:#334155;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">2x</button>
</div>
```
21. Implement `togglePause()`, `restart()` that resets all state to initial, `setSpeed(s)` that highlights active button
22. After one complete animation cycle, auto-pause and show "▶ Play" text on pause button

TEXT & LABELS:
23. Title: bold 26px Arial, white, top-center, with slight shadow
24. Labels: 16px Arial, white, WITH a dark background rect behind each label for readability
25. Draw helper arrows using lines+triangles, annotated with values
26. Show changing values (velocity, time, etc.) as live updating text on screen

EXAMPLES of QUALITY expected:
- GRAVITY: Realistic tree with trunk+leaves (bezier curves), textured apple with highlight, falling with acceleration trail particles, ground with grass blades, velocity/time labels updating live, bounce effect on impact
- SOLAR SYSTEM: Glowing sun with corona rays, 8 planets with correct relative sizes and colors, elliptical orbits with trail lines, planet names and distance labels, starfield background with twinkling
- WATER CYCLE: Landscape with mountains (gradient), ocean with waves (sine animation), clouds forming (particle aggregation), rain drops, sun with light rays, labeled arrows between stages
- SORTING: Colorful gradient bars with rounded tops, smooth sliding transitions, comparison highlights with glow, step counter, algorithm name label, sorted bars turn green with sparkle effect
- ELECTRIC CIRCUIT: Wire paths with electron dots flowing, battery with +/- terminals, light bulb that glows when circuit completes, ammeter showing current value, labeled components

MAKE IT WOW. Professional quality. Students should feel like they're watching a science documentary animation.
"""

IMAGE_PROMPT_GENERATOR = """You are an AI that creates DALL-E image prompts for educational illustrations.

Given a concept/topic, create a detailed DALL-E prompt that will generate a clear, educational illustration.

RULES:
- The image should be educational and clearly explain/illustrate the concept
- Use a clean, modern illustration style (flat design or scientific illustration)
- Include labels, arrows, or annotations in the description when helpful
- Make it visually appealing with good colors
- Keep the prompt under 400 characters
- DO NOT include text that should be readable in the image (DALL-E is bad at text rendering)
- Focus on visual demonstration of the concept
- Return ONLY the prompt text, nothing else
"""


# ──────────────────────────────────────────────────────────────
# VISUAL ENGINE CLASS
# ──────────────────────────────────────────────────────────────

class VisualEngine:
    """Generates AI-powered educational visuals."""

    @staticmethod
    def generate_animation(concept: str, context: str = "") -> dict:
        """
        Generate an HTML5/CSS/JS animation that demonstrates a concept.
        Returns: {"html": "<full html>", "title": "...", "type": "animation"}
        """
        client = _get_client()
        if not client:
            return {"error": "AI not configured. Add OpenAI API key to .env"}

        user_prompt = f"Create a FULL-SCREEN educational animation that visually demonstrates: {concept}"
        if context:
            user_prompt += f"\n\nAdditional context from the lesson: {context}"
        user_prompt += """\n\nIMPORTANT REMINDERS:
- Canvas MUST fill the entire window (use window.innerWidth / innerHeight)
- Animation must be SLOW — students need time to read and understand (use speed=0.3 time scale)
- Include Play/Pause button, Replay button, and Speed selector (0.5x, 1x, 2x) in a fixed bottom bar
- After one complete cycle, PAUSE the animation (don't loop forever)
- Use LARGE elements that fill the screen, not tiny centered graphics
- Output ONLY the raw HTML document. No markdown, no code fences."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Use faster model for visuals on Vercel
                messages=[
                    {"role": "system", "content": ANIMATION_GENERATOR_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                timeout=55,
            )
            
            html_content = response.choices[0].message.content.strip()
            
            # Clean up: remove markdown fences if AI included them
            html_content = VisualEngine._clean_html(html_content)
            
            # Validate it looks like HTML
            if not html_content.strip().startswith(("<!", "<html", "<HTML", "<div", "<canvas", "<svg")):
                # Try to find HTML in the response
                match = re.search(r'(<(!DOCTYPE|html|div|canvas|svg)[^>]*>.*)', html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    html_content = match.group(1)
                else:
                    return {"error": "AI did not generate valid HTML animation"}
            
            # Inject safety: sandbox-friendly, responsive wrapper
            if "<html" not in html_content.lower():
                html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;padding:12px;background:#1a1a2e;color:#e0e0e0;font-family:Arial,sans-serif;overflow:hidden}}</style>
</head><body>{html_content}</body></html>"""
            
            return {
                "html": html_content,
                "title": f"Visual: {concept}",
                "type": "animation",
                "concept": concept,
            }
            
        except Exception as e:
            print(f"Animation generation error: {e}")
            return {"error": f"Failed to generate animation: {str(e)}"}

    @staticmethod
    def generate_image(concept: str, context: str = "") -> dict:
        """
        Generate an educational illustration using DALL-E 3.
        Returns: {"url": "...", "title": "...", "type": "image"}
        """
        client = _get_client()
        if not client:
            return {"error": "AI not configured. Add OpenAI API key to .env"}

        # First, generate an optimized DALL-E prompt
        try:
            prompt_response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": IMAGE_PROMPT_GENERATOR},
                    {"role": "user", "content": f"Create an educational illustration prompt for: {concept}" + (f"\nContext: {context}" if context else "")}
                ],
                temperature=0.7,
                max_tokens=200,
                timeout=55,
            )
            dalle_prompt = prompt_response.choices[0].message.content.strip()
        except Exception as e:
            # Fallback prompt
            dalle_prompt = f"Educational illustration showing {concept}, clean modern flat design, bright colors, professional scientific diagram style"

        # Generate image with DALL-E
        try:
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = image_response.data[0].url
            
            return {
                "url": image_url,
                "title": f"Illustration: {concept}",
                "type": "image",
                "concept": concept,
                "prompt_used": dalle_prompt,
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"DALL-E error: {error_msg}")
            
            # If DALL-E fails (quota, billing), fall back to animation
            if "billing" in error_msg.lower() or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                return {"error": "Image generation not available (API quota). Use 'Generate Animation' instead — it's free with your API key!", "fallback": "animation"}
            
            return {"error": f"Image generation failed: {error_msg}"}

    @staticmethod
    def generate_concept_visual(concept: str, lesson_content: str = "", visual_type: str = "auto") -> dict:
        """
        Smart visual generation - picks the best type based on the concept.
        Optimized for Vercel Hobby (10s limit).
        """
        # On Vercel, always prefer quick SVG unless explicitly asked for something else
        # This ensures we don't hit the 10s timeout
        if visual_type == "auto":
            return VisualEngine.generate_quick_visual(concept)
            
        if visual_type == "image":
            return VisualEngine.generate_image(concept, lesson_content[:500])
        elif visual_type == "animation":
            return VisualEngine.generate_animation(concept, lesson_content[:500])
            
        return VisualEngine.generate_quick_visual(concept)

    @staticmethod
    def _clean_html(html: str) -> str:
        """Remove markdown code fences and other wrappers from AI output."""
        html = html.strip()
        
        # Remove ```html ... ``` fences
        if html.startswith("```"):
            lines = html.split("\n")
            # Remove first line (```html or ```)
            lines = lines[1:]
            # Remove last ``` if present
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            html = "\n".join(lines)
        
        return html.strip()

    @staticmethod
    def generate_quick_visual(topic: str) -> dict:
        """
        Generate a quick inline SVG visual for embedding in tutor messages.
        Returns a simple SVG string, not a full HTML page.
        Used by the tutor to embed small visuals directly in chat.
        """
        client = _get_client()
        if not client:
            return {"error": "AI not configured"}

        prompt = f"""Create a small, inline SVG illustration (max 400x250px) that demonstrates: {topic}

RULES:
- Output ONLY the <svg> tag and its contents, nothing else
- Use a dark background fill (#1e1e3a) for the SVG
- Use bright, visible colors for elements
- Include simple text labels (using <text> tags with fill="#e0e0e0")
- Keep it simple but informative — like a textbook diagram
- SVG must be self-contained (no external references)
- Set viewBox for proper scaling (e.g., viewBox="0 0 400 250")
- Add a small title text at the top

Output the raw SVG tag only. No markdown, no code fences, no explanation."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You create educational SVG diagrams. Output ONLY raw SVG markup."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
                timeout=55,
            )
            
            svg = response.choices[0].message.content.strip()
            svg = VisualEngine._clean_html(svg)
            
            # Ensure it starts with <svg
            if not svg.startswith("<svg"):
                match = re.search(r'(<svg[^>]*>.*?</svg>)', svg, re.DOTALL | re.IGNORECASE)
                if match:
                    svg = match.group(1)
                else:
                    return {"error": "Failed to generate SVG visual"}
            
            return {
                "svg": svg,
                "type": "inline_svg",
                "concept": topic,
            }
            
        except Exception as e:
            return {"error": f"SVG generation failed: {str(e)}"}
