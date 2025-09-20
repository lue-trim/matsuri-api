'处理Matsuri API'
import datetime, math
from loguru import logger
from tortoise.exceptions import DoesNotExist
from functools import reduce

from db.models import ClipInfo, Comments, OffComments, Subtitles, Channels
#from ..static import config
from .parse import get_room_info, date_to_mili_timestamp, highlight_parse, float_to_decimal

### Clip
async def delete_clip(clip_id):
    '删除指定弹幕和场次'
    await ClipInfo.get(clip_id=clip_id).delete()
    await Comments.filter(clip_id=clip_id).all().delete()
    return {"code": 200}

async def refresh_clip(clip_id):
    '手动刷新场次信息'
    old_clip = await ClipInfo.get_or_none(clip_id=clip_id)
    if not old_clip:
        return None

    # 结束时间
    last_danmaku = await Comments.filter(clip_id=clip_id).order_by("-time").first()
    end_time = last_danmaku.time
    if end_time < old_clip.end_time:
        end_time = old_clip.end_time

    # 高能弹幕
    plain_danmakus = await Comments.filter(
        clip_id=clip_id, superchat_price=None, gift_name=None, 
        ).all().order_by("time").values(
            'time', 'text'
            )
    highlights = highlight_parse(plain_danmakus)

    # 开始时间
    first_danmaku = await Comments.filter(clip_id=clip_id).order_by("time").first()
    start_time = first_danmaku.time
    if start_time > old_clip.start_time:
        start_time = old_clip.start_time

    # 收入统计
    all_danmakus = await Comments.filter(clip_id=clip_id).all().values('gift_price', 'superchat_price')
    total_gift = 0
    total_superchat = 0
    for d in all_danmakus:
        gift_price = d['gift_price']
        sc_price = d['superchat_price']
        if gift_price:
            total_gift += gift_price
        elif sc_price:
            total_superchat += sc_price

    # 弹幕统计
    total_danmu = len(all_danmakus)
    total_mins = (end_time - old_clip.start_time).total_seconds() / 60
    danmu_density = total_danmu / total_mins

    # 综合
    clip_info = {
        'start_time': start_time,
        'end_time': end_time,
        'danmu_density': float_to_decimal(danmu_density, 3),
        'total_danmu': total_danmu,
        'total_gift': float_to_decimal(total_gift),
        'total_superchat': float_to_decimal(total_superchat),
        'total_reward': float_to_decimal(total_gift + total_superchat),
        'highlights': highlights,
    }
    await ClipInfo.filter(clip_id=clip_id).update(**clip_info)
    return {"code": 200}

async def get_clip_id(clip_id):
    '获取场次概览信息'
    clip_info = await ClipInfo.get_or_none(clip_id=clip_id)
    if not clip_info:
        return None
    # id, bilibili_uid, title, EXTRACT(EPOCH FROM start_time)*1000 AS start_time, 
    # EXTRACT(EPOCH FROM end_time)*1000 AS end_time, cover, danmu_density, 
    # total_danmu, total_gift, total_superchat, total_reward, highlights, 
    # viewers AS views
    data = {
        'name': clip_info.name,
        'id': clip_info.clip_id,
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

    # 处理没有收录highlights的情况
    if not data['highlights']:
        data.pop('highlights')

    return {
        'status': 0, 'data': data
    }

async def get_clip_id_comments(clip_id):
    '获取特定场次的所有弹幕'
    # EXTRACT(EPOCH FROM "time")*1000 as time, username, user_id, superchat_price, 
    # gift_name, gift_price, gift_num, "text" 
    # FROM all_comments WHERE clip_id = $1 ORDER BY "time"', [id])
    danmakus = await Comments.filter(clip_id=clip_id).all().values(
        'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
        'gift_num', "text"
    )
    subtitles = await Subtitles.filter(clip_id=clip_id).all().values(
        'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
        'gift_num', "text"
    )
    danmakus.extend(subtitles)
    # danmakus:list
    danmakus.sort(key=lambda x:x['time'])

    # 处理数据库返回的信息
    for idx, danmaku in enumerate(danmakus):
        # 把返回值可以null的部分去掉
        for nullable_key in ['superchat_price', 'gift_name']:
            if danmaku[nullable_key] is None:
                danmakus[idx].pop(nullable_key)
        # 把时间改成毫秒时间戳
        danmakus[idx].update({
            'time': date_to_mili_timestamp(danmaku['time'])
        })

    return {
        'status': 0, 'data': danmakus
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
    clips = await ClipInfo.filter(bilibili_uid=mid).all().order_by("-start_time")
    if not clips:
        return None
    data = [{
        'id': clip.clip_id, 
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
async def get_search_advanced(data:dict):
    '高级搜索'
    # 构建请求体
    args = {
        'text__contains': data['keyword']
    }

    # 提取参数
    is_get_danmaku = data['type'] in ('all', 'danmaku')
    is_get_subtitle = data['type'] in ('all', 'subtitle')
    if data['startTime']:
        start_time = datetime.datetime.fromisoformat(data['startTime'])
        args.update({'time__gt': start_time})
    if data['endTime']:
        end_time = datetime.datetime.fromisoformat(data['endTime'])
        args.update({'time__lt': end_time})
    page = data['page'] if data['page'] > 0 else 1 # 与google的验证机制配合，只有获取第0页时需要校验
    page_size = data['pageSize']

    # 查询总数
    total_items = 0
    if is_get_danmaku:
        total_items += await Comments.filter(**args).count()
    if is_get_subtitle:
        total_items += await Subtitles.filter(**args).count()
    total_pages = math.ceil(total_items/page_size)

    # 查询具体内容
    danmakus_list = []
    if is_get_danmaku:
        danmakus_list.extend(
            await Comments.filter(
                **args
            ).all().order_by('-time').offset(page_size*(page-1)).limit(page_size).values(
                'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
                'gift_num', 'text', 'clip_id'
            )
        ) # Page要-1，因为前端是从1开始算的
    if is_get_subtitle:
        danmakus_list.extend(
            await Subtitles.filter(
                **args
            ).all().order_by('-time').offset(page_size*(page-1)).limit(page_size).values(
                'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
                'gift_num', 'text', 'clip_id'
            )
        )

    return await (__get_final_list(
        danmakus_list, version=2, page=page, total_pages=total_pages
        ))

async def get_search_danmaku(danmaku:str, page:int):
    '弹幕全局搜索'
    danmakus_list = await Comments.filter(
        text__contains=danmaku
    ).all().order_by('-time').offset(30*(page-1)).limit(30).values(
        'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
        'gift_num', 'text', 'clip_id'
    )
    # Page要-1，因为前端是从1开始算的
    return await (__get_final_list(danmakus_list))

async def get_viewer_mid(mid:int, page:int):
    '获取指定用户的发言'
    # SELECT DISTINCT(clip_id),MAX(time) as time FROM comments 
    # WHERE user_id = $1 GROUP BY clip_id ORDER BY "time" DESC LIMIT 10 OFFSET $2
    # danmakus_info = await Comments.filter(user_id=mid).group_by('clip_id').order_by('time').only('clip_id').distinct().offset(10*page).limit(10).values('clip_id')
    # 太复杂了，直接取100条吧
    danmakus_info_list = await Comments.filter(
        user_id=mid
    ).all().order_by('-time').offset(50*(page-1)).limit(50).values(
        'time', 'username', 'user_id', 'superchat_price', 'gift_name', 'gift_price', 
        'gift_num', 'text', 'clip_id'
    )
    return (await __get_final_list(danmakus_info_list))

async def __get_final_list(danmakus_info_list, version=1, page=0, total_pages=0):
    '统一处理返回值'
    # 排序
    danmakus_info_list_sorted = sorted(danmakus_info_list, key=lambda x:-x['time'].timestamp())

    # 建立dict
    danmakus_dict = {}
    for item in danmakus_info_list_sorted:
        clip_id = item.get('clip_id', None)
        clip_item = danmakus_dict.get(clip_id, None)
        if clip_item:
            danmakus_dict[clip_id].append(item)
        else:
            danmakus_dict.setdefault(clip_id, [item])
    
    # 获取场次信息
    # logger.warning(f"{danmakus_dict}")
    final_list = []
    for clip_id in danmakus_dict.keys():
        # SELECT id, bilibili_uid, EXTRACT(EPOCH FROM start_time)*1000 AS start_time, 
        # title, cover, danmu_density, EXTRACT(EPOCH FROM end_time)*1000 AS end_time, 
        # total_danmu, total_gift, total_reward, total_superchat, viewers AS views 
        # FROM clip_info WHERE id = $1', [clip_id]
        clip_info = await ClipInfo.get_or_none(clip_id=clip_id).values(
            'name', 'clip_id', 'bilibili_uid', 'start_time', 'title', 'cover', 'danmu_density', 'end_time', 'total_danmu', 'total_gift', 'total_reward', 'total_superchat', 'viewers'
            )
        if not clip_info:
            logger.warning(f"No such clip_id: {clip_id}")
            continue

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
        full_comments = danmakus_dict[clip_id]
        if not full_comments:
            logger.warning(f"Clip ID {clip_id} not found.")
        for idx, c in enumerate(full_comments):
            full_comments[idx]['time'] = date_to_mili_timestamp(c['time'])
            # full_comments.append(c)

        # 最终返回值
        final_list.append({
            'clip_info': clip_info, 
            'full_comments': full_comments
        })

    # 返回值
    if version == 1:
        return {
            'status': 0, 'data': final_list
        }
    elif version == 2:
        return {
            'success': True,
            'message': '',
            'pagination': {
                'totalItems': reduce(lambda x,y:x+len(y['full_comments']), final_list, 0), 
                'totalPages': total_pages,
                'currentPage': page,
            },
            'data': final_list
        }
