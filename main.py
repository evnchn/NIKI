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
from niki_ai import AIloop, clear_conversation, handle_user_input, master_message_list, set_globals
from niki_utils import get_button_and_responses_from_tool_call, my_button, mydisplay, mystrip
from photos import process_and_save_photo
from tts import play_tts

load_dotenv()

assert "NIKI_API_KEY" in os.environ, "NIKI_API_KEY environment variable not set"
assert "NIKI_USER_PASSWORD" in os.environ, "NIKI_USER_PASSWORD environment variable not set"

unrestricted_page_routes = {"/login"}

passwords = {
    "user": os.environ["NIKI_USER_PASSWORD"],
}


class AuthMiddleware(BaseHTTPMiddleware):
    """This middleware restricts access to all NiceGUI pages.

    It redirects the user to the login page if they are not authenticated.
    """

    async def dispatch(self, request: Request, call_next):
        if app.storage.user.get("authenticated", False):
            return await call_next(request)  # authenticated via NiceGUI
        if request.cookies.get("api_key") == os.environ["NIKI_API_KEY"]:
            return await call_next(request)  # authenticated via API key
        if request.url.path.startswith("/_nicegui") or request.url.path in unrestricted_page_routes:
            return await call_next(request)  # necessary pages
        return RedirectResponse(url="/login")


app.add_middleware(AuthMiddleware)


@ui.page("/login")
def login_page():
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
        ui.button("Log in", on_click=try_login)
    return None


app.add_media_files("/assets", "assets")
app.add_media_files("/user_photos", "user_photos")
app.add_media_files("/chosen_photos", "chosen_photos")

# central storage for event UUIDs
event_uuids = {
    "render_event": str(uuid.uuid4()),
    "stop_voice_event": str(uuid.uuid4()),
    "tts_event": str(uuid.uuid4()),
    "camera_taking_event": str(uuid.uuid4()),
}


def update_event_uuid(name: str):
    event_uuids[name] = str(uuid.uuid4())


render_event = Event()
render_event.subscribe(lambda: update_event_uuid("render_event"))

stop_voice_event = Event()
stop_voice_event.subscribe(lambda: update_event_uuid("stop_voice_event"))

tts_event = Event()
tts_event.subscribe(lambda: update_event_uuid("tts_event"))

camera_taking_event = Event()
camera_taking_event.subscribe(lambda: update_event_uuid("camera_taking_event"))

photo_list = []
chosen_photos = []

set_globals(render_event, tts_event, photo_list, chosen_photos)

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
}
""",
    shared=True,
)
ui.label.default_classes("text-white")


if not os.path.exists("tts"):
    os.makedirs("tts")

ui.image.default_props("no-transition no-spinner")

## Button->response mapping moved to `niki_utils.get_button_and_responses_from_tool_call`


class SharedState:
    turn = binding.BindableProperty(on_change=render_event.emit)
    pending_tool_call_id = binding.BindableProperty()
    pending_tool_args = binding.BindableProperty()
    pending_tool_name = binding.BindableProperty()

    def __init__(self):
        self.turn = "user"  # or 'ai' or 'admin'
        self.pending_tool_call_id = None
        self.pending_tool_args = None
        self.pending_tool_name = None


my_shared_state = SharedState()

render_event.subscribe(lambda: print(f"Turn changed to: {my_shared_state.turn}"))


def get_last_tool_info():
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
    with ui.row().classes(row_classes):
        for i, photo in enumerate(photo_list):
            img = ui.image(f"/user_photos/{os.path.basename(photo)}").classes("w-1/3")
            img.on("click", lambda e, i=i: handle_user_input(str(i), my_shared_state))


def build_niki_ui(last_tool_called, last_tool_result):
    ui_state = api_get_niki_ui(last_tool_called, last_tool_result)
    if ui_state["type"] == "image":
        ui.image(ui_state["src"]).classes("w-full")
    elif ui_state["type"] == "display":
        mydisplay(ui_state["emoji"], ui_state["text"])
    elif ui_state["type"] == "photo_selection":
        display_photo_selection()
    elif ui_state["type"] == "button":
        my_button(ui_state["text"], on_click=lambda: handle_user_input("cancel"))


def api_get_niki_ui(last_tool_called, last_tool_result):
    if last_tool_result and "print_success" in last_tool_result and last_tool_result["print_success"]:
        return {"type": "image", "src": "/assets/thank_you.jpeg", "state": "PRINT_SUCCESS"}
    elif last_tool_called == "detect_presence":
        return {"type": "display", "emoji": "ヽ(＾Д＾)ﾉ", "text": "Please step forward!", "state": "DETECT_PRESENCE"}
    elif last_tool_called == "wait_for_user_engagement":
        return {
            "type": "display",
            "emoji": "ヽ(＾Д＾)ﾉ",
            "text": "Waiting for your confirmation...",
            "state": "WAIT_FOR_USER_ENGAGEMENT",
        }
    elif last_tool_called == "wait_for_user_choose_photo":
        return {
            "type": "photo_selection",
            "photos": [f"/user_photos/{os.path.basename(photo)}" for photo in photo_list],
            "state": "WAIT_FOR_USER_CHOOSE_PHOTO",
        }
    elif last_tool_called == "capture_photos":
        return {"type": "button", "text": "Cancel", "state": "CAPTURE_PHOTOS"}
    elif last_tool_called == "print_photo":
        return {"type": "image", "src": "/assets/printing_photo.jpeg", "state": "PRINT_PHOTO"}
    else:
        return {"type": "display", "emoji": "(ᴗ˳ᴗ)ᶻ𝗓𐰁 .ᐟ", "text": "Idle...", "state": "IDLE"}


def display_message(msg):
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
        if "framing_quality" in result:
            ui.label(f"Camera framing assessed: {result['framing_quality']} - {result['details']}")
        elif "engagement" in result:
            ui.label(f"User engagement: {result['engagement']}")
        elif "chosen_photo" in result:
            ui.label(f"Chosen photo: {result['chosen_photo']}")
        elif "presence_detected" in result:
            ui.label(f"Presence detected: {result['presence_detected']}")
        elif "capture_success" in result:
            ui.label(f"Photo capture success: {result['capture_success']}")
        elif "print_success" in result:
            ui.label(f"Print success: {result['print_success']}")
        elif "text" in result and "emotion" in result:
            ui.label(f"AI ({result['emotion']}): {result['text']}")
        else:
            ui.label(f"Tool result: {result}")


def build_main_ui(mode):
    last_tool_called = None
    if mode != "niki":
        build_user_admin_ui()
    else:
        last_tool_called, last_tool_result = get_last_tool_info()
        build_niki_ui(last_tool_called, last_tool_result)
    handle_turn_ui(mode, my_shared_state, photo_list)
    return last_tool_called


def build_user_admin_ui():
    for msg in master_message_list:
        display_message(msg)


def handle_turn_ui(mode, my_shared_state, photo_list):
    if my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_engagement":
        if mode in ("user", "admin"):
            ui.label("User's Turn: Confirm Engagement")
            my_button("Yes", on_click=lambda: handle_user_input("yes", my_shared_state))
            my_button("No", on_click=lambda: handle_user_input("no", my_shared_state))
    elif my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_choose_photo":
        display_photo_selection("")
    elif my_shared_state.turn == "admin" and my_shared_state.pending_tool_name:
        button_and_responses = get_button_and_responses_from_tool_call(my_shared_state.pending_tool_name, photo_list)
        if mode == "admin":
            ui.label(f"Admin: Choose for {my_shared_state.pending_tool_name}")
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
        my_button("Start Conversation", on_click=lambda: AIloop(my_shared_state))
    else:
        ui.label("AI is thinking...")


@ui.page("/")
@ui.page("/{mode}")
async def main_page(mode: str):
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
        camera_taking_event.subscribe(cam.capture)
    if mode == "admin":
        my_button("Stop Voice", on_click=lambda: stop_voice_event.emit())
        my_button("Clear Conversation", on_click=lambda: clear_conversation(my_shared_state))

    def refresh():
        main_container.clear()
        with main_container:
            last_tool_called = build_main_ui(mode)

        if last_tool_called in ["capture_photos"]:
            cam.set_visibility(True)
        else:
            cam.set_visibility(False)

    refresh()
    render_event.subscribe(refresh)


def get_state():
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
        "niki_ui_state": api_get_niki_ui(last_tool_called, last_tool_result),
    }


@app.get("/api/state")
def api_return_state():
    print("API state requested at time:", time())
    return get_state()


async def api_state_yielder(request: Request):
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
    return EventSourceResponse(api_state_yielder(request))


@app.post("/api/handle_user_input")
async def api_handle_user_input(request: Request):
    data = await request.json()
    message = data.get("message", "")
    background_tasks.create(lambda: handle_user_input(message, my_shared_state))
    return "Submitted to server, running AI loop right now."


@app.post("/api/save_photo")
async def save_photo(request: Request):
    data = await request.json()
    image_data = data.get("b64url")
    print("image_data preview:", (image_data or "")[:30], "...")
    # Delegate processing to photos.process_and_save_photo
    filename = process_and_save_photo(image_data)
    photo_list.append(filename)
    return {"success": True, "filename": filename}


@ui.page("/xiaomicam/photo")
def download_photo():
    # show all chosen photos for download
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
    cam = camera().classes("w-full")
    ui.button("Capture", on_click=lambda: cam.capture())


ui.run(port=11011, show=False, storage_secret=os.environ["STORAGE_SECRET"])
