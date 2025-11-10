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
    }
]

master_message_list = [
    {'role': 'system', 'content': '''You are a helpful assistant. 
While being helpful, keep responses as short as possible since they will be spoken aloud.
Always end your response with HAPPY, SAD, or CONFUSED to indicate your emotional tone.'''}]

render_event = Event()

stop_voice_event = Event()


class SharedState:
    turn = binding.BindableProperty(on_change=render_event.emit)

    def __init__(self):
        self.turn = 'user'  # or 'ai'


my_shared_state = SharedState()

render_event.subscribe(lambda: print(
    f"Turn changed to: {my_shared_state.turn}"))


async def post_user_message(message: str):
    master_message_list.append({'role': 'user', 'content': message})
    my_shared_state.turn = 'ai'
    while True:
        result = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=master_message_list,
            tools=tools,
        )
        if result.choices[0].message.tool_calls:
            master_message_list.append(result.choices[0].message.to_dict())
            for tool_call in result.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                if tool_name == 'assess_camera_framing':
                    master_message_list.append(
                        {
                            'role': 'tool',
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "framing_quality": "good",
                                "details": "The subject is well-centered with appropriate headroom and balanced composition.",
                                "random_nonce": json.loads(tool_args).get("random_nonce", "")
                            })
                        })
                else:
                    master_message_list.append(
                        {'role': 'tool',
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({
                                "error": f"Unknown tool: {tool_name}"
                            })
                         })
            continue
        elif result.choices[0].message.content:
            master_message_list.append(
                {'role': 'assistant', 'content': result.choices[0].message.content})
        elif result.choices[0].message.refusal:
            master_message_list.append(
                {'role': 'assistant', 'content': result.choices[0].message.refusal})
        my_shared_state.turn = 'user'
        break

@ui.page('/')
@ui.page('/{mode}')
async def main_page(mode: str):
    if mode not in ('niki', 'user'):
        ui.label('Invalid mode. Use /niki or /user.')
        return
    
    mybutton = ui.button("Click to begin")
    await mybutton.clicked()
    mybutton.delete()

    main_container = ui.column()

    if mode == 'niki':
        stop_voice_event.subscribe(lambda: ui.run_javascript("window.speechSynthesis.cancel();"))
    else:
        ui.button('Stop Voice', on_click=lambda: stop_voice_event.emit())
        ui.button('Clear Conversation', on_click=lambda: [
            master_message_list.clear(),
            master_message_list.append({'role': 'system', 'content': '''You are a helpful assistant.'''},
            render_event.emit())
        ])

    def refresh():
        main_container.clear()
        for i, msg in enumerate(master_message_list):
            if mode == "niki" and i != len(master_message_list) - 1:
                continue # niki mode only shows latest message
            role = msg['role']
            content = msg['content']
            if role == 'user':
                with main_container:
                    ui.label(f'User: {content}')
            elif role == 'assistant':
                with main_container:
                    prefix, stripped_content = mystrip(content or '')
                    ui.label(f'AI ({prefix}): {stripped_content}')
                    if mode == "niki":
                        ui.run_javascript(f"window.speechSynthesis.speak(new SpeechSynthesisUtterance(`{stripped_content}`));")
        if my_shared_state.turn == 'user':
            with main_container:
                if mode != 'niki':
                    ui.label("User's Turn")
                    user_input = ui.input(placeholder='Type your message...')
                    ui.button('Send', on_click=lambda: post_user_message(
                        user_input.value))
        else:
            with main_container:
                ui.label("AI is thinking...")

    refresh()
    render_event.subscribe(refresh)


ui.run()
