import datetime, json, os, re, requests, uuid
import xml.etree.ElementTree as ET
from loguru import logger
from db.models import ClipInfo, Comments
from static import config

def float_to_decimal(num:float, decimal=2):
    '浮点数保留小数'
    p = 10 ** decimal
    return int(num * p) / p

def relative_ts_to_time(ts, start_time:datetime.datetime):
    '相对时间戳转绝对时间'
    relative_ts = float(ts)
    delta_time = datetime.timedelta(seconds=relative_ts)
    final_time = start_time + delta_time
    return final_time

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
    if not t:
        return None
    return int(t.timestamp() * 1000)

def get_uuid(room_id:int, start_time:datetime.datetime):
    '通过房间号和开播时间计算uuid'
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{room_id}{start_time}"))

async def get_room_info(room_id):
    '从blrec获取房间信息'
    host = config.app['blrec_url']
    url = f"{host}/api/v1/tasks/{room_id}/data"
    res = requests.get(url)
    try:
        return res.json()
    except Exception as e:
        logger.error(f"Cannot connect to blrec:{e.with_traceback()}")

def xml_get(patt, s):
    '用于xml字段的正则表达式匹配'
    pattern = re.compile(f"(?<=\<{patt}\>).*(?=\<\/{patt}\>)")
    res = re.search(pattern, s)
    if res:
        return res.group()
    else:
        logger.error(f"no result for {patt} in {s}")
        return None

def xmlonly_parse(file_content:str, clip_id:str, record_start_time:datetime.datetime):
    '只有xml文件时用这个解析'
    summary = {
        "danmakus": [],
        "all_danmakus": [],
        "plain_danmakus": [], # 供分析高能词用
        "total_danmakus": 0,
        "total_superchat": 0,
        "total_reward":  0,
        "total_gift": 0,
        "viewers": 0,
        "last_danmaku": None,
    }

    # 开始解析
    if type(file_content) is list:
        file_content = "\n".join(file_content)
    root = ET.fromstring(file_content)
    info = {}

    # 普通弹幕
    for d in root.findall('d'):
        # 时间
        p = d.get('p')
        relative_ts = p[:p.find(',')] # 取出p属性的第一个元素
        final_time = relative_ts_to_time(relative_ts, record_start_time)
        info = {
            "clip_id": clip_id,
            "time": final_time,
            "username": d.get('user'),
            "user_id": int(d.get('uid')),
            "medal_name": None, # 无法从xml里获取
            "medal_level": None,
            "guard_level": None,
            "text": d.text,
            "superchat_price": None,
            "gift_name": None,
            "gift_price": 0,
            "gift_num": 0,
            "is_misc": False
        }
        summary["danmakus"].append(Comments(**info))
        summary["plain_danmakus"].append(info)

    # 礼物
    for gift in root.findall('gift'):
        info = {
            "clip_id": clip_id,
            "time": relative_ts_to_time(gift.get('ts'), record_start_time),
            "username": gift.get('user'),
            "user_id": int(gift.get('uid')),
            "medal_name": None,
            "medal_level": None,
            "guard_level": None,
            "text": None,
            "gift_price": int(gift.get('price')) / 1000,
            "gift_num": int(gift.get('giftcount')),
            "gift_name": gift.get('giftname')
        }
        total_price = info['gift_price'] * info['gift_num']
        summary["danmakus"].append(Comments(**info))
        summary['total_gift'] += total_price
        summary['total_reward'] += total_price

    # SC
    for sc in root.findall('sc'):
        info = {
            "clip_id": clip_id,
            "time": relative_ts_to_time(sc.get('ts'), record_start_time),
            "username": sc.get('user'),
            "user_id": int(sc.get('uid')),
            "medal_name": None,
            "medal_level": None,
            "guard_level": None,
            "text": sc.text,
            "superchat_price": int(sc.get('price')) / 1000,
        }
        total_price = info['superchat_price']
        summary["danmakus"].append(Comments(**info))
        summary['total_reward'] += total_price
        summary['total_superchat'] += total_price

    # 大航海
    for toast in root.findall('toast'):
        info = {
            "clip_id": clip_id,
            "time": relative_ts_to_time(toast.get('ts'), record_start_time),
            "username": toast.get('user'),
            "user_id": int(toast.get('uid')),
            "text": None,
            "gift_price": int(toast.get('price')) / 1000,
            "gift_num": int(toast.get('count')),
            "gift_name": toast.get('role')
        }
        total_price = info['gift_num'] * info['gift_price']
        summary["danmakus"].append(Comments(**info))
        summary['total_gift'] += total_price
        summary['total_reward'] += total_price

    # 最后
    summary['total_gift'] = int(summary['total_gift']*10) / 10
    summary['total_reward'] = int(summary['total_reward']*10) / 10
    summary['total_danmakus'] = len(summary['danmakus'])
    summary['last_danmaku'] = info
    return summary

def jsonl_parse(file_content, clip_id):
    summary = {
        "danmakus": [],
        "all_danmakus": [],
        "plain_danmakus": [], # 供分析高能词用
        "total_danmakus": 0,
        "total_superchat": 0,
        "total_reward":  0,
        "total_gift": 0,
        "viewers": 0,
        "last_danmaku": None,
    }

    info = {}
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
                medal_name = medal_level = guard_level = None
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['info'][0][4]),
                "username": js['info'][2][1],
                "user_id": js['info'][2][0],
                "medal_name": medal_name,
                "medal_level": medal_level,
                "guard_level": guard_level,
                "text": js['info'][1],
                "superchat_price": None,
                "gift_name": None,
                "gift_price": 0,
                "gift_num": 0,
                "is_misc": False
            } # 有superchat_price和gift_name中的任何一项, 都会被视为礼物弹幕
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
                "gift_price": js['data']['total_coin'] / 1000,
                "gift_num": 1, # 已经按实际收入算了就不要js['data']['num']了
                "gift_name": js['data']['giftName']
            }
            total_price = info['gift_price'] # total_coin是实际收入，跟数量无关
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
                "superchat_price": js['data']['price'],
            }
            total_price = info['superchat_price']
            summary["danmakus"].append(Comments(**info))
            summary['total_reward'] += total_price
            summary['total_superchat'] += total_price
        elif cmd == "USER_TOAST_MSG":
            # 大航海
            info = {
                "clip_id": clip_id,
                "time": timestamp_to_date(js['data']['start_time'], ms=False),
                "username": js['data']['username'],
                "user_id": js['data']['uid'],
                "text": None,
                "gift_price": js['data']['price'] * js['data']['num'] / 1000,
                "gift_num": 1,
                "gift_name": js['data']['role_name']
            }
            total_price = info['gift_num'] * info['gift_price']
            summary["danmakus"].append(Comments(**info))
            summary['total_gift'] += total_price
            summary['total_reward'] += total_price
    # 最后
    summary['total_gift'] = int(summary['total_gift']*10) / 10
    summary['total_reward'] = int(summary['total_reward']*10) / 10
    summary['total_danmakus'] = len(summary['danmakus'])
    summary['last_danmaku'] = info
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
    '从弹幕列表中提取高能关键词(暂时只支持"草""？""哈哈"和应援词)'
    if not plain_danmakus_list:
        return []
    # 排个序
    plain_danmakus_list.sort(key=lambda x:x['time'])

    # 预定义关键词
    keywords = ["草", "？", "哈", "好好好", "牛蛙", "wase", "call"]

    # 确定如何对时间进行分段
    start_ts = date_to_mili_timestamp(plain_danmakus_list[0]['time'])
    summary_list = []

    # 将弹幕文字内容进行分段
    # seg_num = len(summary_list)
    danmakus_seg_list = []
    seg_idx = 0
    while plain_danmakus_list:
        seg_start_ts = start_ts + 60000*seg_idx
        end_ts = 60000 + seg_start_ts
        # logger.debug(f"current: {seg_start_ts}, end: {end_ts}")
        danmakus_seg = ""
        current_ts = date_to_mili_timestamp(plain_danmakus_list[0]['time'])
        while current_ts < end_ts and len(plain_danmakus_list) > 0:
            current_danmaku = plain_danmakus_list.pop(0)
            danmakus_seg += current_danmaku['text']
            current_ts = date_to_mili_timestamp(current_danmaku['time'])

        # 发现超过了60秒后
        danmakus_seg_list.append(danmakus_seg)
        summary_list.append(dict([(key, 0) for key in keywords] + [('time', seg_start_ts)]))
        seg_idx += 1

    # 识别关键词个数
    for idx, danmakus_seg in enumerate(danmakus_seg_list):
        for key in keywords:
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
    clip_id = xml_summary['clip_id']
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            file_content = f.readlines()
        summary = jsonl_parse(file_content=file_content, clip_id=clip_id)
    else:
        summary = xmlonly_parse(file_content=file_content, clip_id=clip_id, record_start_time=xml_summary['record_start_time'])

    # 计算时间和弹幕频率（条/分钟）
    start_time:datetime.datetime = xml_summary['record_start_time']
    if summary['last_danmaku'] != {}:
        end_time = summary['last_danmaku']['time']
    clip_time = end_time - start_time
    danmu_density = summary['total_danmakus'] / (clip_time.total_seconds()/60)
    danmu_density = int(danmu_density*100) / 100

    # 识别高能词
    highlights = highlight_parse(summary['plain_danmakus'])

    # 最终结果
    res = {
        **summary,
        **xml_summary,
        'end_time': end_time,
        'danmu_density': danmu_density,
        'highlights': highlights
    }
    return res
