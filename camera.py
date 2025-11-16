"""
Camera Component Module

This module provides a NiceGUI custom element for WebRTC camera capture.
The camera component uses getUserMedia to access the user's camera and
provides a capture method to take photos.

The actual camera interface is implemented in camera.js as a Vue component.
"""

from nicegui.element import Element


class camera(Element, component="camera.js"):
    """
    NiceGUI custom element for camera capture.

    Wraps a WebRTC camera interface that can capture photos from the user's
    webcam. The camera feed is displayed in a video element, and the capture
    method triggers photo capture via JavaScript.
    """

    def __init__(self) -> None:
        """Initialize the camera element."""
        super().__init__()

    def capture(self):
        """
        Capture a photo from the camera.

        Triggers the JavaScript capture method to take a snapshot from
        the current camera feed and emit it as an event.
        """
        self.run_method("capture")
