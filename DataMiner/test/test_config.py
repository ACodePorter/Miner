from unittest import TestCase

from detonator import Config

_CONFIG_JSON_STR = '''{
"a":"A",
"b":{"bb":"BB"},
"c":["CC", "CC", "CC"],
"d":{"dd":["DDD", "DDD"], "ddd":{"dddd":"DDDD"}},
"e":[{"ee":"EEE"}, {"eee":"EEE"}]
}
'''


class ConfigTestCase(TestCase):

    def setUp(self) -> None:
        pass

    def test_config(self):
        config = Config.from_str(_CONFIG_JSON_STR)
        print(config.a)
        print(config.b.bb)
        print(config.c)
        print(config.d.dd[0])
        print(config.d.ddd.dddd)
        print(config.e[0].ee)

    def tearDown(self) -> None:
        pass
