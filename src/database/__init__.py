import json

from .surreal import *
from .permissions import UserPermissions
from .database_model import DatabaseModel

from .exceptions import *
from .valkey import valkey

encoder = json.JSONEncoder()
decoder = json.JSONDecoder()

import database.users
import database.servers
import database.statuses
import database.analytics
import database.auth
import database.proxy