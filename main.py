import json
from nicegui import Event, ui, binding
from openai import AsyncAzureOpenAI

from dotenv import load_dotenv
load_dotenv()

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
    }
]

master_message_list = [
    {'role': 'system', 'content': '''You are a helpful assistant. Your responses will be spoken aloud, so keep them short.

Always end your response with one of "HAPPY", "SAD", or "CONFUSED" to indicate your emotional tone.

Always use the wait_for_user_input tool to pause and wait for user input before continuing the conversation. Do not assume user input is available without using this tool.'''}]

render_event = Event()

stop_voice_event = Event()


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

async def handle_admin_choice(framing_quality: str):
    if my_shared_state.pending_tool_call_id:
        details = {
            "good": "The subject is well-centered with appropriate headroom and balanced composition.",
            "bad": "The subject is off-center with poor headroom and unbalanced composition."
        }.get(framing_quality, "Unknown quality")
        master_message_list.append(
            {
                'role': 'tool',
                "type": "function_call_output",
                "tool_call_id": my_shared_state.pending_tool_call_id,
                "content": json.dumps({
                    "framing_quality": framing_quality,
                    "details": details,
                    "random_nonce": json.loads(my_shared_state.pending_tool_args).get("random_nonce", "")
                })
            }
        )
        my_shared_state.pending_tool_call_id = None
        my_shared_state.pending_tool_args = None
        my_shared_state.pending_tool_name = None
        my_shared_state.turn = 'ai'
        await AIloop()

def clear_conversation():
    master_message_list.clear()
    master_message_list.append({'role': 'system', 'content': '''You are a helpful assistant. 
While being helpful, keep responses as short as possible since they will be spoken aloud.
Always end your response with HAPPY, SAD, or CONFUSED to indicate your emotional tone.'''})
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

    main_container = ui.column()

    if mode == 'niki':
        stop_voice_event.subscribe(lambda: ui.run_javascript("window.speechSynthesis.cancel();"))
    if mode == 'admin':
        ui.button('Stop Voice', on_click=lambda: stop_voice_event.emit())
        ui.button('Clear Conversation', on_click=clear_conversation)

    def refresh():
        main_container.clear()
        with main_container:
            for i, msg in enumerate(master_message_list):
                if mode == "niki" and i != len(master_message_list) - 1:
                    continue # niki mode only shows latest message
                role = msg['role']
                content = msg['content']
                if role == 'user':
                    ui.label(f'User: {content}')
                elif role == 'assistant':
                    if 'tool_calls' in msg:
                        for tool_call in msg['tool_calls']:
                            ui.label(f'AI is calling {tool_call["function"]["name"]}...')
                    else:
                        prefix, stripped_content = mystrip(content or '')
                        ui.label(f'AI ({prefix}): {stripped_content}')
                        if mode == "niki":
                            ui.run_javascript(f"window.speechSynthesis.speak(new SpeechSynthesisUtterance(`{stripped_content}`));")
                elif role == 'tool':
                    result = json.loads(content)
                    if 'framing_quality' in result:
                        ui.label(f'Camera framing assessed: {result["framing_quality"]} - {result["details"]}')
                    elif 'user_input' in result:
                        ui.label(f'User input: {result["user_input"]}')
                    else:
                        ui.label(f'Tool result: {result}')
            if my_shared_state.turn == 'user' and my_shared_state.pending_tool_name == 'wait_for_user_input':
                if mode != 'niki':
                    ui.label("User's Turn")
                    user_input = ui.input(placeholder='Type your message...')
                    ui.button('Send', on_click=lambda: handle_user_input(
                        user_input.value))
            elif my_shared_state.turn == 'admin' and my_shared_state.pending_tool_name == 'assess_camera_framing':
                if mode == 'admin':
                    ui.label("Admin: Choose camera framing quality")
                    ui.button('Good Framing', on_click=lambda: handle_admin_choice('good'))
                    ui.button('Bad Framing', on_click=lambda: handle_admin_choice('bad'))
                else:
                    ui.label("Waiting for admin to assess camera framing...")
            elif len(master_message_list) == 1 and mode in ('user', 'admin'):
                ui.button('Start Conversation', on_click=AIloop)
            else:
                ui.label("AI is thinking...")

    refresh()
    render_event.subscribe(refresh)


ui.run()
