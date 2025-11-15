import asyncio
import json
import os
import uuid
from time import time

from dotenv import load_dotenv
from fastapi import Request
from nicegui import Event, app, background_tasks, binding, ui
from openai import AsyncAzureOpenAI
from sse_starlette.sse import EventSourceResponse

import tts
from camera import camera
from niki_utils import get_button_and_responses_from_tool_call, mystrip
from photos import process_and_save_photo
from tts import play_tts

load_dotenv()

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


def my_button(text, *, on_click=None):
    return ui.button(text, color="white", on_click=on_click).classes("text-[#006160]")


if not os.path.exists("tts"):
    os.makedirs("tts")

ui.image.default_props("no-transition no-spinner")

SYSTEM_PROMPT = """You are Niki, an automated photo session assistant. Follow this flow, adapting flexibly to user responses and system states:

1. Start by calling detect_presence tool.
2. If presence detected, call text_to_speech_with_emotions with emotion "HAPPY" to say hello and explain who you are (e.g., "Hello! I'm Niki, your friendly photo assistant. Let's take some fun pictures!"), then call wait_for_user_engagement to check for user engagement (expect a verbal confirmation like "yes" or "ready").
3. If engaged, call text_to_speech_with_emotions with emotion "HAPPY" to tell the user to get ready for a photo shoot (e.g., "Great! Simply move into camera, and I will take the photos for you at the right moment!"), then call capture_photos.
4. If capture success, call text_to_speech_with_emotions with emotion "HAPPY" to ask the user to select a photo (e.g., "Awesome shots! Which one do you like best? Click on your favorite photo."), then call wait_for_user_choose_photo (expect photo selection via click: index 0, 1, 2, etc.).
   - If capture fails, retry capture_photos up to 2 times. If still failing, call text_to_speech_with_emotions with emotion "SAD" to apologize (e.g., "Sorry, there was an issue taking the photo. Let's try again later."), then end the session.
5. If photo selected, call text_to_speech_with_emotions with emotion "HAPPY" to say "I am printing the photo for you" (or similar, e.g., "Printing your favorite photo now!"), then call print_photo.
   - If selection is invalid, prompt again once, then default to the first photo or end.
6. If print success, call text_to_speech_with_emotions with emotion "HAPPY" to say goodbye to the user (e.g., "All done! Thanks for the fun photo session. Goodbye!").
   - If print fails, retry print_photo up to 1 time. If still failing, call text_to_speech_with_emotions with emotion "SAD" to notify (e.g., "Sorry, printing failed. Your photo is saved digitally."), then proceed to goodbye.
7. After saying goodbye, go back to step 1 for the next user.

For any tool calls with failing results, try up to 5 times, then gracefully handle failure with appropriate speech and end the session if needed.

Keep AI responses short and tool-focused. Use tools to block for inputs—do not assume inputs without calling tools. Before calling any tool, provide a brief response explaining what you are doing (e.g., "Checking for presence..."). For wait_for_user_engagement, specify what input you expect (e.g., "Waiting for your confirmation..."). For wait_for_user_choose_photo, always respond positively about the choice."""

client = AsyncAzureOpenAI(azure_deployment="gpt-4o-mini")

emotions = ["HAPPY", "SAD", "CONFUSED"]

capture_done = False

## Helper functions moved to `niki_utils.py` to reduce duplication and centralize behavior.


def mydisplay(line1, line2):
    with ui.column().classes("aspect-3/2 w-full items-center"):
        ui.space()
        ui.label(line1).classes("text-6xl")
        ui.label(line2).classes("text-3xl")
        ui.space()


tools = [
    {
        "type": "function",
        "function": {
            "name": "wait_for_user_engagement",
            "description": "Wait for user engagement confirmation (yes/no).",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request.",
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_user_choose_photo",
            "description": "Wait for the user to choose a photo from the captured photos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request.",
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_presence",
            "description": "Detect if there is user presence in front of the camera.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request.",
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_photos",
            "description": "Capture photos during the photo session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request.",
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "print_photo",
            "description": "Print the selected photo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request.",
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "text_to_speech_with_emotions",
            "description": "Convert text to speech with specified emotion to communicate with the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to speak to the user.",
                    },
                    "emotion": {
                        "type": "string",
                        "enum": ["HAPPY", "SAD", "CONFUSED"],
                        "description": "The emotion to convey in the speech.",
                    },
                },
                "required": ["text", "emotion"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]

## Button->response mapping moved to `niki_utils.get_button_and_responses_from_tool_call`

master_message_list = [{"role": "system", "content": SYSTEM_PROMPT}]


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


async def AIloop():
    my_shared_state.turn = "ai"
    agent_continue = True
    while agent_continue:
        # save master_message_list to .debug.json
        with open(".debug.json", "w") as f:
            json.dump(master_message_list, f, indent=2)
        result = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=master_message_list,
            tools=tools,
        )
        if result.choices[0].message.tool_calls:
            master_message_list.append(result.choices[0].message.to_dict())
            tool_calls_handled = False
            for tool_call in result.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                if tool_name == "wait_for_user_engagement":
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = "user"
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == "wait_for_user_choose_photo":
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = "user"
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name in ["detect_presence", "capture_photos", "print_photo"]:
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = "admin"
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == "text_to_speech_with_emotions":
                    # Non-blocking TTS
                    args = json.loads(tool_args)
                    text = args["text"]
                    emotion = args["emotion"]
                    master_message_list.append(
                        {
                            "role": "tool",
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"success": True, "text": text, "emotion": emotion}),
                        }
                    )
                    tts_event.emit(text, emotion)
                    tool_calls_handled = True
                    # Continue the loop for non-blocking
                else:
                    master_message_list.append(
                        {
                            "role": "tool",
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                        }
                    )
            if not tool_calls_handled:
                continue
            # If tool_calls_handled, we are waiting for user input, so break the while
        elif result.choices[0].message.content:
            master_message_list.append({"role": "assistant", "content": result.choices[0].message.content})
        elif result.choices[0].message.refusal:
            master_message_list.append({"role": "assistant", "content": result.choices[0].message.refusal})
        render_event.emit()


async def handle_user_input(message: str):
    if my_shared_state.pending_tool_call_id:
        random_nonce = json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
        if my_shared_state.pending_tool_name == "wait_for_user_engagement":
            content = json.dumps({"engagement": message.lower() == "yes", "random_nonce": random_nonce})
        elif my_shared_state.pending_tool_name == "wait_for_user_choose_photo":
            content = json.dumps({"chosen_photo": message, "random_nonce": random_nonce})
        elif my_shared_state.pending_tool_name == "detect_presence":
            content = json.dumps({"presence_detected": message == "yes", "random_nonce": random_nonce})
        elif my_shared_state.pending_tool_name == "capture_photos":
            content = json.dumps({"capture_success": message == "yes", "random_nonce": random_nonce})
        elif my_shared_state.pending_tool_name == "print_photo":
            content = json.dumps({"print_success": message == "yes", "random_nonce": random_nonce})
        else:
            content = json.dumps(
                {
                    "error": f"Unknown tool response: {message}",
                    "random_nonce": random_nonce,
                }
            )
        master_message_list.append(
            {
                "role": "tool",
                "type": "function_call_output",
                "tool_call_id": my_shared_state.pending_tool_call_id,
                "content": content,
            }
        )
        # Handle photo selection
        if my_shared_state.pending_tool_name == "wait_for_user_choose_photo":
            try:
                index = int(message)
                if 0 <= index < len(photo_list):
                    src = photo_list[index]
                    dst = os.path.join("chosen_photos", os.path.basename(src))
                    os.rename(src, dst)
                    chosen_photos.append(dst)
            except ValueError:
                pass
        my_shared_state.pending_tool_call_id = None
        my_shared_state.pending_tool_args = None
        my_shared_state.pending_tool_name = None
        if my_shared_state.turn == "admin":
            my_shared_state.turn = "ai"
    await AIloop()


def clear_conversation():
    global capture_done
    master_message_list.clear()
    master_message_list.append({"role": "system", "content": SYSTEM_PROMPT})
    my_shared_state.pending_tool_call_id = None
    my_shared_state.pending_tool_args = None
    my_shared_state.pending_tool_name = None
    photo_list.clear()
    chosen_photos.clear()
    capture_done = False
    render_event.emit()


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

    def trigger_capture():
        global capture_done
        cam.capture()
        capture_done = True

    main_container = ui.column().classes("w-full")

    if mode == "niki":
        tts_event.subscribe(lambda text, emotion: play_tts(text, emotion))
        stop_voice_event.subscribe(
            lambda: ui.run_javascript(
                "if (window.currentAudio) { window.currentAudio.pause(); window.currentAudio.currentTime = 0; }"
            )
        )
        camera_taking_event.subscribe(trigger_capture)
    if mode == "admin":
        my_button("Stop Voice", on_click=lambda: stop_voice_event.emit())
        my_button("Clear Conversation", on_click=clear_conversation)

    def refresh():
        last_tool_called = None
        main_container.clear()
        with main_container:
            if mode != "niki":
                for i, msg in enumerate(master_message_list):
                    if mode == "niki" and i != len(master_message_list) - 1:
                        continue  # niki mode only shows latest message
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        ui.label(f"User: {content}")
                    elif role == "assistant":
                        content = msg.get("content")
                        if content:
                            prefix, stripped_content = mystrip(content)
                            ui.label(f"AI ({prefix}): {stripped_content}")
                            if mode == "niki":
                                play_tts(stripped_content, prefix)
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
            else:
                last_tool_called = None
                for msg in reversed(master_message_list):
                    if msg["role"] == "assistant" and "tool_calls" in msg:
                        for tc in reversed(msg["tool_calls"]):
                            if tc["function"]["name"] != "text_to_speech_with_emotions":
                                last_tool_called = tc["function"]["name"]
                                break
                        if last_tool_called:
                            break
                last_tool_result = None
                for msg in reversed(master_message_list):
                    if msg["role"] == "tool":
                        last_tool_result = json.loads(msg["content"])
                        break
                if last_tool_result and "print_success" in last_tool_result and last_tool_result["print_success"]:
                    ui.image("/assets/thank_you.jpeg").classes("w-full")
                elif last_tool_called == "detect_presence":
                    # ('/assets/step_forward.jpeg').classes('w-full')
                    mydisplay("ヽ(＾Д＾)ﾉ", "Please step forward!")
                elif last_tool_called == "wait_for_user_engagement":
                    # Show friendly waiting prompt on the Niki screen
                    mydisplay("ヽ(＾Д＾)ﾉ", "Waiting for your confirmation...")
                elif last_tool_called == "wait_for_user_choose_photo":
                    with ui.row().classes("w-full"):
                        for i, photo in enumerate(photo_list):
                            img = ui.image(f"/user_photos/{os.path.basename(photo)}").classes("w-1/3")
                            img.on("click", lambda e, i=i: handle_user_input(str(i)))
                elif last_tool_called == "capture_photos":
                    my_button("Cancel", on_click=lambda: handle_user_input("cancel"))
                elif last_tool_called == "print_photo":
                    ui.image("/assets/printing_photo.jpeg").classes("w-full")
                else:
                    # ('/assets/idle.jpeg').classes('w-full')
                    mydisplay("(ᴗ˳ᴗ)ᶻ𝗓𐰁 .ᐟ", "Idle...")
            if my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_engagement":
                if mode in ("user", "admin"):
                    ui.label("User's Turn: Confirm Engagement")
                    my_button("Yes", on_click=lambda: handle_user_input("yes"))
                    my_button("No", on_click=lambda: handle_user_input("no"))
            elif my_shared_state.turn == "user" and my_shared_state.pending_tool_name == "wait_for_user_choose_photo":
                with ui.row():
                    for i, photo in enumerate(photo_list):
                        img = ui.image(f"/user_photos/{os.path.basename(photo)}").classes("w-1/3")
                        img.on("click", lambda e, i=i: handle_user_input(str(i)))
            elif my_shared_state.turn == "admin" and my_shared_state.pending_tool_name:
                button_and_responses = get_button_and_responses_from_tool_call(
                    my_shared_state.pending_tool_name, photo_list
                )
                if mode == "admin":
                    ui.label(f"Admin: Choose for {my_shared_state.pending_tool_name}")
                    for button_text, response in button_and_responses.items():
                        my_button(
                            button_text,
                            on_click=lambda r=response: handle_user_input(r),
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
                my_button("Start Conversation", on_click=AIloop)
            else:
                ui.label("AI is thinking...")

        if last_tool_called in ["capture_photos"]:
            cam.set_visibility(True)
        else:
            cam.set_visibility(False)

    refresh()
    render_event.subscribe(refresh)


def get_state():
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
    background_tasks.create(handle_user_input(message))
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


ui.run(port=11011, show=False)
