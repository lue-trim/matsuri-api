import requests, functools, datetime
import urllib.parse
from models import *
from static import config

async def __request(text:str):
    '发送请求'
    matsuri_host = config.matsuri['host']
    matsuri_port = config.matsuri['port']
    matsuri_auth = config.matsuri['Authorization']

    url = f"http://{matsuri_host}:{matsuri_port}/db"
    data = {
        'text': text,
    }
    header = {
        'Authorization': matsuri_auth,
    }
    response = requests.post(url=url, data=data, headers=header)
    response_json = response.json()

    return response_json

async def request(text:str):
    res = await __request(text)
    return res['data'] 

### 构建指令
def __parse_data(item):
    '将不同类型的数据转化成postgres能识别的字符串'
    if type(item) is str:
        return f"'{urllib.parse.quote(item, encoding='utf-8')}'"
    elif type(item) is datetime.datetime:
        return f"to_timestamp({item.timestamp()})"
    elif item is None:
        return "null"
    else:
        return f"{item}"

def __comma_separate(items, parse=True):
    '[x,y,...] -> "x, y, z..."'
    if parse:
        items_list = [__parse_data(item) for item in items]
    else:
        items_list = items
    return ",".join(items_list)

def __comma_separate_tuple(data):
    '[[x1,y1,...], [x2,y2,...], ...] -> ["(x1,y1,...)", "(x2,y2,...)", ...]'
    res_list = []
    for row in data:
        res_list.append(f"({__comma_separate(row)})")
    return res_list

def __build_insert_into(data:list[dict]):
    '构建INSERT INTO命令'
    # 判断数据库类型
    model = data[0]
    if type(model) is AllComments:
        tablename = 'all_comments'
    elif type(model) is OffComments:
        tablename = 'off_comments'
    elif type(model) is Comments:
        tablename = 'comments'
    elif type(model) is Channels:
        tablename = 'channels'
    elif type(model) is ClipInfo:
        tablename = 'clip_info'
    else:
        raise TypeError("Unknown database type.")

    model = data[0]
    keys = model.model_dump(mode='python').keys()
    data_list = [[getattr(model, key) for key in keys] for model in data]

    # 表头
    s = f"INSERT INTO {tablename} ({__comma_separate(keys)}) VALUES "

    # 内容
    s += __comma_separate_tuple(data_list)
    # s += __comma_separate(content_list)
    s += ";"
    return s

def __build_update(model):
    '构建UPDATE命令'
    # 判断类型
    if type(model) is Channels:
        tablename = 'channels'
    elif type(model) is ClipInfo:
        tablename = 'clip_info'
    else:
        raise TypeError("Unknown database type.")
    keys = model.model_dump(mode='python').keys()
    data = [getattr(model, key) for key in keys]

    # 开头
    s = f"UPDATE {tablename} SET "

    # key = data, ...
    l = [f"{key} = {__parse_data(data[idx])}" for idx, key in enumerate(keys)]
    s += __comma_separate(l, False)

    # WHERE CONTIDION=...
    if tablename == 'channels':
        s += f"WHERE bilibili_uid = {__parse_data(model.bilibili_uid)}"
    elif tablename == 'clip_info':
        s += f"WHERE id = {__parse_data(model.id)}"

    s += ";"
    return s

### 外部可访问方法
async def insert(data:list):
    '插入指定数据库'
    # 检查数据可用性
    if not data : 
        raise ReferenceError("Empty data.")
    if type(data) is not list:
        raise TypeError("Data is not a list.")

    # 生成PostgreSQL指令
    command = __build_insert_into(data=data)
    response = await __request(command)
    return response

async def update(model):
    '更新直播场次信息'
    # 检查数据可用性
    if not model : 
        raise ReferenceError("Empty data.")

    # 生成PostgreSQL指令
    command = __build_update(model=model)
    response = await __request(command)
    return response
