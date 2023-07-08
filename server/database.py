
import asyncpg

async def connect_to_db():
    connection_pool = await asyncpg.create_pool(
        host="localhost",
        port="5432",
        user="postgres",
        password="Adil@123",
        database="crewWise"
    )
    return connection_pool