import os, sys, requests, getopt, datetime, uuid

from api import parse
from static import config

def request_api(record_end_time:datetime.datetime, room_id, xml_path):
    '构建请求并向服务端发送'
    # 构建请求
    data_id = str(uuid.uuid4())
    data_date = record_end_time.strftime(r"%Y-%m-%d %H:%M:%S.%f%z")
    data = {
        "id": data_id,
        "date": data_date,
        "type": "DanmakuFileCompletedEvent",
        "data": {
            "room_id": room_id,
            "path": xml_path
        }
    }
    # 发送请求
    host = config.app['host']
    port = config.app['port']
    #prefix = "https" if config.app['https'] else "http"
    prefix = "http"
    url = f"{prefix}://{host}:{port}/rec"
    requests.post(url, data=data)

def find_danmaku_file(path):
    '寻找blrec弹幕文件'
    file_list = os.listdir(path)
    res_list = []
    for i in file_list:
        filename, ext = os.path.splitext(os.path.join(path,i))
        if ext == ".xml":
            if os.path.exists(f"{filename}.jsonl"):
                res_list.append(f"{filename}.xml")
    return res_list

def usage():
    '--help'
    print("""检查并更新cookies
-l / --login\t扫码登录
-c / --cookies\t检查cookies, 并决定是否刷新
-s / --sync\t将cookies同步到blrec
-f / --forced\t不管cookies有没有过期都强制刷新(optional)""")
    quit()

def main():
    'main'
    config_path = "config.toml"
    search_path = ""
    config.load(config_path)

    # 解析参数
    options, args = getopt.getopt(sys.argv[1:], "hc:p:", ["help", "config=", "path="])
    for name, value in options:
        if name in ("-h","--help"):
            usage()
            quit()
        elif name in ("-c", "--config"):
            config_path = value
        elif name in ("-p", "--path"):
            search_path = value

    # 确定需要解析的文件
    parse_list = find_danmaku_file(search_path)

    # 读取文件信息
    for xml_path in parse_list:
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_info = parse.xml_parse(f.read(2000))
        room_id = xml_info['room_id']
        # start_time = xml_info['live_start_time']
        end_time = datetime.datetime.fromtimestamp(os.path.getmtime(xml_path))
        title = xml_info['title']
        print(f"Room ID: {room_id}, End Time: {end_time.strftime(r'%Y-%m-%d %H:%M:%S')}, Title: {title}")
        request_api( record_end_time=end_time, xml_path=xml_path, room_id=room_id)

if __name__ == "__main__":
    main()
