from fastapi import FastAPI, Header, Response, HTTPException
from static import config
from tortoise import run_async
import uvicorn
import db
from .api import matsuri, blrec
from models import *

app = FastAPI()


### blrec webhook
@app.post("/rec")
async def rec_handle(data):
    'webhook处理'
    event_type = data['data']['type']
    if event_type == "LiveBeganEvent":
        # 录制开始
        await blrec.start_clip(data)
    elif event_type == "LiveEndedEvent":
        # 录制结束
        await blrec.end_clip(data)
    elif event_type == "DanmakuFileCompletedEvent":
        # 弹幕完成
        await blrec.update_clip(data)
    return {"code": 200, "message": "Mua~"}


### Matsuri前端API
# Index
@app.get("/")
async def get_index():
    '-> 所有频道'
    res_data = """<html lang="zh-cn">
    <head>
        <title>虽然不知道为什么要做这个网页</title>
    </head>
    <body>
        <h1>但是为了保持API的一致性, 既然原作者brainbrush加了那我也放一个</h1>
    </body>
</html>"""
    return res_data

# Channel
@app.get("/channel/")
async def get_channel():
    '-> 所有频道'
    res_data = await matsuri.get_channel_list()
    return res_data

@app.get("/channel/{mid}")
async def get_channel_id(mid:int):
    'Channel ID -> 场次信息'
    res_data = await matsuri.get_channel_id(id)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Channel not found.")

# Clip
@app.get("/clip/{id}")
async def get_clip_id(id:str):
    'Clip ID -> 场次信息'
    res_data = await matsuri.get_id(id)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Clip not found.")

@app.get("/clip/{id}/comments")
async def get_clip_id_comments(id:str, res:Response):
    'Clip ID -> 所有弹幕(去除礼物)'
    res_data = await matsuri.get_clip_id_comments(id)
    res.headers['Cache-Control'] = 'max-age=31536000'
    return res_data

# Viewer
@app.get("/viewer/{mid}")
async def get_viewer_mid(mid:int, page:int, header:Header):
    'MID -> 对应mid发送的弹幕'
    origin = header['origin']
    if not origin or config.app['safe_origin'] not in origin:
        raise HTTPException(status_code=403, detail="Unauthorized.")

if __name__ == "__main__":
    run_async(config.load())
    run_async(db.init_db())
    uvicorn.run(app=app, host=config.app['host'], port=config.app['port'])
