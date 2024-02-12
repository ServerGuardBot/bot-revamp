from database import DBConnection, resultExists
from surrealdb import Surreal

import config
import glob
import os
import re

model_paths = [os.path.basename(f) for f in glob.glob("database/models/*.surql")]
models = [open("database/models/" + f, "r").read() for f in model_paths]

_migration_paths = [os.path.basename(f) for f in glob.glob("database/models/migrations/*.surql")]

async def is_db_setup():
    """
    Checks if the database has been setup.
    """
    try:
        async with Surreal(f'ws://{config.DATABASE_IP}:{config.DATABASE_PORT}/rpc') as db:
            await db.connect()
            await db.signin({
                "user": config.DATABASE_USER,
                "pass": config.DATABASE_PASSWORD,
                "NS": config.DATABASE_NAMESPACE,
                "DB": config.DATABASE_DB,
            })
            result = await db.query(f"SELECT * FROM bot_data:migration_version;")
            if not resultExists(result):
                return False
            return True
    except:
        return False
    return False

async def try_db_setup():
    """
    Checks if the DB is setup, if not, it will search for a .env.setup file
    and if found, will login using details in the file for initial DB setup
    and then delete the .env.setup file.

    Otherwise will attempt any unapplied migrations.
    """
    if not await is_db_setup():
        if os.path.exists(".env.setup"):
            with open(".env.setup", "r") as f:
                lines = f.readlines()
                user = lines[0].strip()
                password = lines[1].strip()
                print(f"Attempting DB setup with user {user}")
                await init_db_setup(user, password)
                await init_models()
            os.remove(".env.setup")
        else:
            # Scan for the presence of setup logins in env
            # and use those if possible
            if os.getenv("DATABASE_USER_SETUP") and os.getenv("DATABASE_PASSWORD_SETUP"):
                print("Attempting DB setup with setup login")
                await init_db_setup(os.getenv("DATABASE_USER_SETUP"), os.getenv("DATABASE_PASSWORD_SETUP"))
                await init_models()
    else:
        await migrate_models()

async def init_db_setup(user: str, password: str):
    """
    Initialize the database and create the namespace and user.
    This assumes that the IP, Port, Namespace & User/Pass have already been specified in the .env file.

    Will require the root user/pass to be specified when calling the function.
    """
    print("Initializing database")
    async with Surreal(f'ws://{config.DATABASE_IP}:{config.DATABASE_PORT}/rpc') as db:
        await db.connect()
        await db.signin({
            "user": user,
            "pass": password,
        })
        await db.query(f"""
            DEFINE NAMESPACE {config.DATABASE_NAMESPACE};
            USE NS {config.DATABASE_NAMESPACE};
            DEFINE DATABASE {config.DATABASE_DB};
            DEFINE USER {config.DATABASE_USER} ON NAMESPACE PASSWORD '{config.DATABASE_PASSWORD}' ROLES OWNER;
        """)

async def init_models():
    """
    Initializes all the models from the models folder.
    Should only be used for first setup.
    """
    async with DBConnection() as db:
        index = 0
        full_query = ""
        for query in models:
            full_query += query + "\n\n"
            index += 1
        
        full_query += "CREATE bot_data:migration_version SET value = 0;"

        results = await db.query(full_query)
        for response in results:
            if response["status"] != "OK":
                print(f"An error occured in one of the results: {response['result']}")

async def migrate_models():
    """
    Applies any migrations from the migrations folder.
    """
    async with DBConnection() as db:
        migration_version_query = await db.query("SELECT * from bot_data:migration_version;")
        migration_version = migration_version_query[0]["result"][0]["value"]
        print(f"Migration Version: {migration_version}")

        migration_paths = []
        latest_version = migration_version
        for migration in _migration_paths:
            ver = re.match(r"(\d+).surql", migration)
            if ver and int(ver.group(1)) > migration_version:
                print(f"Found migration {ver.group(1)}")
                migration_paths.append(migration)
                latest_version = int(ver.group(1))
        migration_paths.sort(key=lambda x: int(x.split(".")[0]))
        # Makes sure the migrations are applied in order.
        migrations = [open("database/models/migrations/" + f, "r").read() for f in migration_paths]

        for query in migrations:
            print(f"Applying migration:\n\n{query}\n\n")
            await db.query(query)
        
        await db.query(f"UPDATE bot_data:migration_version SET value = {latest_version};")