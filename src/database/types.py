from datetime import datetime
from dateutil import parser

def to_datetime(value):
    if isinstance(value, datetime):
        return value
    elif isinstance(value, str):
        return parser.parse(value).replace(tzinfo=None)
    elif value is None:
        return None
    else:
        raise ValueError('Invalid origin type')

# defaults to None if the string is whitespace
def to_string(value: str):
    if value is None:
        return None
    elif isinstance(value, str):
        if value.strip() == "":
            return None
        else:
            return value
    else:
        raise ValueError('Invalid origin type')