from surrealdb import Surreal
from os import path

import traceback
import config
import glob
import os

queries = {}
for file in glob.glob(path.join(path.abspath(path.dirname(__file__)), "queries", "**", "*.surql"), recursive=True):
    with open(file, 'r') as f:
        queries[os.path.basename(file).split('.')[0]] = f.read()

def resultExists(result, index: int=0, accept_empty: bool=False):
    return (len(result[index]["result"]) > 0 or accept_empty) and result[index]["status"] == "OK"

def loadQuery(name: str):
    return queries[name]

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