## Button->response mapping moved to `niki_utils.get_button_and_responses_from_tool_call`


from nicegui import binding


class SharedState:
    turn = binding.BindableProperty()
    pending_tool_call_id = binding.BindableProperty()
    pending_tool_args = binding.BindableProperty()
    pending_tool_name = binding.BindableProperty()

    def __init__(self):
        self.turn = "user"  # or 'ai' or 'admin'
        self.pending_tool_call_id = None
        self.pending_tool_args = None
        self.pending_tool_name = None
        self.is_interrupting = False
        self.interrupted_tool_call_message = None
