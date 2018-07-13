class ConsulServiceInfo:
    id = None
    host = None
    port = None
    address = None

    def __init__(self, id, host, port):
        self.id = id
        self.host = host
        self.port = port
        self.address = host + ':' + str(port)
