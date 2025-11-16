# NIKI Photo Booth - AI Coding Assistant Instructions

## Project Overview
NIKI is an AI-powered autonomous photo booth system built with Python, featuring conversational AI guidance, real-time camera capture, photo processing, and text-to-speech interaction. The system uses OpenAI's GPT-4o-mini via Azure OpenAI with function calling to orchestrate photo sessions through a state-driven workflow.

## Architecture & Key Components

### Core System Flow
The application follows a strict conversational flow driven by AI tool calls:
1. `detect_presence` → `get_info_for_engagement` → `text_to_speech_with_emotions` → `wait_for_user_engagement`
2. `capture_photos` → `wait_for_user_choose_photo` → `print_photo` → `show_goodbye_screen_and_wait`
3. Loop back to presence detection

### Three UI Modes (`main.py`)
- **`/niki`**: Kiosk mode - emoji/text displays for public use
- **`/user`**: User interface - shows conversation history and engagement buttons
- **`/admin`**: Admin interface - full conversation table, interrupt controls, manual photo capture

### AI System (`niki_ai.py`)
- Uses Azure OpenAI GPT-4o-mini with structured tool definitions
- Maintains `master_message_list` for conversation state
- Tool calls block execution and set `shared_state.pending_tool_name`
- Interrupt handling allows ad-hoc user messages while preserving workflow

### State Management
- `SharedState` class with bindable properties for reactive UI updates
- Event system with UUID-based event tracking (`event_uuids`)
- Server-Sent Events (SSE) at `/api/state/sse` for real-time synchronization
- Global state includes: turn ("user"/"ai"/"admin"), pending tool calls, photo lists

### Camera & Photo Processing
- Custom NiceGUI element (`camera.js`) using WebRTC `getUserMedia`
- Photos saved via `/api/save_photo` endpoint with base64 data
- `photos.py`: PIL processing with 14:9 aspect ratio cropping, 1400x900 resize, 50px white borders
- Photos stored in `user_photos/` and moved to `chosen_photos/` upon selection

### Text-to-Speech (`tts.py`)
- Uses `gTTS` (Google Text-to-Speech) to generate MP3 files
- Files stored in `tts/` directory and served via NiceGUI media files
- Emotion parameter currently unused but structured for future enhancement

## Critical Development Patterns

### Tool Response Handling
When implementing tool responses in `handle_user_input()`:
```python
# For wait_for_user_engagement
content = json.dumps({"engagement": message.lower() == "yes", "random_nonce": random_nonce})

# For wait_for_user_choose_photo
content = json.dumps({"chosen_photo": message, "random_nonce": random_nonce})
# Plus photo file management in chosen_photos/
```

### UI State Mapping
Use `TOOL_UI_MAP` and `api_get_niki_ui()` for consistent kiosk displays:
```python
TOOL_UI_MAP = {
    "detect_presence": {"type": "display", "emoji": "ヽ(＾Д＾)ﾉ", "text": "Please step forward!"},
    "capture_photos": {"type": "button", "text": "Cancel", "state": "CAPTURE_PHOTOS"},
}
```

### Event-Driven Updates
All UI changes trigger via events:
```python
render_event.emit()  # Triggers full UI refresh
tts_event.emit(text, emotion)  # Triggers speech playback
```

### Authentication & Security
- Environment variables: `NIKI_API_KEY`, `NIKI_USER_PASSWORD`, `STORAGE_SECRET`
- API key middleware for external requests
- NiceGUI session-based auth for web interface

## Development Workflow

### Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (.env file)
NIKI_API_KEY=your_api_key
NIKI_USER_PASSWORD=your_password
STORAGE_SECRET=your_secret

# Run the application
python main.py
# Access at http://localhost:11011
```

### Testing & Debugging
- SSE testing: `python test_sse.py`
- AI conversation debugging: Check `.debug.json` after each interaction
- Photo processing: Use `debug_image.py` for image manipulation testing
- Admin mode provides full conversation inspection and manual controls

### Code Quality
- **Linting/Formatting**: `ruff` with pre-commit hooks
- **Configuration**: `.ruff.toml` with custom rules (allows long lines, global statements)
- **Import sorting**: Enabled with `isort` integration

## Common Implementation Patterns

### Adding New Tools
1. Define tool schema in `niki_ai.py` `tools` list
2. Add handling logic in `AIloop()` for blocking vs non-blocking execution
3. Implement response handling in `handle_user_input()`
4. Update UI mappings in `main.py` if needed

### Custom UI Elements
```python
# camera.py - Python wrapper
class camera(Element, component="camera.js"):
    def capture(self):
        self.run_method("capture")

# camera.js - Vue component with WebRTC
export default {
  template: `<video ref="video" autoplay playsinline muted></video>`,
  mounted() {
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => { this.$refs.video.srcObject = stream; });
  }
}
```

### State Synchronization
```python
# SSE endpoint yields state changes
async def api_state_yielder(request: Request):
    past_state = None
    while True:
        state = get_state()
        if state != past_state:
            yield {"event": "state_update", "data": json.dumps(state)}
        await asyncio.sleep(0.1)
```

## Key Files & Their Purposes
- `main.py`: Main application, UI modes, API endpoints, state management
- `niki_ai.py`: OpenAI integration, tool definitions, conversation flow
- `camera.py` + `camera.js`: WebRTC camera capture component
- `photos.py`: Image processing pipeline
- `tts.py`: Text-to-speech generation and playback
- `niki_utils.py`: UI helpers, button mappings, text processing
- `shared_state.py`: Reactive state management
- `FLOW.md`: High-level workflow documentation
- `NIKI_SCREEN_ELEMENTS.md`: UI/UX specifications

## Integration Points
- **External APIs**: Azure OpenAI (conversation), Google TTS
- **Hardware**: Camera (WebRTC), Printer (simulated via admin buttons)
- **File System**: `user_photos/`, `chosen_photos/`, `tts/`, `assets/`
- **Web Standards**: SSE for real-time updates, WebRTC for camera access

Remember: The AI drives all user interaction through tool calls. UI updates are event-driven. State is synchronized via SSE. Test all changes in admin mode first.