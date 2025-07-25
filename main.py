from loguru import logger

from typing import Annotated
from ipaddress import ip_address
from pydantic import BaseModel
from uuid import UUID

from fastapi import FastAPI, Header, Depends, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import uvicorn
from contextlib import asynccontextmanager
from aiohttp import ClientSession

import db
from static import config
from api import matsuri, blrec
from db.models import *

import subtitle
from subtitle.utils import add_subtitles, add_subtitles_all

class BlrecWebhookData(BaseModel):
    'BLREC Webhook的数据格式'
    id: UUID
    date: str
    type: str
    data: dict


@asynccontextmanager
async def lifespan(_app):
    '生命周期管理'
    config.load()
    scheduler = await subtitle.init()
    await db.init_db()

    yield

    await db.close()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
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
    elif event_type in ("LiveEndedEvent", "RecordingFinishedEvent"):
        # 添加一个Recording Finished, 防止出现断了推流但没下播导致的更新延迟
        # 录制结束
        await blrec.end_clip(data)
    elif event_type == "RawDanmakuFileCompletedEvent":
        # 原始弹幕完成
        await blrec.update_clip(data)
    return {"code": 200, "message": "Mua~"}


### 手动刷新接口
@app.post("/refresh/clip/{clip_id}")
async def refresh_clip(clip_id: UUID, ip_check=Depends(check_ip)):
    '刷新片段信息'
    res_data = await matsuri.refresh_clip(clip_id)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Clip not found.")


@app.post("/delete/clip/{clip_id}")
async def delete_clip(clip_id: UUID, ip_check=Depends(check_ip)):
    '删除片段信息'
    res_data = await matsuri.delete_clip(clip_id)
    if res_data:
        return res_data
    else:
        raise HTTPException(status_code=404, detail="Clip not found.")


### 字幕更新相关
@app.post("/subtitle/update")
async def update_subtitles(clip_id:str, bvid:str, _check=Depends(check_ip)):
    '手动更新字幕'
    await add_subtitles(clip_id=clip_id, bvid=bvid)
    return JSONResponse(content={})

@app.post("/subtitle/update/all")
async def update_all_subtitles(forced=False, _check=Depends(check_ip)):
    '自动更新字幕'
    await add_subtitles_all(forced=forced)
    return JSONResponse(content={})


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
        <h1 class="normal_text">你已经被标记了（盯……）</h1>
        <p class="normal_text">这个页面只是用来测试的，如果你找到了这里，那就说明你知道得太多了……</p>
        <p class="normal_text"><a href="//beian.miit.gov.cn">桂ICP备2025066596号</a></p>
    </body>
</html>
"""
    return res_data

# Channel
@app.get("/channel")
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
    'Clip ID -> 所有弹幕(包括礼物)'
    res_data = await matsuri.get_clip_id_comments(id)
    res.headers['Cache-Control'] = 'max-age=31536000'
    return res_data

@app.get("/clip/{id}/subtitles")
async def get_clip_id_subtitles(id:str, res:Response):
    'Clip ID -> 该场直播的语音识别字幕'
    res_data = await matsuri.get_clip_id_comments(id)
    res.headers['Cache-Control'] = 'max-age=31536000'
    return res_data

# Viewer
async def check_origin(req: Request):
    '检测Origin是否合规'
    request_origin = req.headers.get('origin', None)
    allow_origin_list = config.app.get('allow_origin_list', None)

    if not allow_origin_list:
        # 老版设置
        safe_origin = config.app['safe_origin']
        return (safe_origin in request_origin)
    else:
        # 新版设置
        for safe_origin in allow_origin_list:
            if safe_origin in request_origin:
                return True

    # 如果都不对
    raise HTTPException(
        status_code=403, 
        detail=f"Request origin {request_origin} is unauthorized."
    )

async def check_token(req: Request):
    '检查验证码'
    recaptcha_token = req.headers.get('token', None)
    request_ip = ip_address(req.client.host)
    if recaptcha_token:
        # 检查一下是不是要除了第一页以外的页数
        # 不然获取第二页的时候就会因为验证码超时报错了..
        page = int(req.query_params.get('page', 0))
        logger.debug(f"Requiring page {page}")
        if page >= 2:
            return True
        # 跟google验证一下
        async with ClientSession() as session:
            kwargs = {
                'method': "post",
                'url': "https://www.google.com/recaptcha/api/siteverify", 
                'params': {
                    'secret': config.app['recaptcha_secret'],
                    'response': recaptcha_token,
                    'remoteip': request_ip
                },
            }
            async with session.request(**kwargs) as res:
                response = await res.json()
                logger.debug(f"reCAPTCHA: {response}")
                if res.ok and response.get('success', False):
                    return True

    # 如果都不对
    raise HTTPException(
        status_code=403,
        detail=f"Token error."
    )

async def check_search(req: Request):
    '发起搜索时检查Origin和token'
    return (await check_origin(req)) and (await check_token(req))

@app.get("/viewer/{mid}")
async def get_viewer_mid(mid:int, page:int, _check=Depends(check_search)):
    'MID -> 对应mid发送的弹幕'
    res_data = await matsuri.get_viewer_mid(mid, page)
    return res_data

@app.get("/search/{danmaku}")
async def get_search_danmaku(danmaku:str, page:int, _check=Depends(check_search)):
    'danmaku -> 全局搜索到的弹幕'
    res_data = await matsuri.get_search_danmaku(danmaku, page)
    return res_data

# Off Comments, 这个因为mid匹配的范围太广会覆盖其他路由，不能放前面
@app.get("/{mid}/{date}")
async def get_mid_date(mid:int, date:str):
    '主播MID+日期 -> 在该日期及一天以后的时间段内的下播弹幕'
    res_data = await matsuri.get_mid_date(mid, date)
    return res_data

if __name__ == "__main__":
    uvicorn.run(app=app, host=config.app['host'], port=config.app['port'])
