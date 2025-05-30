'blrec相关API'
import functools
from loguru import logger
from db.models import ClipInfo, Channels, Comments
#from static import config
from .parse import get_danmakus_info, get_room_info, get_uuid, float_to_decimal

def __count_danmakus(clip_list:list):
    '计算弹幕总数'
    #return functools.reduce(lambda x,y:x+y['total_danmu'], clip_list, initial=0)
    return sum([i['total_danmu'] for i in clip_list])

async def update_user(data, is_live):
    '更新主鳖信息'
    # 获取场次信息
    uid = data['data']['room_info']['uid']
    user_clips = await ClipInfo.filter(bilibili_uid=uid).all().order_by('start_time').values(
        'total_danmu', 'start_time'
    )
    total_clip = len(user_clips)
    if total_clip > 0:
        last_clip = user_clips[-1]
        last_live = last_clip['start_time']
        last_danmu = last_clip['total_danmu']
        total_danmu = __count_danmakus(user_clips)
    else:
        last_live = None
        last_danmu = 0
        total_danmu = 0

    # 提取频道信息
    room_id = data['data']['room_info']['room_id']
    channel_info = {
        'is_live': is_live,
        'last_danmu': last_danmu,
        'total_clips': total_clip,
        'total_danmu': total_danmu,
        'last_live': last_live,
    }
    if not data['data'].get('user_info', None):
        # 如果是RecordingFinishedEvent就没有user_info这一项, 暂不更新
        channel_info.update({
            'name': data['data']['user_info']['name'],
            'face': data['data']['user_info']['face'],
        })

    # 更新或者创建
    channel = await Channels.get_or_none(bilibili_live_room = room_id)
    if channel:
        channel_info['hidden'] = channel.hidden
        await Channels.filter(bilibili_live_room = room_id).update(**channel_info)
    else:
        channel_info.update({
            'bilibili_uid': uid,
            'bilibili_live_room': room_id,
            'hidden': False,
            'archive': False,
        })
        await Channels.create(**channel_info)

async def start_clip(data):
    '开始录制'
    await update_user(data=data, is_live=True)

async def end_clip(data):
    '结束录制'
    await update_user(data=data, is_live=False)

async def update_clip(data):
    '完成弹幕文件时更新录制信息'
    filename = data['data']['path']
    # 反查直播间信息
    room_id = data['data']['room_id']
    room_info = await get_room_info(room_id)
    uid = room_info['user_info']['uid']
    username = room_info['user_info']['name']
    # title = room_info['room_info']['title'] # 不要现场获取，从xml读才是正确的
    cover = room_info['room_info']['cover'] # 但是封面信息是真读不到

    # 顺带更新一下直播信息
    is_live = room_info['task_status']['running_status'] != "waiting"
    await update_user(
        data={'data': room_info},
        is_live=is_live
        )

    # 解析弹幕文件
    danmakus_info = get_danmakus_info(data)
    title = danmakus_info['title']
    live_start_time = danmakus_info['live_start_time']
    # record_start_time = danmakus_info['record_start_time']
    end_time = danmakus_info['end_time']

    danmu_density = danmakus_info['danmu_density']
    total_danmu = danmakus_info['total_danmakus']
    total_gift = danmakus_info['total_gift']
    total_superchat = danmakus_info['total_superchat']
    total_reward = danmakus_info['total_reward']
    highlights = danmakus_info['highlights']
    viewers = danmakus_info['viewers']

    # 检查是不是这段已经上传过了
    d = danmakus_info['last_danmaku']
    is_duplicate = await Comments.get_or_none(**d) is not None
    if d == {}:
        # 弹幕为空
        logger.warning(f"No danmakus found in {filename}, skipping...")
        # return
    elif is_duplicate:
        # 最后一条弹幕已存在
        logger.debug(f"Duplicate: {d}")
        logger.warning(f"Duplicated danmakus detected in {filename}, skipping...")
        # return
    else:
        # 弹幕不为空且最后一条弹幕在弹幕库里不存在
        danmakus_list = danmakus_info['danmakus']
        await Comments.bulk_create(danmakus_list)
        # AllComments.bulk_create(danmakus_list)

    # 获取场次ID
    clip_id = danmakus_info['clip_id']

    # 更新场次信息
    logger.debug(f"Clip ID: {clip_id}")
    clip_info = {
        'name': username,
        'bilibili_uid': uid,
        'title': title,
        'start_time': live_start_time,
        'end_time': end_time,
        'cover': cover,
    }
    last_clip = await ClipInfo.get_or_none(clip_id=clip_id)
    if last_clip:
        # 自动合并进之前的分段
        last_clip = await ClipInfo.filter(clip_id=clip_id).order_by('start_time').first()
        total_danmu = total_danmu + last_clip.total_danmu
        total_minutes = (end_time - live_start_time).total_seconds()/60
        clip_info.update({
            'danmu_density': float_to_decimal(total_danmu/total_minutes, 3),
            'total_danmu': total_danmu,
            'total_gift': float_to_decimal(total_gift + last_clip.total_gift),
            'total_superchat': float_to_decimal(total_superchat + last_clip.total_superchat),
            'total_reward':  float_to_decimal(total_reward + last_clip.total_reward),
            'highlights': last_clip.highlights + highlights,
            'viewers': viewers,
        })
        await ClipInfo.filter(clip_id=clip_id).update(**clip_info)
        clip_info.pop('highlights')
        logger.debug(f"Updated: {clip_info}")
    else:
        # 新建分段
        clip_info.update({
            'clip_id': clip_id,
            'bilibili_uid': uid,
            'danmu_density': float_to_decimal(danmu_density, 3),
            'total_danmu': total_danmu,
            'total_gift': float_to_decimal(total_gift),
            'total_superchat': float_to_decimal(total_superchat),
            'total_reward':  float_to_decimal(total_reward),
            'highlights': highlights,
            'viewers': viewers,
        })
        await ClipInfo.create(**clip_info)
        clip_info.pop('highlights')
        logger.debug(f"Created: {clip_info}")

    # 输出一下
    start_t = live_start_time.strftime(r"%Y-%m-%d %H:%M:%S%z")
    end_t = end_time.strftime(r"%Y-%m-%d %H:%M:%S%z")
    logger.info(f"Update complete: ID={room_id} Start={start_t} End={end_t}")
