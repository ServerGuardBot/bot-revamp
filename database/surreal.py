from surrealdb import Surreal

import config

def resultExists(result, index: int=0):
    return len(result[index]["result"]) > 0

def loadQuery(name: str):
    with open(f'database/queries/{name}.surql', 'r') as file:
        return file.read()

class DBConnection:
    async def __aenter__(self):
        self.db = Surreal(f'ws://{config.DATABASE_IP}:{config.DATABASE_PORT}/rpc')
        await self.db.connect()
        await self.db.signin({
            "user": config.DATABASE_USER,
            "pass": config.DATABASE_PASSWORD,
            "NS": config.DATABASE_NAMESPACE,
            "DB": config.DATABASE_DB,
        })

        return self.db
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.db.close()
        self.db = None
        return True