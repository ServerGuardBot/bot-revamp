from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder
from database.exceptions import DatabaseError, NotFound
from surrealdb.ws import SurrealException

from .image import Image

import io
import base64

async def store_image(
    source: str,
    data: bytes,
    expires: str="1d"
) -> Image:
    buffer = io.BytesIO(data)
    buffer.seek(0)
    async with DBConnection() as db:
        try:
            existing_image = await get_image(self, source=source)
        except NotFound:
            try:
                response = await db.query(loadQuery("storeImage"), {
                    "source_url": source,
                    "data": base64.b64encode(buffer.read()).decode("utf-8"),
                    "expires": expires
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(response):
                    return Image(response[0]["result"][0])
        else:
            return existing_image

async def get_image(
    id: str=None,
    source: str=None
):
    if id != None and source != None:
        raise ValueError("Cannot specify both id and source")
    elif id == None and source == None:
        raise ValueError("Must specify either id or source")
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("getImage"), {
                "id": id,
                "source_url": source
            })
        except SurrealException as e:
            raise DatabaseError(str(e))
        else:
            if resultExists(response):
                return Image(response[0]["result"][0])
            else:
                raise NotFound

async def cleanup_images():
    async with DBConnection() as db:
        try:
            response = await db.query(loadQuery("cleanupImages"))
        except SurrealException as e:
            raise DatabaseError(str(e))