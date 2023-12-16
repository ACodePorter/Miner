import json
from os import PathLike

from jsmin import jsmin

from ._path import to_real_abs_path


class Config:
    @staticmethod
    def from_file(config_file: str | PathLike) -> 'Config':
        try:
            config_file = to_real_abs_path(config_file)
            with open(config_file, encoding='utf-8', mode='r') as f:
                return Config.from_str(f.read())
        except Exception as e:
            print(f'Failed to create Config:{e}')

    @staticmethod
    def from_str(config_json_str: str) -> 'Config':
        if json_str := jsmin(config_json_str):
            return Config(**json.loads(json_str))
        else:
            print(f'Failed to parse: {config_json_str}')

    def __init__(self, **d):
        self.__d = d
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, Config(**v))
            elif isinstance(v, (list, tuple)):
                setattr(
                    self, k, [Config(**item) if isinstance(item, dict) else item for item in v])
            else:
                setattr(self, k, v)

    def __repr__(self):
        return f'Config:{self.__d}'


_configs = {}


def parser_config(path: str) -> Config:
    _configs[path] = Config.from_file(
        path) if path not in _configs else _configs[path]
    return _configs[path]
