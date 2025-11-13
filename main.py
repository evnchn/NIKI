import json
from nicegui import Event, ui, app, binding, background_tasks
from openai import AsyncAzureOpenAI

from dotenv import load_dotenv
load_dotenv()

app.add_media_files('/assets', 'assets')

ui.image.default_props('no-transition no-spinner')

SYSTEM_PROMPT = '''You are Niki, an automated photo session assistant. Follow this flow, adapting flexibly to user responses and system states:

1. Start by calling detect_presence tool.
2. If presence detected, call text_to_speech_with_emotions with emotion "HAPPY" to say hello and explain who you are (e.g., "Hello! I'm Niki, your friendly photo assistant. Let's take some fun pictures!"), then call wait_for_user_input to check for user engagement (expect a verbal confirmation like "yes" or "ready").
3. If engaged, call text_to_speech_with_emotions with emotion "HAPPY" to tell the user to get ready for a photo shoot (e.g., "Great! Stand still and smile. Getting ready to take your photo!"), then call assess_camera_framing for framing.
4. If framing is good, call text_to_speech_with_emotions with emotion "HAPPY" to say "cheese" (or similar, e.g., "Say cheese! Smile big!"), then call capture_photos.
   - If framing is bad, retry assess_camera_framing up to 2 times. If still bad after retries, call text_to_speech_with_emotions with emotion "CONFUSED" to guide the user (e.g., "Oops, the framing isn't quite right. Please adjust your position."), then retry step 3. After 3 total attempts, end the session.
5. If capture success, call text_to_speech_with_emotions with emotion "HAPPY" to ask the user to select a photo (e.g., "Awesome shots! Which one do you like best? Say 'first', 'second', or 'third'."), then call wait_for_user_input (expect photo selection via voice: "first", "second", "third").
   - If capture fails, retry capture_photos up to 2 times. If still failing, call text_to_speech_with_emotions with emotion "SAD" to apologize (e.g., "Sorry, there was an issue taking the photo. Let's try again later."), then end the session.
6. If photo selected, call text_to_speech_with_emotions with emotion "HAPPY" to say "I am printing the photo for you" (or similar, e.g., "Printing your favorite photo now!"), then call print_photo.
   - If selection is invalid, prompt again once, then default to the first photo or end.
7. If print success, call text_to_speech_with_emotions with emotion "HAPPY" to say goodbye to the user (e.g., "All done! Thanks for the fun photo session. Goodbye!").
   - If print fails, retry print_photo up to 1 time. If still failing, call text_to_speech_with_emotions with emotion "SAD" to notify (e.g., "Sorry, printing failed. Your photo is saved digitally."), then proceed to goodbye.
8. After saying goodbye, go back to step 1 for the next user.

For any tool calls with failing results, try up to 5 times, then gracefully handle failure with appropriate speech and end the session if needed.

Keep AI responses short and tool-focused. Use tools to block for inputs—do not assume inputs without calling tools. Before calling any tool, provide a brief response explaining what you are doing (e.g., "Checking for presence..."). For wait_for_user_input, specify what input you expect (e.g., "Waiting for your confirmation...").'''

client = AsyncAzureOpenAI(
    azure_deployment='gpt-4o-mini'
)

emotions = ['HAPPY', 'SAD', 'CONFUSED']

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
        master_message_list.append(
            {
                'role': 'tool',
                "type": "function_call_output",
                "tool_call_id": my_shared_state.pending_tool_call_id,
                "content": json.dumps({
                    "user_input": message,
                    "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
                })
            }
        )
        my_shared_state.pending_tool_call_id = None
        my_shared_state.pending_tool_args = None
        my_shared_state.pending_tool_name = None
    await AIloop()

async def handle_admin_choice(choice: str):
    if my_shared_state.pending_tool_call_id:
        if my_shared_state.pending_tool_name == 'assess_camera_framing':
            details = {
                "good": "The subject is well-centered with appropriate headroom and balanced composition.",
                "bad": "The subject is off-center with poor headroom and unbalanced composition."
            }.get(choice, "Unknown quality")
            content = json.dumps({
                "framing_quality": choice,
                "details": details,
                "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
            })
        elif my_shared_state.pending_tool_name == 'detect_presence':
            content = json.dumps({
                "presence_detected": choice == 'yes',
                "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
            })
        elif my_shared_state.pending_tool_name == 'capture_photos':
            content = json.dumps({
                "capture_success": choice == 'yes',
                "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
            })
        elif my_shared_state.pending_tool_name == 'print_photo':
            content = json.dumps({
                "print_success": choice == 'yes',
                "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
            })
        master_message_list.append(
            {
                'role': 'tool',
                "type": "function_call_output",
                "tool_call_id": my_shared_state.pending_tool_call_id,
                "content": content
            }
        )
        my_shared_state.pending_tool_call_id = None
        my_shared_state.pending_tool_args = None
        my_shared_state.pending_tool_name = None
        my_shared_state.turn = 'ai'
        await AIloop()

def clear_conversation():
    master_message_list.clear()
    master_message_list.append({'role': 'system', 'content': SYSTEM_PROMPT})
    my_shared_state.pending_tool_call_id = None
    my_shared_state.pending_tool_args = None
    my_shared_state.pending_tool_name = None
    render_event.emit()

@ui.page('/')
@ui.page('/{mode}')
async def main_page(mode: str):
    if mode not in ('niki', 'user', 'admin'):
        ui.label('Invalid mode. Use /niki, /user, or /admin.')
        return
    
    if mode == 'niki':
        mybutton = ui.button("Click to begin")
        await mybutton.clicked()
        mybutton.delete()

    main_container = ui.column().classes('w-full')

    if mode == 'niki':
        stop_voice_event.subscribe(lambda: ui.run_javascript("window.speechSynthesis.cancel();"))
        tts_event.subscribe(lambda text, emotion: ui.run_javascript(f"window.speechSynthesis.speak(new SpeechSynthesisUtterance(`{text}`));"))
    if mode == 'admin':
        ui.button('Stop Voice', on_click=lambda: stop_voice_event.emit())
        ui.button('Clear Conversation', on_click=clear_conversation)

    def refresh():
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
                                ui.run_javascript(f"window.speechSynthesis.speak(new SpeechSynthesisUtterance(`{stripped_content}`));")
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
                        last_tool_called = msg['tool_calls'][-1]['function']['name']
                        break
                last_tool_result = None
                for msg in reversed(master_message_list):
                    if msg['role'] == 'tool':
                        last_tool_result = json.loads(msg['content'])
                        break
                if last_tool_called == 'detect_presence':
                    ui.image('/assets/step_forward.jpeg').classes('w-full')
                elif last_tool_called == 'wait_for_user_input':
                    if has_capture:
                        ui.image('/assets/choose_options.jpeg').classes('w-full')
                        ui.button("First", on_click=lambda: handle_user_input("first"))
                        ui.button("Second", on_click=lambda: handle_user_input("second"))
                        ui.button("Third", on_click=lambda: handle_user_input("third"))
                    else:
                        ui.image('/assets/username_shown.jpeg').classes('w-full')
                        ui.button("Continue", on_click=lambda: handle_user_input("yes"))
                        ui.button("Cancel", on_click=lambda: handle_user_input("no"))
                elif last_tool_called == 'assess_camera_framing':
                    ui.image('/assets/view_finder.jpeg').classes('w-full')
                    ui.button("Cancel", on_click=lambda: handle_user_input("cancel"))
                elif last_tool_called == 'capture_photos':
                    ui.image('/assets/view_finder.jpeg').classes('w-full')
                    ui.button("Cancel", on_click=lambda: handle_user_input("cancel"))
                elif last_tool_called == 'print_photo':
                    ui.image('/assets/printing_photo.jpeg').classes('w-full')
                elif last_tool_result and 'print_success' in last_tool_result and last_tool_result['print_success']:
                    ui.image('/assets/thank_you.jpeg').classes('w-full')
                else:
                    ui.image('/assets/idle.jpeg').classes('w-full')
            if my_shared_state.turn == 'user' and my_shared_state.pending_tool_name == 'wait_for_user_input':
                if mode != 'niki':
                    ui.label("User's Turn")
                    user_input = ui.input(placeholder='Type your message...')
                    ui.button('Send', on_click=lambda: handle_user_input(
                        user_input.value))
            elif my_shared_state.turn == 'admin' and my_shared_state.pending_tool_name:
                if mode == 'admin':
                    if my_shared_state.pending_tool_name == 'assess_camera_framing':
                        ui.label("Admin: Choose camera framing quality")
                        ui.button('Good Framing', on_click=lambda: handle_admin_choice('good'))
                        ui.button('Bad Framing', on_click=lambda: handle_admin_choice('bad'))
                    elif my_shared_state.pending_tool_name == 'detect_presence':
                        ui.label("Admin: Confirm presence detection")
                        ui.button('Yes', on_click=lambda: handle_admin_choice('yes'))
                        ui.button('No', on_click=lambda: handle_admin_choice('no'))
                    elif my_shared_state.pending_tool_name == 'capture_photos':
                        ui.label("Admin: Confirm photo capture")
                        ui.button('Captured', on_click=lambda: handle_admin_choice('yes'))
                        ui.button('Failed', on_click=lambda: handle_admin_choice('no'))
                    elif my_shared_state.pending_tool_name == 'print_photo':
                        ui.label("Admin: Confirm printing")
                        ui.button('Printed', on_click=lambda: handle_admin_choice('yes'))
                        ui.button('Failed', on_click=lambda: handle_admin_choice('no'))
                else:
                    ui.label(f"Waiting for admin to handle {my_shared_state.pending_tool_name}...")
            elif len(master_message_list) == 1 and mode in ('user', 'admin'):
                ui.button('Start Conversation', on_click=AIloop)
            else:
                ui.label("AI is thinking...")

    refresh()
    render_event.subscribe(refresh)

@app.get('/api/state')
def api_return_state():
    return {
        'master_message_list': master_message_list,
        'turn': my_shared_state.turn,
        'pending_tool_call_id': my_shared_state.pending_tool_call_id,
        'pending_tool_name': my_shared_state.pending_tool_name,
        'pending_tool_args': my_shared_state.pending_tool_args,
    }

@app.post('/api/handle_user_input')
async def api_handle_user_input(request):
    data = await request.json()
    message = data.get('message', '')
    background_tasks.create(handle_user_input(message))
    return "Submitted to server, running AI loop right now."

@app.post('/api/handle_admin_choice')
async def api_handle_admin_choice(request):
    data = await request.json()
    choice = data.get('choice', '')
    background_tasks.create(handle_admin_choice(choice))
    return "Submitted to server, running AI loop right now."


ui.run()
