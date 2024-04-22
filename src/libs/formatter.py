from string import Formatter

import guilded
import random

class FormatterValue:
    # FormatterValue class ensures all values passed to a template
    # are simple to use/more powerful
    def __init__(self, value):
        self.__raw = value
        
        if type(value) is str:
            value: str
            self.upper = value.upper()
            self.lower = value.lower()
            self.title = value.title()
            self.capitalize = value.capitalize()
        elif type(value) is dict:
            value: dict
            for k, v in value.items():
                setattr(self, k, FormatterValue(v))
    
    def __str__(self):
        return self.__raw

class SGFormatter(Formatter):
    def __init__(
        self,
        server: guilded.Server=None,
    ):
        self.server = server
        super(SGFormatter, self).__init__()

    def format_field(self, value, spec):
        if spec.startswith("repeat"):
            template = spec.partition(':')[-1]
            if type(value) is dict:
                value = value.items()
            return ''.join([template.format(item=item) for item in value])
        if spec.startswith("if"):
            return (value and spec.partition(':')[-1]) or ''
        if spec.startswith("random"):
            if type(value) is str:
                value = value.split(',')
            return random.choice(value)
        if self.server is not None:
            if spec.startswith("channel"):
                c = self.server.get_channel(value)
                return f"<#{c.id}>"
            if spec.startswith("role"):
                r = self.server.get_role(value)
                return f"<@&{r.id}>"
        if spec.startswith("user"):
            return f"<@{value}>"
        return super(SGFormatter, self).format_field(value, spec)