from pydantic import BaseModel
import datetime

class AllComments(BaseModel):
    time:datetime.datetime
    username:str
    superchat_price:float|None = None
    gift_name:str|None = None
    gift_price:float|None = None
    gift_num:int|None = None
    text:str
    clip_id:str
    user_id:str

class Comments(BaseModel):
    time:datetime.datetime
    username:str
    user_id:str
    superchat_price:float|None = None
    gift_name:str|None = None
    gift_price:float|None = None
    gift_num:int|None = None
    text:str
    clip_id:str

class OffComments(BaseModel):
    time:datetime.datetime
    username:str
    user_id:str
    superchat_price:float|None = None
    gift_name:str|None = None
    gift_price:float|None = None
    gift_num:int|None = None
    text:str
    liver_uid:str

class Channels(BaseModel):
    name:str
    bilibili_uid:str
    bilibili_live_room:int
    is_live:bool
    last_danmu:int
    total_clips:int
    total_danmu:int
    face:str
    hidden:bool
    archive:bool
    last_live:datetime.datetime

class ClipInfo(BaseModel):
    id:str
    bilibili_uid:str
    title:str
    start_time:datetime.datetime
    end_time:datetime.datetime|None = None
    cover:str
    danmu_density:float|None = None
    total_danmu:int|None = None
    total_gift:float|None = None
    total_superchat:float|None = None
    total_reward:float|None = None
    highlights:list[str]|None = None
    viewers:int|None = None