/* ═══════════════════════════════════════════════════════════════
   Voice-Interactive Teaching System
   Makes the AI tutor speak like a real teacher
   - Auto-speaks tutor responses (enabled by default)
   - Visual speaking indicators (sound waves, avatar pulse)
   - Voice input with auto-send
   - Natural pause between sentences for clarity
   ═══════════════════════════════════════════════════════════════ */

const Voice = {
    enabled: false,       // Voice narration on/off
    speaking: false,      // Currently speaking
    listening: false,     // Mic is recording
    paused: false,        // Speech paused by user
    synth: window.speechSynthesis || null,
    recognition: null,
    currentUtterance: null,
    speechQueue: [],      // Queue of text chunks to speak
    queueIndex: 0,
    selectedVoice: null,  // Cached best voice
    wakeWordRecognition: null, // Always-on listener
    wakeWordActive: false,
    
    // Settings
    rate: 0.92,           // Slightly slower than default for teaching
    pitch: 1.05,          // Slightly higher for clarity
    volume: 0.85,

    init() {
        // Speech Recognition setup
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                const result = event.results[event.results.length - 1];
                const text = result[0].transcript;
                const input = document.getElementById('student-input');
                if (input) input.value = text;

                // When final result, auto-send
                if (result.isFinal) {
                    this.listening = false;
                    this.updateMicButton();
                    // Auto-send after a brief delay
                    setTimeout(() => {
                        if (input && input.value.trim()) {
                            Classroom.sendMessage();
                        }
                    }, 400);
                }
            };

            this.recognition.onerror = (e) => {
                console.log('Speech recognition error:', e.error);
                this.listening = false;
                this.updateMicButton();
                if (e.error === 'not-allowed') {
                    App.toast('Microphone access denied. Please allow it in browser settings.', 'error');
                }
            };

            this.recognition.onend = () => {
                this.listening = false;
                this.updateMicButton();
            };

            // Wake Word Recognition (Continuous)
            this.wakeWordRecognition = new SpeechRecognition();
            this.wakeWordRecognition.continuous = true;
            this.wakeWordRecognition.interimResults = false;
            this.wakeWordRecognition.lang = 'en-US';

            this.wakeWordRecognition.onresult = (event) => {
                const text = event.results[event.results.length - 1][0].transcript.toLowerCase();
                if (text.includes('hey nova') || text.includes('hey professor')) {
                    this.processCommand(text);
                }
            };
            
            this.wakeWordRecognition.onerror = (e) => {
                if (e.error !== 'not-allowed') {
                    // Restart listener silently
                    if (this.wakeWordActive) setTimeout(() => this.enableWakeWord(), 1000);
                }
            };
            
            this.wakeWordRecognition.onend = () => {
                // Keep it always running if enabled
                if (this.wakeWordActive) this.enableWakeWord();
            };
        }

        // Pre-select the best voice
        this._selectBestVoice();

        // Update button state
        this._updateToggleButton();
        
        // Auto-start wake word if permitted previously
        if (localStorage.getItem('nova_wakeword') === 'true') {
            this.enableWakeWord();
        }
    },

    // ─── Wake Word & Commands ────────────────────────────────────
    enableWakeWord() {
        if (!this.wakeWordRecognition) return;
        try {
            this.wakeWordActive = true;
            this.wakeWordRecognition.start();
            localStorage.setItem('nova_wakeword', 'true');
        } catch (e) {} // Ignore if already started
    },
    
    stopWakeWord() {
        this.wakeWordActive = false;
        if (this.wakeWordRecognition) this.wakeWordRecognition.stop();
        localStorage.setItem('nova_wakeword', 'false');
    },

    processCommand(text) {
        // Pause any current speech
        this.stop();
        
        // Visual feedback
        if (typeof NovaAI !== 'undefined' && !NovaAI.isOpen) {
            NovaAI.toggle();
        }
        
        if (text.includes('study today') || text.includes('what should i do')) {
            this.speak("I've analyzed your progress. I recommend reviewing your recent Python lesson.");
            setTimeout(() => App.navigate('dashboard'), 2000);
        } else if (text.includes('open classroom') || text.includes('resume')) {
            this.speak("Opening the classroom. Let's pick up where we left off.");
            setTimeout(() => App.navigate('classroom'), 2000);
        } else if (text.includes('how am i doing')) {
            this.speak("You are doing exceptionally well. Keep up this momentum!");
        } else {
            this.speak("At your service. How can I help you learn today?");
        }
    },

    ambientNarration(page) {
        if (!this.enabled) return;
        
        switch(page) {
            case 'dashboard':
                this.speak("Welcome back. I have outlined your learning progress on the dashboard.");
                break;
            case 'courses':
                this.speak("Here are the available courses. Would you like me to recommend one?");
                break;
        }
    },

    // ─── Voice Selection ─────────────────────────────────────────
    _selectBestVoice() {
        if (!this.synth) return;

        const findVoice = () => {
            const voices = this.synth.getVoices();
            if (!voices.length) return;

            // Priority: natural/premium English voices
            const priorities = [
                v => /Google UK English Female/i.test(v.name),
                v => /Google US English/i.test(v.name),
                v => /Microsoft Zira/i.test(v.name),
                v => /Microsoft Jenny/i.test(v.name),
                v => /Samantha/i.test(v.name),
                v => /Google.*English/i.test(v.name),
                v => /Female.*en/i.test(v.name) || (/en[-_]/.test(v.lang) && /female/i.test(v.name)),
                v => v.lang.startsWith('en-') && v.localService,
                v => v.lang.startsWith('en'),
            ];

            for (const test of priorities) {
                const found = voices.find(test);
                if (found) {
                    this.selectedVoice = found;
                    console.log('Selected voice:', found.name, found.lang);
                    return;
                }
            }
            // Fallback
            this.selectedVoice = voices[0];
        };

        findVoice();
        // Voices may not be loaded yet
        if (this.synth.onvoiceschanged !== undefined) {
            this.synth.onvoiceschanged = () => findVoice();
        }
    },

    // ─── Toggle Voice On/Off ─────────────────────────────────────
    toggle() {
        this.enabled = !this.enabled;
        this._updateToggleButton();
        
        if (this.enabled) {
            App.toast('🔊 Voice teaching enabled — I\'ll speak as I teach!', 'success');
            this._showVoiceBanner(true);
        } else {
            this.stop();
            App.toast('🔇 Voice teaching disabled', 'info');
            this._showVoiceBanner(false);
        }
    },

    _updateToggleButton() {
        const btn = document.getElementById('voice-toggle');
        if (!btn) return;
        
        if (this.enabled) {
            btn.innerHTML = '<i class="fas fa-volume-up"></i>';
            btn.classList.add('voice-active');
        } else {
            btn.innerHTML = '<i class="fas fa-volume-mute"></i>';
            btn.classList.remove('voice-active');
        }
    },

    _showVoiceBanner(show) {
        const banner = document.getElementById('voice-mode-banner');
        if (banner) {
            banner.classList.toggle('active', show);
        }
    },

    // ─── Speak Text (Main Method) ────────────────────────────────
    speak(text) {
        if (!this.enabled || !this.synth) return;

        // Save for replay
        this.lastSpokenText = text;

        // Stop any current speech
        this.stop();

        // Clean text for natural speech
        let cleanText = this._cleanForSpeech(text);
        if (!cleanText) return;

        // Split into natural sentence chunks
        this.speechQueue = this._splitIntoSentences(cleanText);
        this.queueIndex = 0;
        this.speaking = true;
        this.paused = false;

        // Show speaking indicator
        this._showSpeakingState(true);

        // Start speaking
        this._speakNext();
    },

    _speakNext() {
        if (this.queueIndex >= this.speechQueue.length || !this.speaking) {
            this._finishSpeaking();
            return;
        }

        const text = this.speechQueue[this.queueIndex];
        const utterance = new SpeechSynthesisUtterance(text);
        
        utterance.rate = this.rate;
        utterance.pitch = this.pitch;
        utterance.volume = this.volume;
        
        if (this.selectedVoice) {
            utterance.voice = this.selectedVoice;
        }

        utterance.onend = () => {
            this.queueIndex++;
            // Small natural pause between sentences
            setTimeout(() => this._speakNext(), 150);
        };

        utterance.onerror = (e) => {
            if (e.error !== 'interrupted') {
                console.error('Speech error:', e.error);
            }
            this._finishSpeaking();
        };

        this.currentUtterance = utterance;
        this.synth.speak(utterance);
    },

    _finishSpeaking() {
        this.speaking = false;
        this.paused = false;
        this.currentUtterance = null;
        this._showSpeakingState(false);
    },

    // Track last spoken text for replay
    lastSpokenText: '',

    // ─── Speaking Visual Indicators ──────────────────────────────
    _showSpeakingState(isSpeaking) {
        // Pulse the latest tutor message avatar
        const messages = document.querySelectorAll('.chat-message.tutor');
        const lastTutor = messages[messages.length - 1];
        
        if (lastTutor) {
            if (isSpeaking) {
                lastTutor.classList.add('tutor-speaking');
            } else {
                lastTutor.classList.remove('tutor-speaking');
            }
        }

        // Update banner
        const statusText = document.getElementById('voice-status-text');
        if (statusText) {
            if (isSpeaking) {
                statusText.innerHTML = '<span class="voice-wave-indicator"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></span> Professor is speaking...';
            } else {
                statusText.textContent = '🔊 Voice teaching active — I\'ll speak when explaining concepts';
            }
        }

        // Update control buttons
        const stopBtn = document.getElementById('stop-speaking-btn');
        const playBtn = document.getElementById('play-speaking-btn');
        if (stopBtn) stopBtn.style.display = isSpeaking ? 'inline-block' : 'none';
        if (playBtn) playBtn.style.display = (!isSpeaking && this.lastSpokenText) ? 'inline-block' : 'none';
    },

    // ─── Stop / Pause / Play Controls ────────────────────────────
    stop() {
        if (this.synth) {
            this.synth.cancel();
        }
        this.speaking = false;
        this.paused = false;
        this.speechQueue = [];
        this.queueIndex = 0;
        this.currentUtterance = null;
        this._showSpeakingState(false);
    },

    // Replay the last tutor message
    replay() {
        if (this.lastSpokenText) {
            this.speak(this.lastSpokenText);
        }
    },

    pauseResume() {
        if (!this.synth || !this.speaking) return;
        
        if (this.paused) {
            this.synth.resume();
            this.paused = false;
            this._showSpeakingState(true);
        } else {
            this.synth.pause();
            this.paused = true;
            const statusText = document.getElementById('voice-status-text');
            if (statusText) {
                statusText.textContent = '⏸ Paused — click to resume';
            }
        }
    },

    // ─── Microphone / Listening ──────────────────────────────────
    startListening() {
        if (!this.recognition) {
            App.toast('Speech recognition not supported in this browser', 'error');
            return;
        }

        // Stop tutor speaking if active (so mic doesn't pick it up)
        if (this.speaking) {
            this.stop();
        }

        if (this.listening) {
            this.recognition.stop();
            this.listening = false;
        } else {
            try {
                this.recognition.start();
                this.listening = true;
                App.toast('🎤 Listening... Speak your question!', 'info');
            } catch(e) {
                console.error('Mic start error:', e);
            }
        }
        this.updateMicButton();
    },

    updateMicButton() {
        const btn = document.getElementById('mic-btn');
        if (!btn) return;
        
        if (this.listening) {
            btn.classList.add('mic-listening');
            btn.innerHTML = '<i class="fas fa-stop"></i>';
        } else {
            btn.classList.remove('mic-listening');
            btn.innerHTML = '<i class="fas fa-microphone"></i>';
        }
    },

    // ─── Text Cleaning for Natural Speech ────────────────────────
    _cleanForSpeech(text) {
        return text
            // Remove visual tags
            .replace(/\[VISUAL_(?:ANIMATION|DIAGRAM):[^\]]+\]/gi, '')
            // Remove code blocks — say "code example on screen" instead
            .replace(/```[\s\S]*?```/g, '... I\'ve put a code example on screen for you ...')
            // Remove inline code backticks
            .replace(/`([^`]+)`/g, '$1')
            // Remove markdown headers
            .replace(/#{1,6}\s/g, '')
            // Remove bold/italic markers
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/__([^_]+)__/g, '$1')
            // Remove emojis (they cause awkward pauses)
            .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}\u{1F100}-\u{1F64F}\u{1F680}-\u{1F6FF}]/gu, '')
            // Remove markdown links, keep text
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            // Remove HTML tags
            .replace(/<[^>]+>/g, '')
            // Clean up excessive whitespace
            .replace(/\n{2,}/g, '. ')
            .replace(/\n/g, ' ')
            .replace(/\s{2,}/g, ' ')
            .trim();
    },

    _splitIntoSentences(text) {
        // Split by sentence endings, keep chunks manageable for the browser
        const chunks = [];
        const maxLen = 200;
        
        // Split on sentence boundaries
        const sentences = text.split(/(?<=[.!?])\s+/);
        let current = '';

        for (const sentence of sentences) {
            if ((current + ' ' + sentence).length > maxLen && current) {
                chunks.push(current.trim());
                current = sentence;
            } else {
                current = current ? current + ' ' + sentence : sentence;
            }
        }
        if (current.trim()) chunks.push(current.trim());
        
        return chunks.filter(c => c.length > 0);
    }
};

// Initialize when voices load
if (window.speechSynthesis) {
    speechSynthesis.onvoiceschanged = () => Voice.init();
}
Voice.init();
