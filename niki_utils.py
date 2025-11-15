"""Small reusable helper utilities extracted for DRYness."""

from typing import Tuple, Dict, List


def strip_emotion_suffix(response: str, emotions: List[str] = None) -> Tuple[str, str]:
    """If a response ends with a known emotion token, return (emotion, stripped_response).

    If no emotion suffix is found, returns ("", response).
    """
    if emotions is None:
        emotions = ["HAPPY", "SAD", "CONFUSED"]
    for emotion in emotions:
        if response.endswith(emotion):
            return emotion, response[: -len(emotion)]
    return "", response


def strip_bad_starting_characters(response: str) -> str:
    bad_starting_characters = [".", ",", "!", "?", ";", ":", " "]
    while response and response[0] in bad_starting_characters:
        response = response[1:]
    return response


def mystrip(response: str, emotions: List[str] = None) -> Tuple[str, str]:
    prefix, stripped_response = strip_emotion_suffix(response, emotions=emotions)
    return prefix, strip_bad_starting_characters(stripped_response)


def get_button_and_responses_from_tool_call(
    tool_name: str, photo_list: List[str] = None
) -> Dict[str, str]:
    """Return a mapping of button label -> response string for admin/user UI interactions.

    For photo choice, pass the current photo_list so the helper can construct photo buttons.
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
    else:
        return {}
