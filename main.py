"""
NIKI Photo Booth Main Application

This module implements the main web application for the NIKI AI-powered photo booth system.
It provides three UI modes: kiosk (/niki), user interface (/user), and admin interface (/admin).
The application integrates AI conversation flow, camera capture, photo processing, and text-to-speech.

Key Features:
- Authentication middleware for secure access
- Real-time state synchronization via Server-Sent Events (SSE)
- Event-driven UI updates
- Integration with Azure OpenAI for conversational AI
- WebRTC camera capture and photo processing
- Text-to-speech functionality

Dependencies:
- nicegui: Web UI framework
- fastapi: Web framework
- sse-starlette: Server-Sent Events support
- python-dotenv: Environment variable management
"""

import asyncio
import json
import os
import uuid
from time import time

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import Event, app, background_tasks, binding, ui
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware

import tts
from camera import camera
from niki_ai import (
    AIloop,
    clear_conversation,
    handle_user_input,
    interrupt_with_user_message,
    master_message_list,
    set_globals,
)
from niki_utils import get_button_and_responses_from_tool_call, my_button, mydisplay, mystrip
from photos import process_and_save_photo
from tts import play_tts

load_dotenv()

# Validate required environment variables
assert "NIKI_API_KEY" in os.environ, "NIKI_API_KEY environment variable not set"
assert "NIKI_USER_PASSWORD" in os.environ, "NIKI_USER_PASSWORD environment variable not set"

# Define unrestricted routes that don't require authentication
unrestricted_page_routes = {"/login"}

# Password storage for different user types
passwords = {
    "user": os.environ["NIKI_USER_PASSWORD"],
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for NiceGUI pages.

    Restricts access to all NiceGUI pages except for unrestricted routes.
    Supports authentication via NiceGUI storage or API key cookies.
    Redirects unauthenticated users to the login page.
    """

    async def dispatch(self, request: Request, call_next):
        # Check if user is authenticated via NiceGUI storage
        if app.storage.user.get("authenticated", False):
            return await call_next(request)

        # Check if user is authenticated via API key cookie
        if request.cookies.get("api_key") == os.environ["NIKI_API_KEY"]:
            return await call_next(request)

        # Allow access to necessary pages without authentication
        if request.url.path.startswith("/_nicegui") or request.url.path in unrestricted_page_routes:
            return await call_next(request)

        # Log unauthenticated access attempts
        print("Unauthenticated access with cookies:", request.cookies)
        return RedirectResponse(url="/login")


# app.add_middleware(AuthMiddleware)


@ui.page("/login")
def login_page():
    """
    Login page for user authentication.

    Provides a simple form for username and password input.
    Redirects authenticated users to the main page.
    """

    def try_login() -> None:  # local function to avoid passing username and password as arguments
        if passwords.get(username.value) == password.value:
            app.storage.user.update({"username": username.value, "authenticated": True})
            ui.navigate.to("/")  # go back to where the user wanted to go
        else:
            ui.notify("Wrong username or password", color="negative")

    if app.storage.user.get("authenticated", False):
        return RedirectResponse("/")
    with ui.card().classes("absolute-center"):
        username = ui.input("Username").on("keydown.enter", try_login)
        password = ui.input("Password", password=True, password_toggle_button=True).on("keydown.enter", try_login)
        with ui.row():
            ui.button("Log in", on_click=try_login)
    return None


app.add_media_files("/assets", "assets")
app.add_media_files("/user_photos", "user_photos")
app.add_media_files("/chosen_photos", "chosen_photos")

# Central storage for event UUIDs to track UI update events
event_uuids = {
    "render_event": str(uuid.uuid4()),
    "stop_voice_event": str(uuid.uuid4()),
    "tts_event": str(uuid.uuid4()),
    "camera_taking_event": str(uuid.uuid4()),
}


def update_event_uuid(name: str):
    """Update the UUID for a specific event type to trigger UI refreshes."""
    event_uuids[name] = str(uuid.uuid4())


# Event objects for triggering UI updates across the application
render_event = Event()
render_event.subscribe(lambda: update_event_uuid("render_event"))

stop_voice_event = Event()
stop_voice_event.subscribe(lambda: update_event_uuid("stop_voice_event"))

tts_event = Event()
tts_event.subscribe(lambda: update_event_uuid("tts_event"))

camera_taking_event = Event()
camera_taking_event.subscribe(lambda: update_event_uuid("camera_taking_event"))

# Global state variables for photo management
photo_list = []  # List of captured photos waiting for selection
chosen_photos = []  # List of selected photos
ui_state_history = []  # History of UI states for debugging

# Initialize global username if not set
if "global_username" not in app.storage.general:
    app.storage.general["global_username"] = "Guest"

# Set global variables for AI system integration
set_globals(render_event, tts_event, photo_list, chosen_photos, app.storage.general)

# Ensure necessary directories exist
if not os.path.exists("chosen_photos"):
    os.makedirs("chosen_photos")

ui.add_css(
    """
@font-face {
    font-family: 'CustomFont';
    src: url('/assets/font.ttf') format('truetype');
}
body {
    background-color: #006160;
    font-family: 'CustomFont', sans-serif;
    height: 100vh;
}
""",
    shared=True,
)
ui.label.default_classes("text-white")

# Ensure TTS directory exists for audio file storage
if not os.path.exists("tts"):
    os.makedirs("tts")

# Configure default image properties for smooth loading
ui.image.default_props("no-transition no-spinner")

# UI state mappings for different tool calls in kiosk mode
TOOL_UI_MAP = {
    "detect_presence": {
        "type": "display",
        "emoji": "ヽ(＾Д＾)ﾉ",
        "text": "Please step forward!",
        "state": "DETECT_PRESENCE",
    },
    "capture_photos": {"type": "button", "text": "Cancel", "state": "CAPTURE_PHOTOS"},
    "print_photo": {"type": "image", "src": "/assets/printing_photo.jpeg", "state": "PRINT_PHOTO"},
    "show_goodbye_screen_and_wait": {"type": "display", "emoji": "👋", "text": "Goodbye!", "state": "GOODBYE"},
    "get_info_for_engagement": {"type": "display", "emoji": "(╭ರ_•́)", "text": "Thinking...", "state": "THINKING"},
}

# Display formatters for tool results in conversation views
RESULT_DISPLAY_KEYS = [
    ("framing_quality", lambda result: f"Camera framing assessed: {result['framing_quality']} - {result['details']}"),
    ("engagement", lambda result: f"User engagement: {result['engagement']}"),
    ("chosen_photo", lambda result: f"Chosen photo: {result['chosen_photo']}"),
    ("presence_detected", lambda result: f"Presence detected: {result['presence_detected']}"),
    ("capture_success", lambda result: f"Photo capture success: {result['capture_success']}"),
    ("print_success", lambda result: f"Print success: {result['print_success']}"),
    ("text", lambda result: f"AI ({result['emotion']}): {result['text']}" if "emotion" in result else None),
    (
        "username",
        lambda result: f"Pitch fetched for {result['username']}: {result['pitch']}" if "pitch" in result else None,
    ),
    ("pitch", lambda result: f"AI (HAPPY): {result['pitch']}"),
]


class SharedState:
    """
    Shared state management for the application.

    Uses NiceGUI's bindable properties to enable reactive UI updates.
    Tracks the current turn (user/ai/admin), pending tool calls, and their parameters.
    """

    turn = binding.BindableProperty(on_change=render_event.emit)
    pending_tool_call_id = binding.BindableProperty()
    pending_tool_args = binding.BindableProperty()
    pending_tool_name = binding.BindableProperty()

    def __init__(self):
        self.turn = "user"  # Current turn: 'user', 'ai', or 'admin'
        self.pending_tool_call_id = None
        self.pending_tool_args = None
        self.pending_tool_name = None


my_shared_state = SharedState()

# Subscribe to render events for debugging turn changes
render_event.subscribe(lambda: print(f"Turn changed to: {my_shared_state.turn}"))


def get_last_tool_info():
    """
    Extract the last tool call and its result from the conversation history.

    Iterates through the master_message_list in reverse to find the most recent
    tool call (excluding text_to_speech_with_emotions) and its corresponding result.

    Returns:
        tuple: (last_tool_called, last_tool_result) where both may be None
    """
    last_tool_called = None
    last_tool_result = None
    for msg in reversed(master_message_list):
        if msg["role"] == "tool" and last_tool_result is None:
            last_tool_result = json.loads(msg["content"])
        elif msg["role"] == "assistant" and "tool_calls" in msg and last_tool_called is None:
            for tc in reversed(msg["tool_calls"]):
                if tc["function"]["name"] != "text_to_speech_with_emotions":
                    last_tool_called = tc["function"]["name"]
                    break
        if last_tool_called is not None and last_tool_result is not None:
            break
    return last_tool_called, last_tool_result


def display_photo_selection(row_classes="w-full"):
    """
    Display a selection of captured photos for user choice.

    Creates clickable image elements for each photo in photo_list.
    When clicked, selects the photo and clears the list.

    Args:
        row_classes: CSS classes for the row container
    """

    async def choose_image_and_clear_list(i: str, my_shared_state):
        global photo_list
        index = int(i)
        chosen_photo = photo_list[index]
        chosen_photos.append(chosen_photo)
        photo_list = []  # Clear photo list after selection
        await handle_user_input(f"choose_photo:{index}", my_shared_state)

    with ui.row().classes(row_classes):
        for i, photo in enumerate(photo_list):
            img = ui.image(f"/user_photos/{os.path.basename(photo)}").classes("w-1/3")
            img.on("click", lambda e, i=i: choose_image_and_clear_list(str(i), my_shared_state))


def build_niki_ui(last_tool_called, last_tool_result):
    """
    Build the kiosk UI based on the current tool state.

    Displays appropriate content (image, text, photo selection, or button)
    based on the last tool called and its result.

    Args:
        last_tool_called: Name of the last tool called
        last_tool_result: Result of the last tool call
    """
    ui_state = api_get_niki_ui(last_tool_called, last_tool_result, app.storage.general["global_username"], photo_list)
    ui_state_history.append(ui_state)
    if ui_state["type"] == "image":
        ui.image(ui_state["src"]).classes("w-full")
    elif ui_state["type"] == "display":
        mydisplay(ui_state["emoji"], ui_state["text"])
    elif ui_state["type"] == "photo_selection":
        display_photo_selection()
    elif ui_state["type"] == "button":
        with ui.row():
            my_button(ui_state["text"], on_click=lambda: handle_user_input("cancel"))


def api_get_niki_ui(last_tool_called, last_tool_result, global_username, photo_list):
    """
    Determine the UI state for kiosk mode based on tool call information.

    Returns a dictionary describing what should be displayed in kiosk mode.

    Args:
        last_tool_called: Name of the last tool called
        last_tool_result: Result of the last tool call
        global_username: Current user's name
        photo_list: List of available photos

    Returns:
        dict: UI state with type, content, and state information
    """
    if last_tool_result and "print_success" in last_tool_result and last_tool_result["print_success"]:
        return {"type": "image", "src": "/assets/thank_you.jpeg", "state": "PRINT_SUCCESS"}
    elif last_tool_called == "wait_for_user_engagement":
        return {
            "type": "display",
            "emoji": "ヽ(＾Д＾)ﾉ",
            "text": f"Hello {global_username}!",
            "state": "WAIT_FOR_USER_ENGAGEMENT",
        }
    elif last_tool_called == "wait_for_user_choose_photo":
        return {
            "type": "photo_selection",
            "photos": [f"/user_photos/{os.path.basename(photo)}" for photo in photo_list],
            "state": "WAIT_FOR_USER_CHOOSE_PHOTO",
        }
    else:
        return TOOL_UI_MAP.get(
            last_tool_called, {"type": "display", "emoji": "(ᴗ˳ᴗ)ᶻ𝗓𐰁 .ᐟ", "text": "Idle...", "state": "IDLE"}
        )


def display_message(msg):
    """
    Display a single message from the conversation history.

    Formats and displays messages based on their role (user, assistant, tool).

    Args:
        msg: Message dictionary with 'role' and 'content' keys
    """
    role = msg["role"]
    content = msg["content"]
    if role == "user":
        ui.label(f"User: {content}")
    elif role == "assistant":
        content = msg.get("content")
        if content:
            prefix, stripped_content = mystrip(content)
            ui.label(f"AI ({prefix}): {stripped_content}")
        if "tool_calls" in msg:
            for tool_call in msg["tool_calls"]:
                if tool_call["function"]["name"] != "text_to_speech_with_emotions":
                    ui.label(f"AI is calling {tool_call['function']['name']}...")
    elif role == "tool":
        result = json.loads(content)
        for key, formatter in RESULT_DISPLAY_KEYS:
            if key in result:
                text = formatter(result)
                if text:
                    ui.label(text)
                    break
        else:
            ui.label(f"Tool result: {result}")


def build_main_ui(mode):
    """
    Build the main UI based on the current mode.

    Delegates to specific UI builders based on mode and handles turn-based UI.

    Args:
        mode: UI mode ('niki', 'user', or 'admin')

    Returns:
        last_tool_called: Name of the last tool called (for camera visibility)
    """
    last_tool_called = None
    if mode == "user":
        build_user_admin_ui()
    elif mode == "admin":
        build_admin_ui()
    else:
        last_tool_called, last_tool_result = get_last_tool_info()
        build_niki_ui(last_tool_called, last_tool_result)
    handle_turn_ui(mode, my_shared_state, photo_list)
    return last_tool_called


def build_user_admin_ui():
    """Build the conversation display for user and admin modes."""
    for msg in master_message_list:
        display_message(msg)


def build_state_display(ui_state):
    """
    Build a visual state progression display with icons.

    Shows the current state in the photo booth workflow with visual indicators.

    Args:
        ui_state: Current UI state dictionary
    """
    states_order = [
        "IDLE",
        "DETECT_PRESENCE",
        "WAIT_FOR_USER_ENGAGEMENT",
        "THINKING",
        "CAPTURE_PHOTOS",
        "WAIT_FOR_USER_CHOOSE_PHOTO",
        "PRINT_PHOTO",
        "PRINT_SUCCESS",
        "GOODBYE",
    ]
    state_icons = {
        "IDLE": "😴",
        "DETECT_PRESENCE": "👀",
        "THINKING": "🤔",
        "WAIT_FOR_USER_ENGAGEMENT": "👋",
        "CAPTURE_PHOTOS": "📸",
        "WAIT_FOR_USER_CHOOSE_PHOTO": "🖼️",
        "PRINT_PHOTO": "🖨️",
        "PRINT_SUCCESS": "✅",
        "GOODBYE": "👋",
    }
    current_state = ui_state.get("state", "IDLE")
    current_index = states_order.index(current_state) if current_state in states_order else -1

    with ui.column().classes("flex-grow"):
        with ui.row().classes("w-full"):
            for i, state in enumerate(states_order):
                icon = state_icons.get(state, "❓")
                label = ui.label(icon).classes("text-2xl mx-2")
                if i <= current_index:
                    label.classes("text-white")
                else:
                    label.classes("text-white opacity-10")


def build_global_username_input():
    """Build UI for updating the global username used in greetings."""
    with ui.column():
        with ui.row():
            global_username_input = (
                ui.input("Global Username", value=app.storage.general["global_username"])
                .props("dark")
                .classes("flex-grow")
            )

            def update_global_username():
                app.storage.general["global_username"] = global_username_input.value
                render_event.emit()

            my_button("Update Global Username", on_click=update_global_username)


def build_conversation_table():
    """Build a table displaying the conversation history for admin mode."""
    with ui.column().classes("w-full mt-4"):
        with ui.element("div").classes("conversation-scroll"):
            columns = [
                {"name": "role", "label": "Role", "field": "role", "align": "left"},
                {"name": "content", "label": "Message", "field": "content", "align": "left"},
            ]
            rows = []
            for msg in master_message_list:
                if msg["role"] == "system":
                    continue
                content = msg.get("content", "")
                if msg["role"] == "assistant" and "tool_calls" in msg:
                    tool_names = [tc["function"]["name"] for tc in msg["tool_calls"]]
                    tool_str = f" (tool calls: {tool_names})"
                    content = f"{content}{tool_str}" if content else tool_str
                rows.append({"role": msg["role"], "content": content})
            ui.table(columns=columns, rows=rows).props("wrap-cells").classes("w-full text-white bg-gray-800")


def build_admin_ui():
    """Build the comprehensive admin interface with state display and controls."""
    last_tool_called, last_tool_result = get_last_tool_info()
    ui_state = api_get_niki_ui(last_tool_called, last_tool_result, app.storage.general["global_username"], photo_list)

    # State steps
    states_order = [
        "IDLE",
        "DETECT_PRESENCE",
        "WAIT_FOR_USER_ENGAGEMENT",
        "THINKING",
        "CAPTURE_PHOTOS",
        "WAIT_FOR_USER_CHOOSE_PHOTO",
        "PRINT_PHOTO",
        "PRINT_SUCCESS",
        "GOODBYE",
    ]
    state_icons = {
        "IDLE": "😴",
        "DETECT_PRESENCE": "👀",
        "THINKING": "🤔",
        "WAIT_FOR_USER_ENGAGEMENT": "👋",
        "CAPTURE_PHOTOS": "📸",
        "WAIT_FOR_USER_CHOOSE_PHOTO": "🖼️",
        "PRINT_PHOTO": "🖨️",
        "PRINT_SUCCESS": "✅",
        "GOODBYE": "👋",
    }
    current_state = ui_state.get("state", "IDLE")
    current_index = states_order.index(current_state) if current_state in states_order else -1

    # Top row: state display on left, global username on right
    with ui.row().classes("w-full"):
        # Left: state display
        with ui.column().classes("flex-grow"):
            with ui.row().classes("w-full"):
                for i, state in enumerate(states_order):
                    icon = state_icons.get(state, "❓")
                    label = ui.label(icon).classes("text-2xl mx-2")
                    if i <= current_index:
                        label.classes("text-white")
                    else:
                        label.classes("text-white opacity-10")
        # Right: global username
        with ui.column():
            build_global_username_input()

    # Conversation Messages
    build_conversation_table()


def handle_turn_ui(mode, my_shared_state, photo_list):
    """
    Handle turn-based UI elements based on current state.

    Shows appropriate buttons and controls depending on whose turn it is
    and what tool is pending.

    Args:
        mode: Current UI mode
        my_shared_state: Shared state object
        photo_list: List of available photos
    """
    if my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_engagement":
        if mode in ("user", "admin"):
            ui.label("User's Turn: Confirm Engagement")
            with ui.row():
                my_button("Yes", on_click=lambda: handle_user_input("yes", my_shared_state))
                my_button("No", on_click=lambda: handle_user_input("no", my_shared_state))
    elif my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_choose_photo":
        display_photo_selection("")
    elif my_shared_state.turn == "admin" and my_shared_state.pending_tool_name:
        button_and_responses = get_button_and_responses_from_tool_call(my_shared_state.pending_tool_name, photo_list)
        if mode == "admin":
            ui.label(f"Admin: Choose for {my_shared_state.pending_tool_name}")
            with ui.row():
                for button_text, response in button_and_responses.items():
                    my_button(
                        button_text,
                        on_click=lambda r=response: handle_user_input(r, my_shared_state),
                    )
                if my_shared_state.pending_tool_name == "capture_photos":
                    my_button("Capture Photo", on_click=camera_taking_event.emit)
                    my_button(
                        "Say cheese",
                        on_click=lambda: play_tts("Say cheese! Smile big!", "HAPPY"),
                    )
                    my_button("3 2 1", on_click=lambda: play_tts("3 2 1", "HAPPY"))
        else:
            ui.label(f"Waiting for admin to handle {my_shared_state.pending_tool_name}...")
    elif len(master_message_list) == 1 and mode in ("user", "admin"):
        with ui.row():
            my_button("Start Conversation", on_click=lambda: AIloop(my_shared_state))
    else:
        ui.label("AI is thinking...")
        ui.label("Debug:")
        ui.label(my_shared_state.pending_tool_name)
        ui.label(my_shared_state.pending_tool_call_id)
        ui.label(my_shared_state.turn)


@ui.page("/")
@ui.page("/{mode}")
async def main_page(mode: str):
    """
    Main page handler for all UI modes.

    Supports three modes:
    - /niki: Kiosk mode for public use
    - /user: User interface showing conversation history
    - /admin: Admin interface with full controls

    Args:
        mode: The UI mode ('niki', 'user', or 'admin')
    """
    if mode not in ("niki", "user", "admin"):
        ui.label("Invalid mode. Use /niki, /user, or /admin.")
        return

    if mode == "niki":
        mybutton = my_button("Click to begin")
        await mybutton.clicked()
        mybutton.delete()

    cam = camera().classes("w-full")
    cam.set_visibility(False)

    main_container = ui.column().classes("w-full")

    if mode == "niki":
        tts_event.subscribe(lambda text, emotion: play_tts(text, emotion))
        stop_voice_event.subscribe(
            lambda: ui.run_javascript(
                "if (window.currentAudio) { window.currentAudio.pause(); window.currentAudio.currentTime = 0; }"
            )
        )
        # Camera capture disabled since native app takes precedence
        # camera_taking_event.subscribe(cam.capture)
    if mode == "admin":
        with ui.row():
            my_button("Stop Voice", on_click=lambda: stop_voice_event.emit())
            my_button("Clear Conversation", on_click=lambda: clear_conversation(my_shared_state))

        async def handle_interrupt(interrupt_text):
            # Handle interrupt with or without pending tool call
            if my_shared_state.pending_tool_name:
                print("Handling interrupt with tool call:", my_shared_state.pending_tool_name)
                await handle_user_input(f"interrupt:{interrupt_text}", my_shared_state)
            else:
                print("Handling interrupt without tool call")
                my_shared_state.turn = "ai"
                await interrupt_with_user_message(interrupt_text, my_shared_state)

        with ui.row().classes("w-full"):
            interrupt_input = ui.input("User message for interrupt", value="").props("dark").classes("flex-grow")
            my_button("Interrupt", on_click=lambda: handle_interrupt(interrupt_input.value))

        with ui.row().classes("w-full"):
            my_button(
                "Interrupt (tech)",
                on_click=lambda: handle_interrupt("Tell me about yourself and the technology which empowers you."),
            )
            my_button("Interrupt (no-tech)", on_click=lambda: handle_interrupt("Tell me about yourself"))

    def refresh():
        """Refresh the main UI container based on current state."""
        main_container.clear()
        with main_container:
            last_tool_called = build_main_ui(mode)

        if last_tool_called in ["capture_photos"]:
            cam.set_visibility(True)
        else:
            cam.set_visibility(False)

        if mode == "admin":
            ui.run_javascript(
                "setTimeout(() => { const el = document.querySelector('.conversation-scroll'); if (el) el.scrollTop = el.scrollHeight; }, 100);"
            )

    refresh()
    render_event.subscribe(refresh)


def get_state():
    """
    Get the current application state for synchronization.

    Returns comprehensive state information including conversation history,
    current turn, pending tool calls, and UI state for real-time updates.

    Returns:
        dict: Complete application state
    """
    last_tool_called, last_tool_result = get_last_tool_info()
    return {
        "master_message_list": master_message_list,
        "turn": my_shared_state.turn,
        "pending_tool_call_id": my_shared_state.pending_tool_call_id,
        "pending_tool_name": my_shared_state.pending_tool_name,
        "pending_tool_args": my_shared_state.pending_tool_args,
        "latest_tts_path": tts.latest_tts_path,
        "button_and_responses": get_button_and_responses_from_tool_call(my_shared_state.pending_tool_name, photo_list)
        if my_shared_state.pending_tool_name
        else {},
        "event_uuids": event_uuids,
        "niki_ui_state": api_get_niki_ui(
            last_tool_called, last_tool_result, app.storage.general["global_username"], photo_list
        ),
    }


@app.get("/api/state")
def api_return_state():
    """
    REST API endpoint to get current application state.

    Used for polling the current state when Server-Sent Events are not available.
    """
    print("API state requested at time:", time())
    return get_state()


async def api_state_yielder(request: Request):
    """
    Server-Sent Events generator for real-time state updates.

    Continuously yields state changes to connected clients for live synchronization.

    Args:
        request: FastAPI request object

    Yields:
        dict: SSE event with state update data
    """
    past_state = None
    while True:
        if request.is_disconnected():
            print("Client disconnected from SSE")
            break
        state = get_state()
        if state != past_state:
            yield {"event": "state_update", "data": json.dumps(state)}
            past_state = state
        await asyncio.sleep(0.1)


@app.get("/api/state/sse")
def api_state_sse(request: Request):
    """
    Server-Sent Events endpoint for real-time state synchronization.

    Clients connect to this endpoint to receive live updates of application state.

    Args:
        request: FastAPI request object

    Returns:
        EventSourceResponse: SSE response stream
    """
    return EventSourceResponse(api_state_yielder(request))


@app.post("/api/handle_user_input")
async def api_handle_user_input(request: Request):
    """
    API endpoint to handle user input asynchronously.

    Processes user messages in the background and triggers AI processing.

    Args:
        request: FastAPI request with message data

    Returns:
        str: Confirmation message
    """
    data = await request.json()
    message = data.get("message", "")
    background_tasks.create(handle_user_input(message, my_shared_state))
    return "Submitted to server, running AI loop right now."


@app.post("/api/save_photo")
async def save_photo(request: Request):
    """
    API endpoint to save a captured photo.

    Receives base64 encoded image data, processes it, and adds to photo list.

    Args:
        request: FastAPI request with base64 image data

    Returns:
        dict: Success status and filename
    """
    data = await request.json()
    image_data = data.get("b64url")
    print("image_data preview:", (image_data or "")[:30], "...")
    # Delegate processing to photos.process_and_save_photo
    filename = process_and_save_photo(image_data)
    photo_list.append(filename)
    return {"success": True, "filename": filename}


@ui.page("/xiaomicam/photo")
def download_photo():
    """
    Photo download page for chosen photos.

    Displays all selected photos with download links.
    """
    # Show all chosen photos for download
    with ui.column():
        if chosen_photos:
            for photo in chosen_photos:
                ui.image(f"/chosen_photos/{os.path.basename(photo)}").classes("w-1/3")
                ui.label(f"Download {os.path.basename(photo)}:")
                ui.link(
                    f"/chosen_photos/{os.path.basename(photo)}",
                    f"/chosen_photos/{os.path.basename(photo)}",
                )
        else:
            ui.label("No chosen photos available for download.")


@ui.page("/test/camera")
def test_camera_page():
    """
    Camera test page for debugging camera functionality.

    Provides a simple interface to test camera capture.
    """
    cam = camera().classes("w-full")
    with ui.row():
        ui.button("Capture", on_click=lambda: cam.capture())


# Start the NiceGUI application server
ui.run(port=11011, show=False, storage_secret=os.environ["STORAGE_SECRET"])
