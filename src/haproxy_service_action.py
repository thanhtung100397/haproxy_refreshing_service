class HaproxyServiceAction:
    id: None
    host: None
    port: None
    address: None
    action: None

    def __init__(self, id, host, port, action):
        self.id = id
        self.host = host
        self.port = port
        self.address = host + ':' + str(port)
        self.action = action
