import sys
import toml, loguru

class __Config:
    __app:dict
    __postgres:dict
    __log:dict
    __subtitle:dict

    def __init__(self, config_path="config.toml"):
        self.load(config_path)

    @property
    def app(self):
        'api设置'
        return self.__app

    @property
    def postgres(self):
        '数据库设置'
        return self.__postgres

    @property
    def log(self):
        '日志记录器'
        return self.__log
    
    @property
    def subtitle(self):
        '字幕同步'
        return self.__subtitle

    def load(self, config_path="config.toml"):
        '加载配置'
        with open(config_path, 'r', encoding='utf-8') as f:
            config_file = toml.load(f)
            self.__app = config_file['app']
            self.__postgres = config_file['postgres']
            self.__log = config_file['log']
            self.__subtitle = config_file['subtitle']

config = __Config()

# 初始化记录器
loguru.logger.remove()
log_file = config.log['file']
level = config.log['level']
if log_file:
    loguru.logger.add(log_file, enqueue=True, level=level)
else:
    loguru.logger.add(sys.stdout, enqueue=True, level=level)
