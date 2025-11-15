from nicegui.element import Element


class camera(Element, component='camera.js'):

    def __init__(self) -> None:
        super().__init__()

    def capture(self):
        self.run_method('capture')