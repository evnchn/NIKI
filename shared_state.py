"""
Shared State Management Module

This module provides reactive state management for the NIKI Photo Booth application.
Uses NiceGUI's bindable properties to enable automatic UI updates when state changes.

The SharedState class maintains the current conversation turn, pending tool calls,
and interruption state for coordinating between AI processing and UI interactions.
"""

from nicegui import binding


class SharedState:
    """
    Reactive shared state for application coordination.

    Uses NiceGUI bindable properties to automatically trigger UI updates
    when state values change. Maintains conversation flow state and pending
    tool call information.

    Attributes:
        turn: Current conversation turn ('user', 'ai', or 'admin')
        pending_tool_call_id: ID of currently pending tool call
        pending_tool_args: Arguments for pending tool call
        pending_tool_name: Name of pending tool
        is_interrupting: Flag indicating if conversation is interrupted
        interrupted_tool_call_message: Stored interrupted tool call message
    """

    # Bindable properties that trigger UI updates on change
    turn = binding.BindableProperty()
    pending_tool_call_id = binding.BindableProperty()
    pending_tool_args = binding.BindableProperty()
    pending_tool_name = binding.BindableProperty()

    def __init__(self):
        """Initialize shared state with default values."""
        self.turn = "user"  # Current turn: 'user', 'ai', or 'admin'
        self.pending_tool_call_id = None  # ID of pending tool call
        self.pending_tool_args = None  # Arguments for pending tool call
        self.pending_tool_name = None  # Name of pending tool
        self.is_interrupting = False  # Flag for conversation interruption
        self.interrupted_tool_call_message = None  # Stored interrupted message
