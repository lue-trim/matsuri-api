'处理Matsuri API'
import datetime
from tortoise.exceptions import DoesNotExist
from db.models import *
#from ..static import config
from .parse import get_room_info, date_to_mili_timestamp

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
    danmakus = await Comments.filter(clip_id=clip_id, ordering="time").all()
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
    channel_list = await Channels.all().values(
        'name', 'bilibili_uid', 'bilibili_live_room', 'is_live', 'last_danmu', 
        'total_clips', 'total_danmu', 'face', 'hidden', 'archive', 'last_live'
    )
    if not channel_list:
        return {
            'status': 0, 'data': []
        }
    for idx, item in enumerate(channel_list):
        channel_list[idx].update({
            'last_live': date_to_mili_timestamp(item['last_live'])
        })
    return {
        'status': 0, 'data': channel_list
    }

async def get_channel_id(mid:int):
    '获取指定频道信息'
    # 'SELECT name, bilibili_uid, bilibili_live_room, is_live, last_danmu, total_clips, 
    # total_danmu, face, hidden, EXTRACT(EPOCH FROM last_live)*1000 AS last_live 
    # from channels WHERE bilibili_uid= $1', [mid]
    try:
        channel_info = await Channels.get(bilibili_uid=mid).values(
            'name', 'bilibili_uid', 'bilibili_live_room', 'is_live', 'last_danmu', 
            'total_clips', 'total_danmu', 'face', 'hidden', 'last_live'
            )
    except DoesNotExist:
        return None
    channel_info.update({
        'last_live': date_to_mili_timestamp(channel_info['last_live'])
        })
    return {
        'status': 0, 'data': channel_info
    }

async def get_channel_id_clips(mid:int):
    '获取指定频道的所有场次'
    # SELECT id, bilibili_uid, title, EXTRACT(EPOCH FROM start_time)*1000 AS start_time, 
    # EXTRACT(EPOCH FROM end_time)*1000 AS end_time, cover, total_danmu, 
    # viewers AS views FROM clip_info WHERE bilibili_uid= $1 ORDER BY start_time DESC
    clips = await ClipInfo.filter(bilibili_uid=mid).all().order_by("start_time")
    if not clips:
        return None
    data = [{
        'id': clip.id, 
        'bilibili_uid': clip.bilibili_uid, 
        'title': clip.title,
        'start_time': date_to_mili_timestamp(clip.start_time),
        'end_time': date_to_mili_timestamp(clip.end_time), 
        'cover': clip.cover, 
        'total_danmu': clip.total_danmu,
        'views': clip.viewers
    } for clip in clips]
    return {
        'status': 0, 'data': data
    }


### Off Comments
async def get_mid_date(mid:int, date:str):
    '获取特定主播指定日期及其之后24小时内的下播弹幕'
    # SELECT EXTRACT(EPOCH FROM "time")*1000 as time, username, user_id, superchat_price, 
    # gift_name, gift_price, gift_num, "text" FROM off_comments WHERE liver_uid = $1 
    # AND ("time" BETWEEN to_timestamp($2) AND to_timestamp($3)) ORDER BY "time"',
    # [mid, format_date, format_date + 24 * 3600]
    t1 = datetime.datetime.strptime(date, r"%Y%m%d")
    t2 = t1 + datetime.timedelta(days=1)
    danmakus = await OffComments.filter(liver_uid=mid, time__gte=t1, time___lte=t2).all().order_by("time")
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


### Viewer
async def get_viewer_mid(mid:int, page:int):
    '获取指定用户的发言'
    # SELECT DISTINCT(clip_id),MAX(time) as time FROM comments 
    # WHERE user_id = $1 GROUP BY clip_id ORDER BY "time" DESC LIMIT 10 OFFSET $2
    # danmakus_info = await Comments.filter(user_id=mid).group_by('clip_id').order_by('time').only('clip_id').distinct().offset(10*page).limit(10).values('clip_id')
    # 太复杂了，直接取100条吧
    danmakus_info_list = await Comments.filter(
        no_enter_message=False, user_id=mid
        ).group_by('clip_id').order_by('time').offset(10*page).limit(10)
    danmakus_dict = {}
    for item in danmakus_info_list:
        clip_id = item.clip_id
        clip_item = danmakus_dict.get(clip_id, default=None)
        if clip_item:
            danmakus_dict['clip_id'].append(item)
        else:
            danmakus_dict.update({clip_id: []})
    
    # 获取场次信息
    final_list = []
    for clip_id in danmakus_dict.keys():
        # SELECT id, bilibili_uid, EXTRACT(EPOCH FROM start_time)*1000 AS start_time, 
        # title, cover, danmu_density, EXTRACT(EPOCH FROM end_time)*1000 AS end_time, 
        # total_danmu, total_gift, total_reward, total_superchat, viewers AS views 
        # FROM clip_info WHERE id = $1', [clip_id]
        clip_info = await ClipInfo.get(clip_id=clip_id).values(
            'name', 'clip_id', 'bilibili_uid', 'start_time', 'title', 'cover', 'danmu_density', 'end_time', 'total_danmu', 'total_gift', 'total_reward', 'total_superchat', 'viewers'
            )
        # SELECT name FROM channels WHERE bilibili_uid = $1
        clip_info.update({
            'id': clip_info['clip_id'],
            'start_time': date_to_mili_timestamp(clip_info['start_time']),
            'end_time': date_to_mili_timestamp(clip_info['end_time']),
            'views': clip_info['viewers'],
        })
        clip_info.pop('clip_id')
        clip_info.pop('viewers')
        # SELECT EXTRACT(EPOCH FROM "time")*1000 as time, username, user_id, 
        # superchat_price, gift_name, gift_price, gift_num, "text" FROM comments 
        # WHERE clip_id = $1 AND user_id = $2 ORDER BY "time"
        full_comments = [{
            'time': date_to_mili_timestamp(c.time), 
            'username': c.username, 
            'user_id': c.user_id, 
            'superchat_price': c.superchat_price, 
            'gift_name': c.gift_name, 
            'gift_price': c.gift_price, 
            'gift_num': c.gift_num, 
            'text': c.text
        } for c in danmakus_dict['clip_id']]
        final_list.append({
            'clip_info': clip_info, 
            'full_comments': full_comments
        })

    # 返回值
    return {
        'status': 0, 'data': final_list
    }
