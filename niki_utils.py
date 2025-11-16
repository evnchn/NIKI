"""
NIKI Utilities Module

This module contains small reusable helper functions for text processing,
UI components, and tool response mappings used throughout the NIKI Photo Booth.
"""

from nicegui import ui


def strip_emotion_suffix(response: str, emotions: list[str] | None = None) -> tuple[str, str]:
    """
    Strip emotion suffix from AI response if present.

    Checks if the response ends with a known emotion token and returns
    the emotion and stripped response separately.

    Args:
        response: AI response text
        emotions: List of emotion tokens to check for

    Returns:
        tuple: (emotion, stripped_response) or ("", response) if no emotion found
    """
    if emotions is None:
        emotions = ["HAPPY", "SAD", "CONFUSED"]

    for emotion in emotions:
        if response.endswith(emotion):
            return emotion, response[: -len(emotion)]

    return "", response


def strip_bad_starting_characters(response: str) -> str:
    """
    Remove unwanted starting characters from text.

    Strips punctuation and whitespace from the beginning of responses.

    Args:
        response: Text to clean

    Returns:
        str: Cleaned text
    """
    bad_starting_characters = [".", ",", "!", "?", ";", ":", " "]
    while response and response[0] in bad_starting_characters:
        response = response[1:]
    return response


def mystrip(response: str, emotions: list[str] | None = None) -> tuple[str, str]:
    """
    Combined text cleaning function.

    Strips emotion suffix and bad starting characters from AI responses.

    Args:
        response: AI response text
        emotions: List of emotion tokens

    Returns:
        tuple: (emotion, cleaned_response)
    """
    prefix, stripped_response = strip_emotion_suffix(response, emotions=emotions)
    return prefix, strip_bad_starting_characters(stripped_response)


def my_button(text, *, on_click=None):
    """
    Create a styled button for the NIKI interface.

    Creates a white button with teal text matching the application theme.

    Args:
        text: Button label text
        on_click: Click handler function

    Returns:
        NiceGUI button element
    """
    return ui.button(text, color="white", on_click=on_click).classes("text-[#006160]")


def mydisplay(line1, line2):
    """
    Display two lines of text in a centered column layout.

    Used for kiosk mode displays with large, centered text.

    Args:
        line1: First line (larger text)
        line2: Second line (smaller text)
    """
    with ui.column().classes("aspect-3/2 w-full items-center"):
        ui.space()
        ui.label(line1).classes("text-6xl")
        ui.label(line2).classes("text-3xl")
        ui.space()


def get_button_and_responses_from_tool_call(tool_name: str, photo_list: list[str] | None = None) -> dict[str, str]:
    """
    Get button labels and response mappings for admin UI interactions.

    Provides appropriate buttons based on the current pending tool call,
    allowing admins to simulate tool responses for testing and control.

    Args:
        tool_name: Name of the pending tool call
        photo_list: Current list of captured photos (for photo selection)

    Returns:
        dict: Mapping of button labels to response strings
    """
    if photo_list is None:
        photo_list = []

    if tool_name == "detect_presence":
        return {"Yes": "yes", "No": "no"}
    elif tool_name == "wait_for_user_engagement":
        return {"Yes": "yes", "No": "no"}
    elif tool_name == "capture_photos":
        return {"Captured": "yes", "Failed": "no"}
    elif tool_name == "print_photo":
        return {"Printed": "yes", "Failed": "no"}
    elif tool_name == "wait_for_user_choose_photo":
        return {f"Photo {i + 1}": str(i) for i in range(len(photo_list))}
    elif tool_name == "show_goodbye_screen_and_wait":
        return {"Next": "yes"}
    else:
        return {}
