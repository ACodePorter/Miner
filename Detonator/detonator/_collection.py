from typing import Iterable, Dict, Any


def list_minus(l1: Iterable[Any], l2: Iterable[Any]) -> Iterable[Any]:
    return [item for item in l1 if item not in l2]


def common_in_list(l1: Iterable[Any], l2: Iterable[Any]) -> Iterable[Any]:
    return [item for item in l1 if item in l2]


def subdict(sub_keys: Iterable[str], orig_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据指定的 Key 获取 Dict 的子 Dict
    """
    return {key: orig_dict[key] for key in sub_keys}
