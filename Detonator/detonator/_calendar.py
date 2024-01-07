def add_minus_to_YYYYmmdd(YYYYmmdd: str) -> str:
    return f'{YYYYmmdd[:4]}-{YYYYmmdd[4:6]}-{YYYYmmdd[6:]}' if '-' not in YYYYmmdd else YYYYmmdd


def remove_minus_in_YYYYmmdd(YYYYmmdd: str) -> str:
    return YYYYmmdd.replace('-', '')
