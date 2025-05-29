import datetime, traceback

from bilibili_api.video import Video
from bilibili_api.user import User
from bilibili_api import Credential

from aiohttp import ClientSession, ClientTimeout
from loguru import logger

from tortoise.exceptions import MultipleObjectsReturned, DoesNotExist

from static import config
from db.models import Subtitles, ClipInfo
from api.parse import get_cookies, timestamp_to_date, relative_ts_to_time
from api.matsuri import get_clip_id

async def get_credential(cookies_dict=None):
    '获取credential'
    if not cookies_dict:
        cookies_dict = await get_cookies()
    c = Credential(**cookies_dict)
    return c

async def get_video_info(v:Video):
    '从视频中获取信息'
    # 获取视频信息
    video_info = await v.get_info()
    title = video_info['title']
    name = video_info['owner']['name']
    uid = video_info['owner']['mid']

    # 获取所有分区的字幕
    subtitle_list = []
    current_duration = 0
    for page in video_info['pages']:
        # 获取URL
        cid = page['cid']
        subtitle_info = await v.get_subtitle(cid)
        page_subtitle_list = subtitle_info['subtitles']

        # 确认是否存在字幕
        if page_subtitle_list:
            subtitle_url = page_subtitle_list[0]['subtitle_url']

            # 发起请求
            async with ClientSession(timeout=ClientTimeout(None)) as session:
                url = f"https:{subtitle_url}"
                async with session.get(url) as req:
                    res = await req.json()

            # 处理每条字幕的时间
            page_subtitles = res['body']
            for idx, subtitle in enumerate(page_subtitles):
                page_subtitles[idx]['from'] = subtitle['from'] + current_duration
                page_subtitles[idx]['to'] = subtitle['to'] + current_duration

            # 处理列表
            subtitle_list.extend(page_subtitles)
        current_duration += page['duration']

    return {
        "title": title,
        "name": name,
        "uid": uid,
        "subtitle_list": subtitle_list
    }

async def get_video_series(uid:int, sid:int, pn:int, ps=10):
    '获取官方录播合集'
    u = User(uid=uid)
    series_info = await u.get_channel_videos_series(sid=sid, pn=pn, ps=ps)
    return series_info['archives']

async def pair_clip(clip:dict, video_series:list):
    '将回放视频与弹幕站的片段进行匹配'
    # time_title = clip['start_time'].strftime(r"%Y年%m月%d日%H点场")
    clip_title = generate_title(clip['title'], clip['start_time'])

    # 只匹配时间容易出现同一个小时开两场不好判断的问题
    for archive in video_series:
        # if time_title in archive['title']:
        if clip_title == archive['title']:
            bvid = archive['bvid']
            logger.debug(f"Clip {clip['clip_id']} matched {bvid}")
            clip.update({
                "bvid": bvid
            })
            return clip
    else:
        logger.warning(f"No paired for clip {clip['clip_id']} -> {clip_title}")

def generate_title(title:str, t):
    '生成官方录播风格的标题'
    if type(t) is str:
        format_t = t
    elif type(t) is datetime.datetime:
        tz = datetime.datetime.now().tzinfo
        local_t = datetime.datetime.fromtimestamp(t.timestamp(), tz=tz)
        format_t = local_t.strftime(r"%Y年%m月%d日%H点场")
    else:
        logger.error(f"Invalid time format {type(t)}")
        return
    return f"【直播回放】{title} {format_t}"

async def subtitle_parse(**kwargs):
    '解析字幕'
    # 展开参数
    subtitle_list = kwargs['subtitle_list']
    clip_id = kwargs['clip_id']
    name = kwargs['name']
    uid = kwargs['uid']

    # 获取开播时间
    start_time_ms = (await get_clip_id(clip_id))['data']['start_time']
    start_time = timestamp_to_date(start_time_ms, ms=True)

    # 构建翻译man弹幕
    res_list = []
    for subtitle in subtitle_list:
        # {
        #     "from": 339.719,
        #     "to": 340.839,
        #     "sid": 4,
        #     "location": 2,
        #     "content": "奇怪了",
        #     "music": 0.0
        # }
        time = relative_ts_to_time(subtitle['from'], start_time)
        content = subtitle['content']
        if subtitle['music'] > 0.2:
            text = f"♪: 【{content}】"
        else:
            text = f"主播: 【{content}】"
        info = {
            "clip_id": clip_id,
            "time": time,
            "username": name,
            "user_id": uid,
            "medal_name": None,
            "medal_level": None,
            "guard_level": None,
            "text": text,
            "superchat_price": None,
            "gift_name": None,
            "gift_price": 0,
            "gift_num": 0,
            "is_misc": True
        }
        res_list.append(Subtitles(**info))

    return res_list

async def add_subtitles(**subtitle_config):
    '给单个clip添加字幕'
    # 从config读取
    clip = subtitle_config.get('clip', None)
    clip_id = subtitle_config.get('clip_id', clip['clip_id'])
    bvid = subtitle_config.get('bvid', None)
    video_series = subtitle_config.get('video_series', None)

    # 如果只指定了id而没有指定clip
    if not clip:
        clip = await ClipInfo.get(clip_id=clip_id).values(
            'start_time', 'title', 'clip_id'
        )

    # 与官方录播配对
    if bvid:
        paired_clip = clip.copy()
        paired_clip.update({'bvid': bvid})
    else:
        paired_clip = await pair_clip(clip=clip, video_series=video_series)
        if not paired_clip:
            return

    # 获取视频信息和对应字幕
    c = await get_credential()
    v = Video(bvid=paired_clip['bvid'], credential=c)
    try:
        video_info = await get_video_info(v)
    except Exception as e:
        logger.error(f"Get subtitle error: {traceback.format_exc()}")
        return
    subtitle_list = await subtitle_parse(clip_id=clip_id, **video_info)

    # 上传字幕
    await Subtitles.bulk_create(subtitle_list)
    logger.info(f"Added subtitle for clip {clip_id}")

async def add_subtitles_all(forced=False):
    '添加字幕'
    # 读取配置
    subtitle_config_list = config.subtitle.get('config', [])
    for subtitle_config in subtitle_config_list:
        uid = subtitle_config['uid']
        sid = subtitle_config['sid']
        max_videos = subtitle_config['max_videos']

        # 获取最近的clip列表
        clip_list = await ClipInfo.filter(
            bilibili_uid=uid
        ).all().order_by("-start_time").limit(max_videos).values(
            'start_time', 'title', 'clip_id'
        )

        # 先去除已经有了字幕的片段
        if forced:
            new_clip_list = clip_list
        else:
            new_clip_list = []
            for clip in clip_list:
                try:
                    await Subtitles.get(clip_id=clip['clip_id'])
                except MultipleObjectsReturned:
                    is_exist = True
                except DoesNotExist:
                    is_exist = False
                else:
                    is_exist = True
                if not is_exist:
                    logger.debug(f"Adding clip {clip['clip_id']}..")
                    new_clip_list.append(clip)
        if not new_clip_list:
            logger.debug(f"All of {max_videos} clips have substitles.")
            return

        # 获取最近的官方录播合集
        video_series = await get_video_series(uid=uid, sid=sid, pn=1, ps=max_videos)

        # 开始添加
        for clip in new_clip_list:
            logger.debug(f"Searching for clip {clip['clip_id']} in {len(video_series)} videos")
            await add_subtitles(clip=clip, video_series=video_series)
