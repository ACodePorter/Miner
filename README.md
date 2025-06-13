# Miner

This is a repository for syncing/storing/managing financial market data. you can deploy it to your host by one command.


## Get Started with Miner

1. Tushare api key

register a free account at https://tushare.pro/register?reg=253543, and get a api key

2. Install Docker & Docker Compose(I am using orbstack on macOS)
> All the code was developed and tested on macOS, it should be working on all unix-like system with Docker/Docker Compose installed

## Deployment

```bash
./Deploy/deploy.sh <tushare_key> <runtime_env[PROD|TEST|DEV]> [miner_data_dir]
```

## Usage

1. http://localhost/docs, you'll see the APIs.
2. http://localhost/flower, see the celery tasks

## TODO

- [ ] add MCP server for stock market data
- [ ] add sec edgar data
- [ ] mongo db query performance optimization
    - [ ] replace mongoengine with pymongo
- [X] improve deployment speed by using uv instead of pip
- [ ] avoid querying db for trade calendar every time before getting stock data
    - [ ] add a cache for trade calendar, like 1 day
- [X] regular russell index ticker names(class A/class B stock tickers incorrect, like BFA/BFB)
    - like correcting company ticker based on name and https://www.sec.gov/files/company_tickers.json
- [X] add russell index tickers bootstrap, getting history tickers record
- [X] make mongodb run in seperated container
- [ ] ~~config proxy from environment variable or command line~~
- [X] 增加日线数据获取失败处理(偶尔,无法从yahoo获取某些股票的日线数据,需要第二天重新获取更新)
- [X] update miniconda to Python 3.12
- [X] update Ubuntu to 24.04
- [X] 优化获取 yahoo 数据时间间隔管理,减少等待时间
- [X] reduce logs of celery

