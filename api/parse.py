import datetime, json, os, re, requests, uuid
from loguru import logger
from db.models import ClipInfo, Comments
from static import config

def date1_to_time(time_in_blrec:str):
    '2025-04-02 12:00:24.255628+08:00 -> datetime'
    return datetime.datetime.strptime(time_in_blrec, r"%Y-%m-%d %H:%M:%S.%f%z")

def date2_to_time(s):
    '2025-04-02T12:00:24+08:00 -> datetime'
    return datetime.datetime.strptime(s, r"%Y-%m-%dT%H:%M:%S%z")

def timestamp_to_date(timestamp, ms=True):
    '1743566521395(毫秒) -> 2025-04-02 12:02:01'
    return datetime.datetime.fromtimestamp(
        timestamp / 1000 if ms else timestamp, 
        tz=datetime.timezone(datetime.timedelta(seconds=28800))
        )

def date_to_mili_timestamp(t:datetime.datetime):
    '2025-04-02 12:02:01 -> 1743566521395(毫秒)'
    return int(t.timestamp() * 1000)

def get_uuid(room_id:int, start_time:datetime.datetime):
    '通过房间号和开播时间计算uuid'
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{room_id}{start_time}"))

async def get_room_info(room_id):
    '从blrec获取房间信息'
    host = config.blrec['host']
    port = config.blrec['port']
    url = f"http://{host}:{port}/api/v1/tasks/{room_id}/data"
    res = requests.get(url)
    return res.json()

def xml_get(patt, s):
    '用于xml字段的正则表达式匹配'
    pattern = re.compile(f"(?<=\<{patt}\>).*(?=\<\/{patt}\>)")
    res = re.search(pattern, s)
    if res:
        return res.group()
    else:
        logger.error(f"no result for {patt} in {s}")
        return None

def jsonl_parse(file_content, clip_id):
    summary = {
        "danmakus": [],
        "all_danmakus": [],
        "plain_danmakus": [], # 供分析高能词用
        "total_danmakus": 0,
        "total_superchat": 0,
        "total_reward":  0,
        "total_gift": 0,
        "viewers": 0
    }
    for line in file_content:
        try:
            js = json.loads(line)
        except Exception:
            raise Exception(f"Parse Error on {line}")
        cmd = js['cmd']
        if cmd == "WATCHED_CHANGE":
            # 已观看人数更新
            summary['viewers'] = js['data']['num']
        # elif cmd == "INTERACT_WORD":
        #     # 进入房间
        #     if not js['data']['fans_medal']:
        #         fans_medal = {'medal_name':None,'medal_level':None,'guard_level':None}
        #     else:
        #         fans_medal = js['data']['fans_medal']
        #     uname = js['data']['uname']
        #     info = {
        #         "clip_id": clip_id,
        #         "time": timestamp_to_date(js['data']['timestamp'], ms=False),
        #         "username": uname,
        #         "user_id": js['data']['uid'],
        #         "medal_name": fans_medal['medal_name'],
        #         "medal_level": fans_medal['medal_level'],
        #         "guard_level": fans_medal['guard_level'],
        #         "text": f"{uname}进入直播间",
        #         "is_misc": True
        #     }
        #     summary["danmakus"].append(Comments(**info))
        elif cmd == "DANMU_MSG":
            # 普通弹幕
            medal_guard_info = js['info'][3]
            if medal_guard_info:
                medal_name = medal_guard_info[1]
                medal_level = medal_guard_info[0]
                guard_level = medal_guard_info[10]
            else:
                medal_name =medal_level = guard_level = None
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['info'][0][4]),
                "username": js['info'][2][1],
                "user_id": js['info'][2][0],
                "medal_name": medal_name,
                "medal_level": medal_level,
                "guard_level": guard_level,
                "text": js['info'][1],
            }
            summary["danmakus"].append(Comments(**info))
            summary["plain_danmakus"].append(info)
        elif cmd == "SEND_GIFT":
            # 投喂礼物
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['data']['timestamp'], ms=False),
                "username": js['data']['uname'],
                "user_id": js['data']['uid'],
                "medal_name": js['data']['medal_info']['medal_name'],
                "medal_level": js['data']['medal_info']['medal_level'],
                "guard_level": js['data']['medal_info']['guard_level'],
                "text": None,
                "gift_price": js['data']['price'] / 1000,
                "gift_num": js['data']['num'],
                "gift_name": js['data']['giftName']
            }
            total_price = info['gift_num'] * info['gift_price']
            summary["danmakus"].append(Comments(**info))
            summary['total_gift'] += total_price
            summary['total_reward'] += total_price
        elif cmd == "SUPER_CHAT_MESSAGE":
            # SC
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['send_time']),
                "username": js['data']['user_info']['uname'],
                "user_id": js['data']['uid'],
                "medal_name": js['data']['medal_info']['medal_name'],
                "medal_level": js['data']['medal_info']['medal_level'],
                "guard_level": js['data']['medal_info']['guard_level'],
                "text": js['data']['message'],
                "superchat_price": js['data']['price'] / 1000,
            }
            total_price = info['superchat_price']
            summary["danmakus"].append(Comments(**info))
            summary['total_reward'] += total_price
            summary['total_superchat'] += total_price
        elif cmd == "GUARD_BUY":
            # 大航海
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['data']['start_time'], ms=False),
                "username": js['data']['username'],
                "user_id": js['data']['uid'],
                "text": None,
                "gift_price": js['data']['price'] / 1000,
                "gift_num": js['data']['num'],
                "gift_name": js['data']['gift_name']
            }
            total_price = info['gift_num'] * info['gift_price']
            summary["danmakus"].append(Comments(**info))
            summary['total_gift'] += total_price
            summary['total_reward'] += total_price
    # 最后
    summary['total_danmakus'] = len(summary['danmakus'])
    return summary

def xml_parse(file_content):
    '从xml文件中提取信息'
    file_content = str(file_content)
    # 开始时间
    record_start_time = xml_get("record_start_time", file_content)
    record_start_time = date2_to_time(record_start_time)
    live_start_time = xml_get("live_start_time", file_content)
    live_start_time = date2_to_time(live_start_time)

    # 直播间号
    room_id = xml_get("room_id", file_content)
    room_id = int(room_id)

    # Clip ID
    clip_id = get_uuid(room_id, live_start_time)

    # 主鳖的名字
    liver_name = xml_get("user_name", file_content)

    # 直播间标题
    title = xml_get("room_title", file_content)

    return {
        'clip_id': clip_id,
        'title': title,
        'room_id': room_id,
        'liver_name': liver_name,
        'record_start_time': record_start_time,
        'live_start_time': live_start_time
        }

def highlight_parse(plain_danmakus_list:list):
    '从弹幕列表中提取高能关键词(暂时只支持"草""?/？""哈哈"和应援词)'
    if not plain_danmakus_list:
        return []
    # 预定义关键词
    keywords = ["time", "草", "?", "？", "哈哈", "好好好", "牛蛙", "wase", "call", "/\\"]

    # 确定如何对时间进行分段
    start_ts = date_to_mili_timestamp(plain_danmakus_list[0]['time'])
    summary_list = []

    # 将弹幕文字内容进行分段
    seg_num = len(summary_list)
    danmakus_seg_list = []
    seg_idx = 0
    while plain_danmakus_list:
        seg_start_ts = start_ts + 60000*seg_idx
        end_ts = 60000 + seg_start_ts
        danmakus_seg = ""
        current_ts = date_to_mili_timestamp(plain_danmakus_list[0]['time'])
        while current_ts < end_ts:
            current_danmaku = plain_danmakus_list.pop(0)
            danmakus_seg += current_danmaku['text']
            current_ts = date_to_mili_timestamp(current_danmaku['time'])
            if not plain_danmakus_list:
                # 后面没弹幕了就退出
                break

        # 发现超过了60秒后
        danmakus_seg_list.append(danmakus_seg)
        summary_list.append(dict([(key, 0) for key in keywords[1:]] + [('time', seg_start_ts)]))
        seg_idx += 1

    # 识别关键词个数
    for idx, danmakus_seg in enumerate(danmakus_seg_list):
        for key in keywords[1:]:
            summary_list[idx][key] = danmakus_seg.count(key)
    return summary_list

def get_danmakus_info(data):
    '从原始弹幕文件结束的webhook信息和具体文件中提取信息'
    # webhook消息
    jsonl_path = data['data']['path']
    end_time = date1_to_time(data['date'])

    # xml
    xml_path = f"{os.path.splitext(jsonl_path)[0]}.xml"
    logger.debug(f"Reading {xml_path}")
    with open(xml_path, "r", encoding='utf-8') as f:
        file_content = f.readlines()
    xml_summary = xml_parse(file_content)

    # jsonl
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        file_content = f.readlines()
    clip_id = xml_summary['clip_id']
    summary = jsonl_parse(file_content=file_content, clip_id=clip_id)

    # 计算时间和弹幕频率（条/分钟）
    start_time:datetime.datetime = xml_summary['record_start_time']
    clip_time = end_time - start_time
    danmu_density = summary['total_danmakus'] / (clip_time.total_seconds()/60)

    # 识别高能词
    highlights = highlight_parse(summary['plain_danmakus'])

    # 最终结果
    return {
        **summary,
        **xml_summary,
        'end_time': end_time,
        'danmu_density': danmu_density,
        'highlights': highlights
    }
