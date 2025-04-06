'处理Matsuri API'
import json, datetime, functools, uuid, requests
from ..models import *
from ..static import config
from ..parse import date1_to_time, date_to_mili_timestamp


### Viewer


### Clip
async def get_clip_id(clip_id):
    '获取场次信息'
    clip_info = await ClipInfo.get_or_none(id=clip_id)
    if not clip_info:
        return None
    # id, bilibili_uid, title, EXTRACT(EPOCH FROM start_time)*1000 AS start_time, 
    # EXTRACT(EPOCH FROM end_time)*1000 AS end_time, cover, danmu_density, 
    # total_danmu, total_gift, total_superchat, total_reward, highlights, 
    # viewers AS views
    data = {
        'id': clip_info.id,
        'bilibili_uid': clip_info.bilibili_uid,
        'title': clip_info.title,
        'start_time': date_to_mili_timestamp(clip_info.start_time),
        'end_time': date_to_mili_timestamp(clip_info.end_time),
        'cover': clip_info.cover,
        'danmu_density': clip_info.danmu_density,
        'total_danmu': clip_info.total_danmu,
        'total_gift': clip_info.total_gift,
        'total_superchat': clip_info.total_superchat,
        'total_reward': clip_info.total_reward,
        'highlights': clip_info.highlights,
        'views': clip_info.viewers
    }
    return {
        'status': 0, 'data': data
    }

async def get_clip_id_comments(clip_id):
    '获取特定场次弹幕'
    # EXTRACT(EPOCH FROM "time")*1000 as time, username, user_id, superchat_price, 
    # gift_name, gift_price, gift_num, "text" 
    # FROM all_comments WHERE clip_id = $1 ORDER BY "time"', [id])
    danmakus = await Comments.filter(clip_id=clip_id, ordering="time")
    if not danmakus:
        return {
            'status': 0, 'data': []
        }
    data = [{
        'time': date_to_mili_timestamp(danmaku.time),
        'username': danmaku.username,
        'user_id': danmaku.user_id, 
        'superchat_price': danmaku.superchat_price, 
        'gift_name': danmaku.gift_name, 
        'gift_price': danmaku.gift_price, 
        'gift_num':danmaku.gift_num, 
        'text': danmaku.text,
    } for danmaku in danmakus]
    return {
        'status': 0, 'data': data
    }


### Channel
async def get_channel_list():
    '获取频道列表'
    # SELECT name, bilibili_uid, bilibili_live_room, is_live, last_danmu, 
    # total_clips, total_danmu, face, hidden, archive, 
    # EXTRACT(EPOCH FROM last_live)*1000 AS last_live from channels
    channel_list = await Channels.all()
    if not channel_list:
        return {
            'status': 0, 'data': []
        }
    data = [{
        'name': channel.name, 
        'bilibili_uid': channel.bilibili_uid,
        'bilibili_live_room': channel.bilibili_live_room, 
        'is_live': channel.is_live, 
        'last_danmu': channel.last_danmu, 
        'total_clips': channel.total_clips, 
        'total_danmu': channel.total_danmu, 
        'face': channel.face, 
        'hidden': channel.hidden, 
        'archive': channel.archive, 
        'last_live': date_to_mili_timestamp(channel.last_live),
    } for channel in channel_list]
    return {
        'status': 0, 'data': data
    }
