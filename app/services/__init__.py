from redis.asyncio import Redis

redis_client : Redis | None = None


async def init_redis():
    global redis_client
    redis_client = Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,  # returns str instead of bytes
    )
    try:
        await redis_client.ping()
    except Exception as e:
        raise RuntimeError(f"Redis is not reachable: {e}")

def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialized")
    return redis_client


def ok(data):
    return {
            "success": "true",
            "error": "",
            "data": data
        } 

def not_ok(error):
    return {
            "success": "false",
            "error": error,
            "data": ""
        } 