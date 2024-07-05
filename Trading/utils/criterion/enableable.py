class Enableable:
    '''
        A class that can be enabled or disabled.
    '''
    def __init__(self, is_enabled: bool = False) -> None:
        self.is_enabled = is_enabled

    def enable(self):
        self.is_enabled = True

    def disable(self):
        self.is_enabled = False
