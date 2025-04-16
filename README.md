# Matsuri-API - 自制麻酱后端
作为[matsuri](https://github.com/lue-trim/matsuri.icu)的后端使用，兼具与blrec联动更新弹幕数据库的功能

## Feature
- 纯Python实现
- 与[原版麻酱api](https://github.com/brainbush/api.matsuri.icu)完全兼容  
（更新弹幕数据的部分除外）
- 可以与[HarukaBot修改版](https://github.com/lue-trim/haruka-bot)共享同一个conda环境
- 与[blrec](https://github.com/lue-trim/haruka-bot)无缝对接

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
    在[HarukaBot](https://github.com/lue-trim/haruka-bot)的conda环境的基础上再安装一个toml包
    ```bash
    conda activate HarukaBot # 注意替换环境名字
    pip install toml
    ```
    > 需要注意的是，因为自动更新弹幕信息时blrec发送过来的不是弹幕文件本身，而是它的路径，所以matsuri-api最好跟blrec部署在**同一台**机器上
1. 修改配置  
    编辑config.toml，按照里面的说明修改一下设置就好
1. 运行  
    直接运行main.py就行
    ```bash
    python main.py
    ```
- 如果想手动更新弹幕和直播间信息怎么办？
    位于同一个目录下的`manual_update.py`可以帮忙（使用-h/--help查看具体使用说明）：
    ```bash
    python manual_update.py -h
    ```
- 那如果想删除弹幕或直播间信息呢？  
    可以自己登录PostgreSQL后端使用命令进行操作，不想要的内容直接删掉就可以了
    ```bash
    docker exec -itd postgres psql -U postgres
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
