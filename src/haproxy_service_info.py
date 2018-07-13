class HaproxyServiceInfo:
    id: None
    host: None
    port: None
    address: None
    status: None

    def __init__(self, id, address, status):
        self.id = id
        self.address = address
        host_port = address.split(':')
        self.host = host_port[0]
        self.port = int(host_port[1])
        self.status = status

    def is_active(self):
        return self.status != 'MAINT'
