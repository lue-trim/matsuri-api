import os, argparse, datetime, uuid, json
from loguru import logger
from aiohttp import ClientSession, ClientTimeout
import asyncio

from api import parse
from static import config

async def send_matsuri(data="", params="", api_path="/"):
    '向服务端发送'
    headers = {
            'Content-Type': 'application/json'
    }
    host = config.app['host']
    port = config.app['port']
    #prefix = "https" if config.app['https'] else "http"
    prefix = "http"
    url = f"{prefix}://{host}:{port}{api_path}"

    # 发起请求
    async with ClientSession(timeout=ClientTimeout(None)) as session:
        async with session.post(url=url, data=data, params=params, headers=headers) as req:
            res = await req.json()
            # res = requests.post(url, data=json.dumps(data), params=json.dumps(params))
            if not req.ok:
                print(f"Server Error: {res}")
            else:
                print(f"Success - {url}")

    return res

def update_subtitle(is_all=True, bvid="", clip_id=""):
    '更新语音识别字幕'
    if is_all:
        asyncio.run(send_matsuri(api_path="/subtitle/update/all"))
    else:
        params = {
            'bvid': bvid,
            'clip_id': clip_id
        }
        asyncio.run(send_matsuri(params=params, api_path="/subtitle/update"))

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
                msg = f"解析失败, 正在跳过: {xml_path}"
                print(msg)
                logger.warning(msg)
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
        asyncio.run(send_matsuri(data=json.dumps(data), api_path="/rec"))

def update_channel(room_id):
    '更新直播间信息'
    msg = f"Updating channel {room_id}.."
    print(msg)
    logger.info(msg)

    # 先向blrec问个信息
    host = config.app['blrec_url']
    url = f"{host}/api/v1/tasks/{room_id}/data"
    params = {"room_id": int(room_id)}
    res = requests.get(url, params=params)
    if res:
        blrec_data = res.json()
    else:
        print("更新失败")
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
    asyncio.run(send_matsuri(data=data, api_path="/rec"))

def update_clip(clip_id):
    '更新场次信息'
    logger.info(f"Updating clip {clip_id}..")
    asyncio.run(send_matsuri(api_path=f"/refresh/clip/{clip_id}"))

def delete_clip(clip_id):
    '删除场次和弹幕'
    logger.info(f"Deleting clip {clip_id}..")
    asyncio.run(send_matsuri(api_path=f"/delete/clip/{clip_id}"))

def usage():
    '--help'
    print("""
给matsuri-api手动发送更新指令

Usage: python manual_update.py <options> [<param>]

Options: 
-h / --help:\t显示这条帮助并退出
-c / --config:\t指定配置文件
-d / --delete <clip_id>:\t删除指定场次和弹幕
\tclip_id:\t场次的uuid(可通过弹幕站的具体场次url获取)
-r / --refresh <clip_id>:\t刷新指定场次的弹幕和礼物统计信息(不包含封面)
\tclip_id:\t场次的uuid(可通过弹幕站的具体场次url获取)
-u / --upload <path>:\t上传弹幕并更新场次信息
\tpath:\t包含场次和弹幕信息的jsonl文件所在文件夹(子文件夹也会被识别)
-a / --channel <room_id>:\t更新直播间信息
\troom_id:\t直播间号(不支持短号)
-s / --subtitle <room_id>:\t更新直播间信息
\troom_id:\t直播间号(不支持短号)
""")
    quit()

def __add(args):
    '添加'
    if args.danmaku:
        update_danmakus(args.danmaku)
    if args.subtitle:
        update_subtitle(is_all=args.all, bvid=args.bvid, clip_id=args.clip)

def __refresh(args):
    '刷新'
    if args.room:
        update_channel(args.room)
    if args.clip:
        update_clip(args.clip)

def __del(args):
    '删除'
    if args.clip:
        delete_clip(args.clip)

def main():
    'main'
    config_path = "config.toml"
    config.load(config_path)

    # 解析参数
    p = argparse.ArgumentParser()
    # p.add_argument("subcommand", help="子命令", choices=['add', 'del', 'refresh'], required=True)
    sp = p.add_subparsers(title="subcommand")

    p_add = sp.add_parser("add", help="上传")
    p_add.add_argument("-d", "--danmaku", help="弹幕文件所在文件夹", default="")
    p_add.add_argument("-s", "--subtitle", help="上传字幕", action="store_true")
    p_add.add_argument("--all", help="(subtitle)模拟周期性自动识别并上传字幕", action="store_true")
    p_add.add_argument("--clip", help="(subtitle)要上传到的录播站场次id", default="")
    p_add.add_argument("--bvid", help="(subtitle)官方录播的BV号('BV'不能省略)", default="")
    p_add.set_defaults(func=__add)

    p_del = sp.add_parser("del", help="删除")
    p_del.add_argument("--clip", help="弹幕对应的录播站场次ID", required=True)
    p_del.set_defaults(func=__del)

    p_ref = sp.add_parser("refresh", help="刷新")
    p_ref.add_argument("--clip", help="场次id")
    p_ref.add_argument("--room", help="直播间id", default=0, type=int)
    p_ref.set_defaults(func=__refresh)

    p.add_argument("-c", "--config", help="指定配置文件", default="")

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
