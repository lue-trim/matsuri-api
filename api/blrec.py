'blrec相关API'
import json, datetime, functools, uuid, requests
from ..models import *
from ..static import config
from ..parse import get_danmakus_info, get_room_info

def __count_danmakus(clip_list:list):
    '计算弹幕总数'
    return functools.reduce(lambda x,y:x+y.total_danmu, clip_list, initial=0)

def __get_uuid(room_id:int, start_time:datetime.datetime):
    '通过房间号和开播时间计算uuid'
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{room_id}{start_time}"))

async def update_user(data, is_live, recalculate=False, new_danmakus=0):
    '更新主鳖信息'
    # 获取场次信息
    uid = data['data']['room_info']['uid']
    clip_count = await ClipInfo.filter(uid=uid).all().count()
    last_clip = await ClipInfo.filter(uid=uid).all().order_by('-start_time').first()
    if last_clip:
        last_danmu = last_clip.total_danmu
        total_clip = clip_count
        if recalculate:
            clip_list = await ClipInfo.filter(uid=uid).all()
            total_danmu = __count_danmakus(clip_list)
        else:
            total_danmu = last_clip.total_danmu + new_danmakus
    else:
        last_danmu = 0
        total_clip = 0
        total_danmu = 0

    # 提取频道信息
    room_id = data['data']['room_info']['room_id']
    channel_info = {
        'name': data['data']['user_info']['name'],
        'bilibili_uid': uid,
        'bilibili_live_room': room_id,
        'is_live': is_live,
        'last_danmu': last_danmu,
        'total_clips': total_clip,
        'total_danmu': total_danmu,
        'face': data['data']['user_info']['face'],
        'last_live': last_clip.start_time if last_clip else None
    }

    # 更新或者创建
    channel = await Channels.get_or_none(bilibili_live_room = room_id)
    if channel:
        channel.update_from_dict(channel_info)
    else:
        Channels.create(**channel_info)

async def start_clip(data):
    '开始录制'
    await update_user(data=data, is_live=True)

async def end_clip(data):
    '结束录制'
    await update_user(data=data, is_live=False)

async def update_clip(data):
    '完成弹幕文件时更新录制信息'
    # 反查直播间信息
    room_id = data['data']['room_id']
    room_info = await get_room_info(room_id)
    uid = room_info['user_info']['uid']
    username = room_info['user_info']['name']
    title = room_info['room_info']['title']
    cover = room_info['room_info']['cover']

    # 解析弹幕文件
    danmakus_info = get_danmakus_info(data)
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

    # 更新弹幕信息
    danmakus_list = danmakus_info['danmakus']
    Comments.bulk_create(danmakus_list)
    # AllComments.bulk_create(danmakus_list)

    # 生成uuid
    clip_id = __get_uuid(room_id, live_start_time)

    # 更新场次信息
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
        total_danmu = total_danmu + last_clip.total_danmu
        total_minutes = (end_time - live_start_time).total_seconds()/60
        clip_info.update({
            'danmu_density': total_danmu / total_minutes,
            'total_danmu': total_danmu + last_clip.total_danmu,
            'total_gift': total_gift + last_clip.total_gift,
            'total_superchat': total_superchat + last_clip.total_superchat,
            'total_reward':  total_reward + last_clip.total_reward,
            'highlights': highlights + last_clip.highlights,
            'viewers': viewers + last_clip.viewers,
        })
        await last_clip.update_from_dict(clip_info)
    else:
        # 新建分段
        clip_info.update({
            'clip_id': clip_id,
            'bilibili_uid': uid,
            'danmu_density': danmu_density,
            'total_danmu': total_danmu,
            'total_gift': total_gift,
            'total_superchat': total_superchat,
            'total_reward':  total_reward,
            'highlights': highlights,
            'viewers': viewers,
        })
        ClipInfo.create(**clip_info)
