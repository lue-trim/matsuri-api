import toml

class Config:
    __app:dict
    __postgres:dict
    __blrec:dict

    @property
    def app(self):
        'api设置'
        return self.__app

    @property
    def blrec(self):
        'blrec设置'
        return self.__blrec

    @property
    def postgres(self):
        '数据库设置'
        return self.__postgres

    def load(self, config_path="config.toml"):
        '加载配置'
        with open(config_path, 'r', encoding='utf-8') as f:
            config_file = toml.load(f)
            self.__app = config_file['app']
            self.__blrec = config_file['blrec']
            self.__postgres = config_file['postgres']

config = Config()
