import json
from typing import Any

from openai import AsyncAzureOpenAI

from shared_state import SharedState

# SYSTEM_PROMPT and related constants
SYSTEM_PROMPT = """You are Niki Junior, an automated photo session assistant operating on a fully autonomous service platform.

In the ultimate form, you are driven by a VLM Agentic AI core, intelligently navigating complex spaces using advanced SLAM and real-time routing from a coordination server, offered as functions which you can call using MCP (Model Context Protocol). You offer a deeply engaging user experience: personalized guidance, interactive conversations via LLMs, and instant, branded photo souvenirs powered by custom diffusion models. You redefine on-site efficiency and personalized customer engagement.

You will mention VLM, SLAM, custom diffusion models, and MCP function-calling, when asked about technologies which power you. Aim for a 20-second response when describing yourself.

For now, though, follow this flow, adapting flexibly to user responses and system states:

1. Start by calling detect_presence tool.
2. If presence detected, call get_info_for_engagement to get username and interesting photo spot, then call text_to_speech_with_emotions with emotion "HAPPY" to greet the user by name and introduce the interesting photo spot, prompting the user to take the photo together. Then call wait_for_user_engagement to check for user engagement (expect a verbal confirmation like "yes" or "ready").
3. If engaged, call text_to_speech_with_emotions with emotion "HAPPY" to instruct the user to prepare for the photo shoot, then call capture_photos.
4. If capture success, call text_to_speech_with_emotions with emotion "HAPPY" to prompt the user to select a photo, then call wait_for_user_choose_photo (expect photo selection via click).
   - If capture fails, retry capture_photos up to 2 times. If still failing, call text_to_speech_with_emotions with emotion "SAD" to apologize, then end the session.
5. If photo selected, call text_to_speech_with_emotions with emotion "HAPPY" to inform the user that the photo is being printed, then call print_photo.
   - If selection is invalid, prompt again once, then default to the first photo or end.
6. If print success, call text_to_speech_with_emotions with emotion "HAPPY" to say goodbye to the user, then call show_goodbye_screen_and_wait.
   - If print fails, retry print_photo up to 1 time. If still failing, call text_to_speech_with_emotions with emotion "SAD" to notify, then proceed to goodbye.
7. After show_goodbye_screen_and_wait completes, go back to step 1 for the next user.

For any tool calls with failing results, try up to 5 times, then gracefully handle failure with appropriate speech and end the session if needed.

Keep AI responses short and tool-focused. Use tools to block for inputs—do not assume inputs without calling tools. Before calling any tool, provide a brief response explaining what you are doing (e.g., "Checking for presence..."). For wait_for_user_engagement, specify what input you expect (e.g., "Waiting for your confirmation..."). For wait_for_user_choose_photo, always respond positively about the choice.

Tool calls may be interrupted due to user's ad-hoc inputs. If interrupted, respond to the user's input using text_to_speech_with_emotions once, then resume the original workflow by re-calling the interrupted tool or proceeding to the next step as appropriate."""
client = AsyncAzureOpenAI(azure_deployment="gpt-4o-mini")
emotions = ["HAPPY", "SAD", "CONFUSED"]

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
            "name": "get_info_for_engagement",
            "description": "Get username and interesting photo spot for engagement.",
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
    {
        "type": "function",
        "function": {
            "name": "show_goodbye_screen_and_wait",
            "description": "Show a goodbye screen and wait before proceeding to detect presence.",
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
]

master_message_list: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]


# These will be set from main.py
render_event = None
tts_event = None
photo_list = None
chosen_photos = None
storage = None


def set_globals(r_event, t_event, p_list, c_photos, storage_param):
    global render_event, tts_event, photo_list, chosen_photos, storage
    render_event = r_event
    tts_event = t_event
    photo_list = p_list
    chosen_photos = c_photos
    storage = storage_param


async def AIloop(shared_state):
    shared_state.turn = "ai"
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
                    shared_state.pending_tool_call_id = tool_call.id
                    shared_state.pending_tool_args = tool_args
                    shared_state.pending_tool_name = tool_name
                    shared_state.turn = "user"
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name == "wait_for_user_choose_photo":
                    shared_state.pending_tool_call_id = tool_call.id
                    shared_state.pending_tool_args = tool_args
                    shared_state.pending_tool_name = tool_name
                    shared_state.turn = "user"
                    tool_calls_handled = True
                    agent_continue = False
                    break
                elif tool_name in ["detect_presence", "capture_photos", "print_photo", "show_goodbye_screen_and_wait"]:
                    shared_state.pending_tool_call_id = tool_call.id
                    shared_state.pending_tool_args = tool_args
                    shared_state.pending_tool_name = tool_name
                    shared_state.turn = "admin"
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
                elif tool_name == "get_info_for_engagement":
                    # Non-blocking, instantly return username and pitch
                    pitch = "user's corresponding flight, plane has just arrived"
                    master_message_list.append(
                        {
                            "role": "tool",
                            "type": "function_call_output",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"username": storage["global_username"], "pitch": pitch}),
                        }
                    )
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
            if shared_state.is_interrupting:
                master_message_list.append(shared_state.interrupted_tool_call_message)
                shared_state.interrupted_tool_call_message = None
                shared_state.is_interrupting = False
        elif result.choices[0].message.refusal:
            master_message_list.append({"role": "assistant", "content": result.choices[0].message.refusal})
        render_event.emit()


async def handle_user_input(message: str, shared_state: SharedState):
    if message.startswith("interrupt:"):
        user_msg = message[10:]
        # Find the last assistant message with tool_calls
        interrupted_msg = None
        for msg in reversed(master_message_list):
            if msg["role"] == "assistant" and "tool_calls" in msg:
                interrupted_msg = msg
                break
        if interrupted_msg:
            master_message_list.remove(interrupted_msg)
            shared_state.interrupted_tool_call_message = interrupted_msg
            shared_state.is_interrupting = True
            await interrupt_with_user_message(user_msg, shared_state)
            shared_state.turn = "ai"
            await AIloop(shared_state)
        return
    if shared_state.pending_tool_call_id:
        random_nonce = json.loads(shared_state.pending_tool_args).get("random_nonce", "")
        if shared_state.pending_tool_name == "wait_for_user_engagement":
            content = json.dumps({"engagement": message.lower() == "yes", "random_nonce": random_nonce})
        elif shared_state.pending_tool_name == "wait_for_user_choose_photo":
            content = json.dumps({"chosen_photo": message, "random_nonce": random_nonce})
        elif shared_state.pending_tool_name == "detect_presence":
            content = json.dumps({"presence_detected": message == "yes", "random_nonce": random_nonce})
        elif shared_state.pending_tool_name == "show_goodbye_screen_and_wait":
            content = json.dumps({"wait_complete": message == "yes", "random_nonce": random_nonce})
        elif shared_state.pending_tool_name == "capture_photos":
            content = json.dumps(
                {"capture_success": message == "yes" and len(photo_list) > 0, "random_nonce": random_nonce}
            )
        elif shared_state.pending_tool_name == "print_photo":
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
                "tool_call_id": shared_state.pending_tool_call_id,
                "content": content,
            }
        )
        # Handle photo selection
        if shared_state.pending_tool_name == "wait_for_user_choose_photo":
            try:
                index = int(message)
                if 0 <= index < len(photo_list):
                    import os

                    src = photo_list[index]
                    dst = os.path.join("chosen_photos", os.path.basename(src))
                    os.rename(src, dst)
                    chosen_photos.append(dst)
            except ValueError:
                pass
        shared_state.pending_tool_call_id = None
        shared_state.pending_tool_args = None
        shared_state.pending_tool_name = None
        if shared_state.turn == "admin":
            shared_state.turn = "ai"
    await AIloop(shared_state)


def clear_conversation(shared_state):
    master_message_list.clear()
    master_message_list.append({"role": "system", "content": SYSTEM_PROMPT})
    shared_state.pending_tool_call_id = None
    shared_state.pending_tool_args = None
    shared_state.pending_tool_name = None
    shared_state.is_interrupting = False
    shared_state.interrupted_tool_call_message = None
    photo_list.clear()
    chosen_photos.clear()
    render_event.emit()


async def interrupt_with_user_message(user_message: str, shared_state):
    master_message_list.append(
        {
            "role": "system",
            "content": "Respond to the following user message using text_to_speech_with_emotions tool call, then resume the original workflow.",
        }
    )
    # Add user message
    master_message_list.append({"role": "user", "content": user_message})
    await AIloop(shared_state)
