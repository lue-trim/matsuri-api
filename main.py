from typing import Annotated
from fastapi import FastAPI, Header, Depends, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from ipaddress import ip_address
import uvicorn
from pydantic import BaseModel
from tortoise import run_async
from uuid import UUID

import db
from static import config
from api import matsuri, blrec
from db.models import *

class BlrecWebhookData(BaseModel):
    'BLREC Webhook的数据格式'
    id: UUID
    date: str
    type: str
    data: dict

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


### blrec webhook
def check_ip (req: Request):
    request_ip = ip_address(req.client.host)
    allow_ip_list = [ip_address(ip) for ip in config.app['allow_post_ips']]
    if request_ip not in allow_ip_list:
        raise HTTPException(
            status_code=403, 
            detail="You are unauthorized here."
            )
    else:
        return True

@app.post("/rec")
async def rec_handle(data: BlrecWebhookData, ip_check=Depends(check_ip)):
    'webhook处理'
    #data = json.loads(data)
    data = data.dict()
    event_type = data['type']
    if event_type == "LiveBeganEvent":
        # 录制开始
        await blrec.start_clip(data)
    elif event_type == "LiveEndedEvent":
        # 录制结束
        await blrec.end_clip(data)
    elif event_type == "RawDanmakuFileCompletedEvent":
        # 原始弹幕完成
        await blrec.update_clip(data)
    return {"code": 200, "message": "Mua~"}


### Matsuri前端API
# Index
@app.get("/", response_class=HTMLResponse)
async def get_index():
    '-> 所有频道'
    res_data = \
"""
<!DOCTYPE html>
<html lang="zh-cn">
    <head>
        <title>Matsuri API</title>
        <style>
            ::selection {
                background: #80abff80;
            }
            @font-face {
                font-family: "阿里巴巴普惠体 2.0 65 Medium";
                font-weight: 400;
                src: url("https://cdn.jsdelivr.net/gh/lue-trim/lue-trim.github.io/static/font/3rfuFKwVRC0r.woff2") format("woff2"),
                url("https://cdn.jsdelivr.net/gh/lue-trim/lue-trim.github.io/static/font/3rfuFKwVRC0r.woff") format("woff");
                font-display: swap;
            }
            * {
                font-family: "阿里巴巴普惠体 2.0 65 Medium";
            }
            .image_container {
                align-self: center;
                width: 800px;
                height: 600px;
                background-size: cover;
                border-radius: 5%;
            }
            .normal_text {
                align-self: center;
            }
        </style>
    </head>
    <body>
        <h1 class="normal_text">恭喜你抓到了一只雅典娜叽！</h1>
        <img class="image_container" alt="早稻叽" :src="https://i0.hdslb.com/bfs/new_dyn/f77d22df1ecd7e63033618a6f7816da51950658.jpg">
        <p class="normal_text">这个页面只是用来测试的，如果你找到了这里，那就说明你知道得太多了……</p>
    </body>
</html>
"""
    return res_data

# Channel
@app.get("/channel/")
async def get_channel():
    '-> 所有频道'
    res_data = await matsuri.get_channel_list()
    return res_data

@app.get("/channel/{mid}")
async def get_channel_id(mid:int):
    'Channel ID -> 频道基本信息'
    res_data = await matsuri.get_channel_id(mid)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Channel not found.")

@app.get("/channel/{mid}/clips")
async def get_channel_id(mid:int):
    'Channel ID -> 该频道的所有场次'
    res_data = await matsuri.get_channel_id_clips(mid)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Channel not found.")

# Clip
@app.get("/clip/{id}")
async def get_clip_id(id:str):
    'Clip ID -> 场次信息'
    res_data = await matsuri.get_clip_id(id)
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

# Off Comments
@app.get("/{mid}/{date}")
async def get_mid_date(mid:int, date:str):
    '主播MID+日期 -> 在该日期及一天以后的时间段内的下播弹幕'
    res_data = await matsuri.get_mid_date(mid, date)
    return res_data

# Viewer
@app.get("/viewer/{mid}")
async def get_viewer_mid(mid:int, page:int, header:Annotated[str|None,Header()]):
    'MID -> 对应mid发送的弹幕'
    origin = header['origin']
    if not origin or config.app['safe_origin'] not in origin:
        raise HTTPException(status_code=403, detail="Request origin not authorized.")
    res_data = await matsuri.get_viewer_mid(mid, page)
    return res_data

if __name__ == "__main__":
    config.load()
    run_async(db.init_db())
    uvicorn.run(app=app, host=config.app['host'], port=config.app['port'])
    run_async(db.close())
