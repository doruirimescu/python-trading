from abc import ABC, abstractclassmethod
class Session(ABC):
    def __init__(self, client):
        self.client = client

    @abstractclassmethod
    def login(self, username, password):
        pass

    @abstractclassmethod
    def logout(self):
        pass

    @abstractclassmethod
    def __del__(self):
        pass

class XTBSession(Session):
    def __init__(self, client):
        Session.__init__(self, client)

    def login(self, username, password):
        self.client.login(username, password, mode="demo")
        return self.client

    def logout(self):
        self.client.logout()

    def __del__(self):
        self.client.logout()

client = None
x = XTBSession(client)
