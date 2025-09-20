import json, datetime
from fastapi import Request, Response, HTTPException
from loguru import logger
from ipaddress import ip_address
from aiohttp import ClientSession

from static import config
from db.models import Token

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
    # 初始化
    time_now = datetime.datetime.now(tz=datetime.timezone.utc)
    timedelta = datetime.timedelta(seconds=config.app['token_exp'])
    is_valid = False

    # 获取验证码
    recaptcha_token = req.headers.get('token', None)
    request_ip = ip_address(req.client.host)
    if recaptcha_token:
        # 检查一下是不是要除了第一页以外的页数
        # 不然获取第二页的时候就会因为验证码超时报错了..
        # page = int(req.query_params.get('page', 0))
        # ## 高级请求的page写在body里，再检查一下
        # if page == 0:
        #     try:
        #         req_body = json.loads(await req.body())
        #         page = req_body.get('page', 0)
        #     except:
        #         pass
        # logger.debug(f"Requiring page {page}")
        # if page >= 1:
        #     return True
        token_data = await Token.get_or_none(token=recaptcha_token)
        if token_data is None:
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
                        is_valid = True
        else:
            # 检查日期
            if time_now <= token_data.expires:
                is_valid = True
        
    if is_valid:
        # 如果没问题
        await Token.update_or_create({
            'token': recaptcha_token,
            'expires': time_now + timedelta
            })
        logger.debug(f"Updating token {recaptcha_token}, expiring at {time_now}")
        return True
    else:
        # 如果都不对
        logger.debug(f"Invalid token {recaptcha_token}")
        await Token.filter(token=recaptcha_token).delete()
        raise HTTPException(
            status_code=403,
            detail=f"Token error."
        )

