# Matsuri-API - 自制麻酱后端
作为[matsuri](https://github.com/lue-trim/matsuri.icu)的后端使用，兼具与blrec联动更新弹幕数据库的功能

## Feature
- FastAPI异步实现
- 与[api.matsuri.icu](https://github.com/brainbush/api.matsuri.icu)大致兼容  
（仅数据库的clipinfo部分字段有差异）
- 可以与[HarukaBot修改版](https://github.com/lue-trim/haruka-bot)共享同一个conda环境
- 与[blrec](https://github.com/lue-trim/haruka-bot)无缝对接
- 自己增加了一部分的增删改REST接口

## 整个项目的组成部分简介
### matsuri-api (本仓库)  
后端服务器，负责数据管理和信息交互
### [blrec](https://github.com/lue-trim/haruka-bot)  
虽然主业是录播，但在这里主要是提供弹幕数据的，利用webhook机制与后端交互
### [PostgreSQL](https://www.postgresql.org)  
数据库，存储所有弹幕信息并与后端交互

## 部署说明
### PostgreSQL
最简单的办法是直接通过官方Docker镜像部署
1. 下载  
    ```bash
    docker pull postgres:latest
    ```
1. 运行  
    可以参考以下配置
    ```bash
    docker run -d \
    -e POSTGRES_PASSWORD=<数据库密码> \ # 要和后端的设置相同
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -v <路径>:/var/lib/postgresql/data \ # 存放数据库用的，最好是空文件夹
    -p <端口号>:5432 \ # 映射到本地的端口号，随便取，注意要和后端的设置对应上
    --restart unless-stopped \ # 崩溃时自动重启
    --name postgres \ # 容器名称，可以随便设置
    postgres:latest
    ```
1. 不出意外的话只要让它一直运行就可以了
### matsuri-api
1. 环境  
    在[HarukaBot](https://github.com/lue-trim/haruka-bot)的基础上再安装一个toml包
    ```bash
    pip install toml
    ```
    > 需要注意的是，因为自动更新弹幕信息时blrec只会发过来文件路径，而不是发送具体内容，所以matsuri-api最好跟blrec部署在**同一台**机器上
1. 修改配置  
    编辑config.toml，按照里面的说明修改一下设置就好
1. 运行  
    直接运行main.py就行
    ```bash
    python main.py
    ```
- 如果想手动更新/删除弹幕和直播间信息怎么办？  
    位于同一个目录下的`manual_update.py`可以完成直播间信息/场次信息/弹幕的补录、更新和删除操作（使用-h/--help查看具体使用说明）：  
    但是因为封面只能靠即时获取，所以没有留下更新封面的接口；如果要修改，得手动进postgres后台改一下（见下文）  
    ```bash
    python manual_update.py -h
    ```
- 那如果想手动修改更多信息呢？  
    可以自己登录PostgreSQL终端操作
    ```bash
    docker exec -it postgres psql -U postgres
    ```
### blrec
1. 在`Webhooks`设置里添加matsuri-api的url，比如：
    ```
    http://localhost:23562/rec
    ```
    记得加上最后那个/rec
1. 勾选上`开播`、`下播`、`原始弹幕文件完成`三个事件
    > 全选也可以，但是会增加资源占用，不是很有必要

至此配置就完成了，使用愉快！
