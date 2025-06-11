# Miner

## Get Started with Miner Development

1. Enable git lfs (not used for now)

```shell
# 为了 github 包含超过 100MB 的大文件
brew install git-lfs
```

2. Tushare api key

register a free account https://tushare.pro, and get a api key

3. Docker & Docker Compose

4. A proxy for accessing Yahoo Finance
ssh tunnel as socks5 proxy for me, you should modify it to work for you

## Deployment

```bash
./Deploy/deploy.sh <tushare_key> <runtime_env[PROD|TEST|DEV]> [miner_data_dir]
```

## Usage

open http://localhost/docs, you'll see.

## TODO

- [ ] mongo db query performance optimization
    - [ ] replace mongoengine with pymongo
- [X] ~~improve deployment speed by using uv instead of pip~~
- [ ] avoid querying db for trade calendar every time before getting stock data
    - [ ] add a cache for trade calendar, like 1 day
- [ ] regular russell index ticker names(class A/class B stock tickers incorrect, like BFA/BFB)
    - like correcting company ticker based on name and https://www.sec.gov/files/company_tickers.json
- [X] ~~add russell index tickers bootstrap, getting history tickers record~~
- [X] ~~make mongodb run in seperated container~~
- [ ] ~~config proxy from environment variable or command line~~
- [ ] 增加日线数据获取失败处理(偶尔,无法从yahoo获取某些股票的日线数据,需要第二天重新获取更新)
- [X] ~~update miniconda to Python 3.12~~
- [X] ~~update Ubuntu to 24.04~~
- [X] ~~优化获取 yahoo 数据时间间隔管理,减少等待时间~~
- [X] ~~reduce logs of celery~~

