import tortoise
from tortoise import Tortoise
from static import config
from urllib.parse import quote
from .models import *

async def init_db():
    '初始化数据库'
    user = quote(config.postgres['user'])
    passwd = quote(config.postgres['password'])
    db_host = quote(config.postgres['host'])
    db_port = config.postgres['port']
    database = quote(config.postgres['database'])
    config_db = {
            "connections": {
                "matsuri_db": f"postgres://{user}:{passwd}@{db_host}:{db_port}/{database}"
            },
            "apps": {
                "matsuri_app": {
                    "models": ["db.models"],
                    "default_connection": "matsuri_db",
                }
            },
        }
    await Tortoise.init(config_db)
    await Tortoise.generate_schemas(safe=True)

async def close():
    '关闭数据库连接'
    await tortoise.connections.close_all(discard=False)

async def add_danmaku(danmakus_list, clip_id=None):
    '添加弹幕'
    for kwargs in danmakus_list:
        AllComments.add(clip_id=clip_id, **kwargs)
