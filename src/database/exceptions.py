class NotFound(Exception):
    pass

class ServerNotFound(NotFound):
    pass

class NotInServer(NotFound):
    pass

class DatabaseError(Exception):
    pass