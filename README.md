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

## Environments Variables

```bash
RUNTIME_ENV=prod/dev
```

## Deployment

```bash
./Deploy/deploy.sh your_tushare_api_key
```

## Usage

open http://localhost/docs, you'll see.

## TODO

- [ ] add russell index tickers bootstrap, getting history tickers record
