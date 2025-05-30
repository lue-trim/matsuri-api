# Matsuri-API - 自制麻酱后端
作为[matsuri](https://github.com/lue-trim/matsuri.icu)的后端使用，兼具与blrec联动更新弹幕数据库的功能

## Feature
- FastAPI异步实现
- 与[api.matsuri.icu](https://github.com/brainbush/api.matsuri.icu)大致兼容  
（仅数据库的clipinfo部分字段有差异）
- 可以与[HarukaBot修改版](https://github.com/lue-trim/haruka-bot)共享同一个conda环境
- 与[blrec](https://github.com/lue-trim/haruka-bot)无缝对接
- 自己增加了一部分的增删改REST接口
- 自动同步官方录播生成的AI字幕，并将其作为翻译man弹幕处理

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
> **注意**  
> 在录完之后，blrec只会告诉matsuri-api哪场直播录完了，而不会把具体的弹幕数据发送过来，所以matsuri-api最好跟blrec部署在**同一台**机器上
1. 环境  
    以下两个选项二选一：
    1. 在[HarukaBot](https://github.com/lue-trim/haruka-bot)的环境基础上再安装一个toml包
        ```bash
        pip install toml
        ```
        > 毕竟跟HarukaBot选用的架构路线都差不多
    1. 也可以参考这个yml从头安装一个conda环境
        ```yaml
        name: # 填一下环境的名字
        channels:
        - conda-forge
        dependencies:
        - _libgcc_mutex=0.1=conda_forge
        - _openmp_mutex=4.5=2_gnu
        - bzip2=1.0.8=h4bc722e_7
        - ca-certificates=2025.4.26=hbd8a1cb_0
        - ld_impl_linux-64=2.43=h712a8e2_4
        - libexpat=2.7.0=h5888daf_0
        - libffi=3.4.6=h2dba641_1
        - libgcc=14.2.0=h767d61c_2
        - libgcc-ng=14.2.0=h69a702a_2
        - libgomp=14.2.0=h767d61c_2
        - libiconv=1.18=h4ce23a2_1
        - liblzma=5.8.1=hb9d3cd8_0
        - libnsl=2.0.1=hd590300_0
        - libsqlite=3.49.1=hee588c1_2
        - libuuid=2.38.1=h0b41bf4_0
        - libxcrypt=4.4.36=hd590300_1
        - libxml2=2.13.7=h81593ed_1
        - libxslt=1.1.39=h76b75d6_0
        - libzlib=1.3.1=hb9d3cd8_2
        - lxml=4.6.5=py310ha5446b1_0
        - ncurses=6.5=h2d0b736_3
        - openssl=3.5.0=h7b32b05_0
        - pip=25.1=pyh8b19718_0
        - python=3.10.17=hd6af730_0_cpython
        - python_abi=3.10=7_cp310
        - readline=8.2=h8c095d6_2
        - setuptools=79.0.1=pyhff2d567_0
        - tk=8.6.13=noxft_h4845f30_101
        - tzdata=2025b=h78e105d_0
        - wheel=0.45.1=pyhd8ed1ab_1
        - pip:
            - bilibili-api-python==17.2.0
            # - haruka-bot==1.7.5
            - httpx==0.27.2
            - requests==2.32.3
            - toml==0.10.2
        ```
1. 修改配置  
    编辑config.toml，按照里面的说明修改一下设置就好  
    > **特别说明**  
    > 如果要取消自动同步官方录播AI字幕的功能，把`[[subtitle.config]]`删掉，对应位置改成`subtitle.config = []`就可以了  
1. 运行  
    直接运行main.py就行
    ```bash
    python main.py
    ```
- 如果想手动更新/删除弹幕和直播间信息怎么办？  
    位于同一个目录下的`manual_update.py`可以完成直播间信息/场次信息/弹幕的补录、更新和删除操作（使用-h/--help查看具体使用说明）：  
    ```bash
    python manual_update.py -h  
    ### 几个常用功能
    # 1. 手动获取AI字幕并添加到录播站
    python manual_update.py add -s --bvid BV1DQ4y1j7bE --clip 902b4438-b553-53bf-b803-ebde2ef400a4
    # 2. 手动刷新直播间信息
    python manual_update.py refresh --room 41682
    # 3. 手动添加弹幕(自动识别并添加场次信息)
    python manual_update.py add -d ~/rec/20250530/
    ```
    > **提示**  
    > 1. 手动上传弹幕文件时，会自动识别所有的子文件夹  
    > 1. 不管是自动同步还是手动上传弹幕，都会强制通过匹配*文件包含的最后一条弹幕*来判断对应的弹幕文件有没有上传过，以避免弹幕重复的问题  
    > 1. 如果没有原始弹幕文件（`*.jsonl`），也可以手动上传包含blrec弹幕文件（`*.xml`）的文件夹，但是“观看人数”会显示成0

    但是因为封面只能靠即时获取，弹幕文件里面没记录，所以没做更新封面的接口；如果要修改，得手动进postgres后台改一下（见下文）  
- 那如果想手动修改更多信息呢？  
    可以自己登录PostgreSQL终端操作
    ```bash
    docker exec -it postgres psql -U postgres
    ```
### blrec
> **提示**  
> matsuri-api设计之初就考虑了分段录制的处理，只要是同一场直播，即使是分段录的弹幕也会被自动归类到一起  
>（只要不是手动点的/超管切的下播，短时间断流都没影响）
1. 在`Webhooks`设置里添加matsuri-api的url，比如：
    ```
    http://localhost:23562/rec
    ```
    记得加上最后那个/rec
1. 打开`设置 > 弹幕`里的`保存原始弹幕`选项  
1. 勾选上`开播`、`下播`、`录制完成`、`原始弹幕文件完成`4个事件
    > 全选也可以，但是没必要（

至此配置就完成了，使用愉快！
