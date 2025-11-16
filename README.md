# NIKI Photo Booth

NIKI is an AI-powered autonomous photo booth system built with Python, featuring conversational AI guidance, real-time camera capture, photo processing, and text-to-speech interaction. The system uses OpenAI's GPT-4o-mini via Azure OpenAI with function calling to orchestrate photo sessions through a state-driven workflow.

## Features

- **Conversational AI**: Powered by Azure OpenAI GPT-4o-mini for natural user interactions
- **Real-time Camera Capture**: WebRTC-based camera integration for live photo taking
- **Photo Processing**: Automatic cropping, resizing, and border addition using PIL
- **Text-to-Speech**: Google Text-to-Speech integration for voice guidance
- **Multi-UI Modes**: Kiosk, user, and admin interfaces for different use cases
- **State-Driven Workflow**: Event-based state management with Server-Sent Events (SSE)
- **Real-time Synchronization**: Live UI updates across all connected clients

## Architecture

### Core System Flow
The application follows a strict conversational flow driven by AI tool calls:
1. `detect_presence` → `get_info_for_engagement` → `text_to_speech_with_emotions` → `wait_for_user_engagement`
2. `capture_photos` → `wait_for_user_choose_photo` → `print_photo` → `show_goodbye_screen_and_wait`
3. Loop back to presence detection

### Three UI Modes
- **`/niki`**: Kiosk mode - emoji/text displays for public use
- **`/user`**: User interface - shows conversation history and engagement buttons
- **`/admin`**: Admin interface - full conversation table, interrupt controls, manual photo capture

### Key Components
- `main.py`: Main application, UI modes, API endpoints, state management
- `niki_ai.py`: OpenAI integration, tool definitions, conversation flow
- `camera.py` + `camera.js`: WebRTC camera capture component
- `photos.py`: Image processing pipeline
- `tts.py`: Text-to-speech generation and playback
- `shared_state.py`: Reactive state management

## Installation

### Prerequisites
- Python 3.8+
- Azure OpenAI API access
- WebRTC-compatible browser

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/evnchn/NIKI.git
   cd NIKI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables (create a `.env` file):
   ```
   NIKI_API_KEY=your_azure_openai_api_key
   NIKI_USER_PASSWORD=your_user_password
   STORAGE_SECRET=your_storage_secret
   ```

## Usage

### Running the Application
```bash
python main.py
```

Access the application at `http://localhost:11011`

### UI Modes
- **Kiosk Mode** (`/niki`): Public-facing interface with emoji/text displays
- **User Mode** (`/user`): Interactive interface with conversation history
- **Admin Mode** (`/admin`): Full control panel with manual overrides

### API Endpoints
- `/api/state/sse`: Server-Sent Events for real-time state updates
- `/api/save_photo`: Save captured photos
- `/api/user_input`: Handle user interactions

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

## Troubleshooting

### Common Issues
- **Camera not working**: Ensure WebRTC permissions are granted in the browser
- **TTS not playing**: Check internet connection for Google TTS API
- **AI responses slow**: Verify Azure OpenAI API key and network connectivity
- **State not syncing**: Check SSE connection and browser console for errors

### Debug Mode
Use admin mode (`/admin`) for full conversation inspection and manual controls. Check `.debug.json` for AI interaction logs.

## Contributing

1. Follow the established code quality standards (ruff, isort)
2. Test all changes in admin mode first
3. Update documentation for any new features
4. Ensure backward compatibility with existing workflows

## License

[Add your license information here]