import os, sys, requests, getopt, datetime, uuid, json
from loguru import logger

from api import parse
from static import config

def send_matsuri(data="", params="", api_path="/"):
    '向服务端发送'
    host = config.app['host']
    port = config.app['port']
    #prefix = "https" if config.app['https'] else "http"
    prefix = "http"
    url = f"{prefix}://{host}:{port}{api_path}"
    res = requests.post(url, data=json.dumps(data), params=json.dumps(params))
    if res:
        return res.json()
    else:
        logger.error(f"Server Error: {res}")

def find_danmaku_file(path):
    '寻找blrec弹幕文件'
    file_list = os.listdir(path)
    res_list = []
    for i in file_list:
        abs_path = os.path.join(path,i)
        if os.path.isdir(abs_path):
            # 递归查找
            res_list.extend(find_danmaku_file(abs_path))
        else:
            # 寻找弹幕文件
            filename, ext = os.path.splitext(abs_path)
            if ext == ".xml":
                # if os.path.exists(f"{filename}.jsonl"):
                #     res_list.append(f"{filename}.xml")
                res_list.append(abs_path)
                logger.info(f"Found {abs_path}")
    res_list.sort()
    return res_list

def update_danmakus(search_path):
    '更新弹幕和直播场次信息'
    logger.info("Updating danmakus and clips..")
    parse_list = find_danmaku_file(search_path)

    # 读取文件信息
    for xml_path in parse_list:
        with open(xml_path, 'r', encoding='utf-8') as f:
            try:
                xml_info = parse.xml_parse(f.read(2000))
            except TypeError:
                logger.warning(f"解析失败, 正在跳过: {xml_path}")
        room_id = xml_info['room_id']
        # start_time = xml_info['live_start_time']
        end_time = datetime.datetime.fromtimestamp(os.path.getmtime(xml_path))
        title = xml_info['title']
        logger.info(f"Room ID: {room_id}, End Time: {end_time.strftime(r'%Y-%m-%d %H:%M:%S')}, Title: {title}")

        # 构建请求
        jsonl_path=xml_path[:-3]+"jsonl"
        data_id = str(uuid.uuid4())
        data_date = end_time.strftime(r"%Y-%m-%d %H:%M:%S.%f+08:00")
        data = {
            "id": data_id,
            "date": data_date,
            "type": "RawDanmakuFileCompletedEvent",
            "data": {
                "room_id": room_id,
                "path": jsonl_path
            }
        }
        # 发送请求
        send_matsuri(data=data, api_path="/rec")

def update_channel(room_id):
    '更新直播间信息'
    logger.info(f"Updating channel {room_id}..")

    # 先向blrec问个信息
    host = config.app['blrec_url']
    url = f"{host}/api/v1/tasks/{room_id}/data"
    params = {"room_id": int(room_id)}
    res = requests.get(url, params=params)
    if res:
        blrec_data = res.json()
    else:
        logger.error(f"Blrec returned an error: {res}")
        return

    # 确定在不在啵
    is_live = not blrec_data['task_status']['running_status'] == "waiting"
    data_id = str(uuid.uuid4())
    data_date = datetime.datetime.now().strftime(r"%Y-%m-%d %H:%M:%S.%f+08:00")
    data = {
        "id": data_id,
        "date": data_date,
        "type": "LiveBeganEvent" if is_live else "LiveEndedEvent",
        "data": blrec_data
        }

    # 发送
    send_matsuri(data=data, api_path="/rec")

def update_clip(clip_id):
    '更新场次信息'
    logger.info(f"Updating clip {clip_id}..")
    send_matsuri(api_path=f"/refresh/clip/{clip_id}")

def delete_clip(clip_id):
    '删除场次和弹幕'
    logger.info(f"Deleting clip {clip_id}..")
    send_matsuri(api_path=f"/delete/clip/{clip_id}")

def usage():
    '--help'
    print("""
给matsuri-api手动发送更新指令
Usage: python manual_update.py <options> [<param>]
-h / --help:\t显示这条帮助并退出
-c / --config:\t指定配置文件
-d / --delete <clip_id>:\t删除指定场次和弹幕
\tclip_id:\t场次的uuid(可通过弹幕站的具体场次url获取)
-r / --refresh <clip_id>:\t刷新指定场次的弹幕和礼物统计信息(不包含封面)
\tclip_id:\t场次的uuid(可通过弹幕站的具体场次url获取)
-u / --upload <path>:\t上传弹幕并更新场次信息
\tpath:\t包含场次和弹幕信息的jsonl文件所在文件夹(子文件夹也会被识别)
-a / --channel <room_id>:\t更新直播间信息
\troom_id:\t要自动识别的jsonl所在文件夹
""")
    quit()

def main():
    'main'
    config_path = "config.toml"
    search_path = ""
    room_id = ""
    del_clip_id = ""
    ref_clip_id = ""
    config.load(config_path)

    # 解析参数
    options, args = getopt.getopt(
        sys.argv[1:], 
        "hd:c:a:u:r:", 
        ["help", "upload=", "channel=", "config=", "delete=", "refresh="]
        )
    for name, value in options:
        if name in ("-h","--help"):
            usage()
            quit()
        elif name in ("-c", "--config"):
            config_path = value
        elif name in ("-u", "--upload"):
            search_path = value
        elif name in ("-a", "--channel"):
            room_id = value
        elif name in ("-d", "--delete"):
            del_clip_id = value
        elif name in ("-r", "--refresh"):
            ref_clip_id = value

    if search_path:
        update_danmakus(search_path)
    if room_id:
        update_channel(room_id)
    if del_clip_id:
        delete_clip(clip_id=del_clip_id)
    if ref_clip_id:
        update_clip(clip_id=ref_clip_id)

if __name__ == "__main__":
    main()
