import json
from time import time
from fastapi import Request
from fastapi.responses import FileResponse
from nicegui import Event, ui, app, binding, background_tasks
from openai import AsyncAzureOpenAI

from dotenv import load_dotenv
load_dotenv()

from gtts import gTTS
import uuid
import os
import base64
from camera import camera

app.add_media_files('/assets', 'assets')
app.add_media_files('/user_photos', 'user_photos')
app.add_media_files('/chosen_photos', 'chosen_photos')

photo_list = []
chosen_photos = []

if not os.path.exists('chosen_photos'):
    os.makedirs('chosen_photos')

ui.add_css("""
body {
    background-color: #006160;
}
""", shared=True)
ui.label.default_classes("text-white")

def my_button(text, *, on_click=None):
    return ui.button(text, color="white", on_click=on_click).classes('text-[#006160]')

if not os.path.exists('tts'):
    os.makedirs('tts')

ui.image.default_props('no-transition no-spinner')

SYSTEM_PROMPT = '''You are Niki, an automated photo session assistant. Follow this flow, adapting flexibly to user responses and system states:

1. Start by calling detect_presence tool.
2. If presence detected, call text_to_speech_with_emotions with emotion "HAPPY" to say hello and explain who you are (e.g., "Hello! I'm Niki, your friendly photo assistant. Let's take some fun pictures!"), then call wait_for_user_input to check for user engagement (expect a verbal confirmation like "yes" or "ready").
3. If engaged, call text_to_speech_with_emotions with emotion "HAPPY" to tell the user to get ready for a photo shoot (e.g., "Great! Stand still and smile. Getting ready to take your photo!"), then call assess_camera_framing for framing.
4. If framing is good, call text_to_speech_with_emotions with emotion "HAPPY" to say "cheese" (or similar, e.g., "Say cheese! Smile big!"), then call capture_photos.
   - If framing is bad, retry assess_camera_framing up to 2 times. If still bad after retries, call text_to_speech_with_emotions with emotion "CONFUSED" to guide the user (e.g., "Oops, the framing isn't quite right. Please adjust your position."), then retry step 3. After 3 total attempts, end the session.
5. If capture success, call text_to_speech_with_emotions with emotion "HAPPY" to ask the user to select a photo (e.g., "Awesome shots! Which one do you like best? Click on your favorite photo."), then call wait_for_user_choose_photo (expect photo selection via click: index 0, 1, 2, etc.).
   - If capture fails, retry capture_photos up to 2 times. If still failing, call text_to_speech_with_emotions with emotion "SAD" to apologize (e.g., "Sorry, there was an issue taking the photo. Let's try again later."), then end the session.
6. If photo selected, call text_to_speech_with_emotions with emotion "HAPPY" to say "I am printing the photo for you" (or similar, e.g., "Printing your favorite photo now!"), then call print_photo.
   - If selection is invalid, prompt again once, then default to the first photo or end.
7. If print success, call text_to_speech_with_emotions with emotion "HAPPY" to say goodbye to the user (e.g., "All done! Thanks for the fun photo session. Goodbye!").
   - If print fails, retry print_photo up to 1 time. If still failing, call text_to_speech_with_emotions with emotion "SAD" to notify (e.g., "Sorry, printing failed. Your photo is saved digitally."), then proceed to goodbye.
8. After saying goodbye, go back to step 1 for the next user.

For any tool calls with failing results, try up to 5 times, then gracefully handle failure with appropriate speech and end the session if needed.

Keep AI responses short and tool-focused. Use tools to block for inputs—do not assume inputs without calling tools. Before calling any tool, provide a brief response explaining what you are doing (e.g., "Checking for presence..."). For wait_for_user_input, specify what input you expect (e.g., "Waiting for your confirmation..."). For wait_for_user_choose_photo, always respond positively about the choice.'''

client = AsyncAzureOpenAI(
    azure_deployment='gpt-4o-mini'
)

emotions = ['HAPPY', 'SAD', 'CONFUSED']

latest_tts_path = None

capture_done = False

def generate_tts(text, emotion=None):
    global latest_tts_path
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join('tts', filename)
    tts = gTTS(text)
    tts.save(filepath)
    media_path = f'/tts/{filename}'
    app.add_media_file(url_path=media_path, local_file=filepath)
    latest_tts_path = media_path
    return media_path

def play_tts(text, emotion=None):
    media_path = generate_tts(text, emotion)
    ui.run_javascript(f"window.currentAudio = new Audio('{media_path}'); window.currentAudio.play();")

def strip_emotion_suffix(response: str) -> str:
    for emotion in emotions:
        if response.endswith(emotion):
            return emotion, response[:-len(emotion)]
    return "", response

def strip_bad_starting_characters(response: str) -> str:
    bad_starting_characters = ['.', ',', '!', '?', ';', ':', ' ']
    while response and response[0] in bad_starting_characters:
        response = response[1:]
    return response

def mystrip(response: str) -> str:
    prefix, stripped_response = strip_emotion_suffix(response)
    return prefix, strip_bad_starting_characters(stripped_response)

tools = [
    {
        "type": "function",
        "function": {
            "name": "assess_camera_framing",
            "description": "Check if the camera framing is good for taking a portrait photo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_user_input",
            "description": "Wait for the user to provide input before continuing the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "random_nonce": {
                        "type": "string",
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
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
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
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
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
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
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
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
                        "description": "A random nonce to ensure uniqueness of the request."
                    },
                },
                "required": ["random_nonce"],
                "additionalProperties": False,
            },
            'strict': True,
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
                        "description": "The text to speak to the user."
                    },
                    "emotion": {
                        "type": "string",
                        "enum": ["HAPPY", "SAD", "CONFUSED"],
                        "description": "The emotion to convey in the speech."
                    }
                },
                "required": ["text", "emotion"],
                "additionalProperties": False,
            },
            'strict': True,
        },
    }
]

def get_button_and_responses_from_tool_call(tool_name):
    if tool_name == 'assess_camera_framing':
        return {'Good Framing': 'good', 'Bad Framing': 'bad'}
    elif tool_name == 'detect_presence':
        return {'Yes': 'yes', 'No': 'no'}
    elif tool_name == 'capture_photos':
        return {'Captured': 'yes', 'Failed': 'no'}
    elif tool_name == 'print_photo':
        return {'Printed': 'yes', 'Failed': 'no'}
    elif tool_name == 'wait_for_user_choose_photo':
        return {f'Photo {i+1}': str(i) for i in range(len(photo_list))}
    else:
        return {}

master_message_list = [
    {
        'role': 'system',
        'content': SYSTEM_PROMPT
    }
]

render_event = Event()

stop_voice_event = Event()

tts_event = Event()


class SharedState:
    turn = binding.BindableProperty(on_change=render_event.emit)
    pending_tool_call_id = binding.BindableProperty()
    pending_tool_args = binding.BindableProperty()
    pending_tool_name = binding.BindableProperty()

    def __init__(self):
        self.turn = 'user'  # or 'ai' or 'admin'
        self.pending_tool_call_id = None
        self.pending_tool_args = None
        self.pending_tool_name = None


my_shared_state = SharedState()

render_event.subscribe(lambda: print(
    f"Turn changed to: {my_shared_state.turn}"))


async def AIloop():
    my_shared_state.turn = 'ai'
    agent_continue = True
    while agent_continue:
        # save master_message_list to .debug.json
        with open('.debug.json', 'w') as f:
            json.dump(master_message_list, f, indent=2)
        result = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=master_message_list,
            tools=tools,
        )
        if result.choices[0].message.tool_calls:
            master_message_list.append(result.choices[0].message.to_dict())
            tool_calls_handled = False
            for tool_call in result.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                if tool_name == 'assess_camera_framing':
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = 'admin'
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == 'wait_for_user_input':
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = 'user'
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == 'wait_for_user_choose_photo':
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = 'user'
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name in ['detect_presence', 'capture_photos', 'print_photo']:
                    my_shared_state.pending_tool_call_id = tool_call.id
                    my_shared_state.pending_tool_args = tool_args
                    my_shared_state.pending_tool_name = tool_name
                    my_shared_state.turn = 'admin'
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == 'text_to_speech_with_emotions':
                    # Non-blocking TTS
                    args = json.loads(tool_args)
                    text = args['text']
                    emotion = args['emotion']
                    master_message_list.append(
                        {'role': 'tool',
                         "type": "function_call_output",
                         "tool_call_id": tool_call.id,
                         "content": json.dumps({"success": True, "text": text, "emotion": emotion})
                         }
                    )
                    tts_event.emit(text, emotion)
                    tool_calls_handled = True
                    # Continue the loop for non-blocking
                else:
                    master_message_list.append(
                        {'role': 'tool',
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "error": f"Unknown tool: {tool_name}"
                            })
                         })
            if not tool_calls_handled:
                continue
            # If tool_calls_handled, we are waiting for user input, so break the while
        elif result.choices[0].message.content:
            master_message_list.append(
                {'role': 'assistant', 'content': result.choices[0].message.content})
        elif result.choices[0].message.refusal:
            master_message_list.append(
                {'role': 'assistant', 'content': result.choices[0].message.refusal})
        render_event.emit()

async def handle_user_input(message: str):
    if my_shared_state.pending_tool_call_id:
        random_nonce = json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
        if my_shared_state.pending_tool_name == 'wait_for_user_input':
            content = json.dumps({
                "user_input": message,
                "random_nonce": random_nonce
            })
        elif my_shared_state.pending_tool_name == 'wait_for_user_choose_photo':
            content = json.dumps({
                "chosen_photo": message,
                "random_nonce": random_nonce
            })
        elif my_shared_state.pending_tool_name == 'assess_camera_framing':
            details = {
                "good": "The subject is well-centered with appropriate headroom and balanced composition.",
                "bad": "The subject is off-center with poor headroom and unbalanced composition."
            }.get(message, "Unknown quality")
            content = json.dumps({
                "framing_quality": message,
                "details": details,
                "random_nonce": random_nonce
            })
        elif my_shared_state.pending_tool_name == 'detect_presence':
            content = json.dumps({
                "presence_detected": message == 'yes',
                "random_nonce": random_nonce
            })
        elif my_shared_state.pending_tool_name == 'capture_photos':
            content = json.dumps({
                "capture_success": message == 'yes',
                "random_nonce": random_nonce
            })
        elif my_shared_state.pending_tool_name == 'print_photo':
            content = json.dumps({
                "print_success": message == 'yes',
                "random_nonce": random_nonce
            })
        else:
            content = json.dumps({
                "error": f"Unknown tool response: {message}",
                "random_nonce": random_nonce
            })
        master_message_list.append(
            {
                'role': 'tool',
                "type": "function_call_output",
                "tool_call_id": my_shared_state.pending_tool_call_id,
                "content": content
            }
        )
        # Handle photo selection
        if my_shared_state.pending_tool_name == 'wait_for_user_choose_photo':
            try:
                index = int(message)
                if 0 <= index < len(photo_list):
                    src = photo_list[index]
                    dst = os.path.join('chosen_photos', os.path.basename(src))
                    os.rename(src, dst)
                    chosen_photos.append(dst)
            except ValueError:
                pass
        my_shared_state.pending_tool_call_id = None
        my_shared_state.pending_tool_args = None
        my_shared_state.pending_tool_name = None
        if my_shared_state.turn == 'admin':
            my_shared_state.turn = 'ai'
    await AIloop()

def clear_conversation():
    global capture_done
    master_message_list.clear()
    master_message_list.append({'role': 'system', 'content': SYSTEM_PROMPT})
    my_shared_state.pending_tool_call_id = None
    my_shared_state.pending_tool_args = None
    my_shared_state.pending_tool_name = None
    photo_list.clear()
    chosen_photos.clear()
    capture_done = False
    render_event.emit()

@ui.page('/')
@ui.page('/{mode}')
async def main_page(mode: str):
    if mode not in ('niki', 'user', 'admin'):
        ui.label('Invalid mode. Use /niki, /user, or /admin.')
        return
    
    if mode == 'niki':
        mybutton = my_button("Click to begin")
        await mybutton.clicked()
        mybutton.delete()

    global capture_done
    cam = camera().classes('w-full')
    cam.set_visibility(False)

    main_container = ui.column().classes('w-full')

    if mode == 'niki':
        tts_event.subscribe(lambda text, emotion: play_tts(text, emotion))
        stop_voice_event.subscribe(lambda: ui.run_javascript("if (window.currentAudio) { window.currentAudio.pause(); window.currentAudio.currentTime = 0; }"))
    if mode == 'admin':
        my_button('Stop Voice', on_click=lambda: stop_voice_event.emit())
        my_button('Clear Conversation', on_click=clear_conversation)

    def refresh():
        global capture_done
        last_tool_called = None
        main_container.clear()
        with main_container:
            if mode != 'niki':
                for i, msg in enumerate(master_message_list):
                    if mode == "niki" and i != len(master_message_list) - 1:
                        continue # niki mode only shows latest message
                    role = msg['role']
                    content = msg['content']
                    if role == 'user':
                        ui.label(f'User: {content}')
                    elif role == 'assistant':
                        content = msg.get('content')
                        if content:
                            prefix, stripped_content = mystrip(content)
                            ui.label(f'AI ({prefix}): {stripped_content}')
                            if mode == "niki":
                                play_tts(stripped_content, prefix)
                        if 'tool_calls' in msg:
                            for tool_call in msg['tool_calls']:
                                if tool_call["function"]["name"] != 'text_to_speech_with_emotions':
                                    ui.label(f'AI is calling {tool_call["function"]["name"]}...')
                    elif role == 'tool':
                        result = json.loads(content)
                        if 'framing_quality' in result:
                            ui.label(f'Camera framing assessed: {result["framing_quality"]} - {result["details"]}')
                        elif 'user_input' in result:
                            ui.label(f'User input: {result["user_input"]}')
                        elif 'chosen_photo' in result:
                            ui.label(f'Chosen photo: {result["chosen_photo"]}')
                        elif 'presence_detected' in result:
                            ui.label(f'Presence detected: {result["presence_detected"]}')
                        elif 'capture_success' in result:
                            ui.label(f'Photo capture success: {result["capture_success"]}')
                        elif 'print_success' in result:
                            ui.label(f'Print success: {result["print_success"]}')
                        elif 'text' in result and 'emotion' in result:
                            ui.label(f'AI ({result["emotion"]}): {result["text"]}')
                        else:
                            ui.label(f'Tool result: {result}')
            else:
                # Determine if capture has happened
                has_capture = any(msg.get('role') == 'assistant' and 'tool_calls' in msg and any(tc['function']['name'] == 'capture_photos' for tc in msg['tool_calls']) for msg in master_message_list)
                last_tool_called = None
                for msg in reversed(master_message_list):
                    if msg['role'] == 'assistant' and 'tool_calls' in msg:
                        for tc in reversed(msg['tool_calls']):
                            if tc['function']['name'] != 'text_to_speech_with_emotions':
                                last_tool_called = tc['function']['name']
                                break
                        if last_tool_called:
                            break
                last_tool_result = None
                for msg in reversed(master_message_list):
                    if msg['role'] == 'tool':
                        last_tool_result = json.loads(msg['content'])
                        break
                if last_tool_result and 'print_success' in last_tool_result and last_tool_result['print_success']:
                    ui.image('/assets/thank_you.jpeg').classes('w-full')
                elif last_tool_called == 'detect_presence':
                    ui.image('/assets/step_forward.jpeg').classes('w-full')
                elif last_tool_called == 'wait_for_user_choose_photo':
                    with ui.row().classes("w-full"):
                        for i, photo in enumerate(photo_list):
                            img = ui.image(f'/user_photos/{os.path.basename(photo)}').classes('w-1/3')
                            img.on('click', lambda e, i=i: handle_user_input(str(i)))
                elif last_tool_called == 'assess_camera_framing':
                    my_button("Cancel", on_click=lambda: handle_user_input("cancel"))
                elif last_tool_called == 'capture_photos':
                    my_button("Cancel", on_click=lambda: handle_user_input("cancel"))
                elif last_tool_called == 'print_photo':
                    ui.image('/assets/printing_photo.jpeg').classes('w-full')
                else:
                    ui.image('/assets/idle.jpeg').classes('w-full')
            if my_shared_state.turn == 'user' and my_shared_state.pending_tool_name == 'wait_for_user_input':
                if mode != 'niki':
                    ui.label("User's Turn")
                    user_input = ui.input(placeholder='Type your message...')
                    my_button('Send', on_click=lambda: handle_user_input(
                        user_input.value))
            elif my_shared_state.turn == 'user' and my_shared_state.pending_tool_name == 'wait_for_user_choose_photo':
                with ui.row():
                    for i, photo in enumerate(photo_list):
                        img = ui.image(f'/user_photos/{os.path.basename(photo)}').classes('w-1/3')
                        img.on('click', lambda e, i=i: handle_user_input(str(i)))
            elif my_shared_state.turn == 'admin' and my_shared_state.pending_tool_name:
                button_and_responses = get_button_and_responses_from_tool_call(my_shared_state.pending_tool_name)
                if mode == 'admin':
                    ui.label(f"Admin: Choose for {my_shared_state.pending_tool_name}")
                    for button_text, response in button_and_responses.items():
                        my_button(button_text, on_click=lambda r=response: handle_user_input(r))
                else:
                    ui.label(f"Waiting for admin to handle {my_shared_state.pending_tool_name}...")
            elif len(master_message_list) == 1 and mode in ('user', 'admin'):
                my_button('Start Conversation', on_click=AIloop)
            else:
                ui.label("AI is thinking...")

        if last_tool_called in ['assess_camera_framing', 'capture_photos']:
            cam.set_visibility(True)
            if last_tool_called == 'capture_photos' and not capture_done:
                cam.capture()
                capture_done = True
        else:
            cam.set_visibility(False)

    refresh()
    render_event.subscribe(refresh)

@app.get('/api/state')
def api_return_state():
    print("API state requested at time:", time())
    return {
        'master_message_list': master_message_list,
        'turn': my_shared_state.turn,
        'pending_tool_call_id': my_shared_state.pending_tool_call_id,
        'pending_tool_name': my_shared_state.pending_tool_name,
        'pending_tool_args': my_shared_state.pending_tool_args,
        'latest_tts_path': latest_tts_path,
        'button_and_responses': get_button_and_responses_from_tool_call(my_shared_state.pending_tool_name) if my_shared_state.pending_tool_name else {},
    }

@app.post('/api/handle_user_input')
async def api_handle_user_input(request: Request):
    data = await request.json()
    message = data.get('message', '')
    background_tasks.create(handle_user_input(message))
    return "Submitted to server, running AI loop right now."

@app.post('/api/save_photo')
async def save_photo(request: Request):
    data = await request.json()
    image_data = data['b64url']
    print("image_data preview:", image_data[:30], "...")
    header, encoded = image_data.split(',', 1)
    if header == 'data:image/jpeg;base64' or header == 'data:image/jpg;base64':
        filetype = 'jpg'
    else:
        filetype = 'png'
    image_bytes = base64.b64decode(encoded)
    os.makedirs('user_photos', exist_ok=True)
    filename = f"user_photos/photo_{int(time())}.{filetype}"
    photo_list.append(filename)
    with open(filename, 'wb') as f:
        f.write(image_bytes)
    return {"success": True, "filename": filename}

@ui.page('/xiaomicam/photo')
def download_photo():
    # show all chosen photos for download
    with ui.column():
        if chosen_photos:
            for photo in chosen_photos:
                ui.image(f'/chosen_photos/{os.path.basename(photo)}').classes('w-1/3')
                ui.label(f'Download {os.path.basename(photo)}:')
                ui.link(f'/chosen_photos/{os.path.basename(photo)}', f'/chosen_photos/{os.path.basename(photo)}')
        else:
            ui.label('No chosen photos available for download.')

@ui.page("/test/camera")
def test_camera_page():
    cam = camera().classes('w-full')
    ui.button("Capture", on_click=lambda: cam.capture())

ui.run(port=11011, show=False)
