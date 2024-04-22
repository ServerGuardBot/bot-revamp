from database import DBConnection, resultExists
from surrealdb import Surreal
from os import path

import subprocess
import config
import glob
import os
import re

migrations_exec = os.path.join(os.path.expanduser("~"), ".cargo", "bin", "surrealdb-migrations")

async def setup_db():
    subprocess.run(
        [
            migrations_exec,
            "apply",
            "--ns",
            config.DATABASE_NAMESPACE,
            "--db",
            config.DATABASE_DB,
            "--username",
            config.DATABASE_USER,
            "--password",
            config.DATABASE_PASSWORD,
            "--url",
            f"{config.DATABASE_IP}:{config.DATABASE_PORT}",
        ]
    )
    async with DBConnection() as db:
        analyzers = open(path.join(path.abspath(path.dirname(__file__)), "analyzers.surql"), "r").read()
        await db.query(analyzers)