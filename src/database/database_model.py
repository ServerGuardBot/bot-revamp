class DatabaseModel:
    def __init__(self, data: dict):
        self.__raw = data
    
    @property
    def id(self):
        raw = self.__raw["id"]
        
        if len(raw.split(":")) > 1:
            return raw.split(":")[1]
        else:
            return raw
    
    @classmethod
    def partial(cls, id: str):
        return cls({
            "id": id
        })