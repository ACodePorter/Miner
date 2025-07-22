# Miner

Miner is a modular, Dockerized platform for collecting, processing, and serving financial market data, with a focus on US equities and market breadth analytics. It is designed for easy deployment, automation, and extensibility, supporting both research and production use cases.

## Project Structure

- **BrowserScraper**: Scrapes market valuation data (e.g., P/E ratios) from web sources and updates the database automatically via Celery tasks.
- **DataMiner**: Core data ingestion and management for US stock market data, including tickers, daily info, financials, and indicators. Integrates with Yahoo Finance, iShares, and more.
- **Detonator**: Shared utilities for logging, configuration, database connections, and other infrastructure needs.
- **MinerService**: FastAPI-based web service exposing REST APIs for data updates, queries, and analytics.
- **MinerWorkers**: Celery worker setup and configuration for distributed task execution.
- **MarketBreadth**: Calculates and stores market breadth indicators (e.g., % of stocks above SMA) by sector and index.
- **Deploy**: Docker and deployment scripts/configuration for all services.
- **Misc**: Utility scripts for maintenance, backup, and data correction.

## Quick Start

1. **Clone the repository**
2. **Install Docker & Docker Compose**
   - All code is developed and tested on macOS, but should work on any Unix-like system with Docker/Docker Compose
   - You should have docker and docker compose installed (Docker/DockerDesktop/OrbStack, etc.)
3. **Deploy with one command:**

```bash
./Deploy/deploy.sh <github_pat_token> <runtime_env[PROD|TEST|DEV]> [miner_data_dir]
```
- `<github_pat_token>`: Your GitHub Personal Access Token (required for Maintainer build)
- `<runtime_env>`: One of `PROD`, `TEST`, or `DEV`
- `[miner_data_dir]`: (Optional) Path to store persistent data (default: `$HOME/.miner/data`)

## Docker Compose Services

- **mongodb**: MongoDB 8.0.5 for persistent data storage
- **redis**: Redis for Celery task queue
- **rabbitmq**: RabbitMQ for Celery broker
- **browserscraper**: Scrapes market valuation data
- **maintainer**: Handles maintenance and GitHub integration
- **miner**: Main API and background service (FastAPI, Celery, etc.)

## API Usage

- Visit `http://localhost/docs` for interactive API documentation (Swagger UI)
- Visit `http://localhost/flower` to monitor Celery tasks

### Main API Endpoints

- `GET /update_us_trade_calendar` — Update US trade calendar
- `GET /update_spx_tickers_info`, `/update_iwd_tickers_info`, `/update_iwf_tickers_info`, `/update_iwm_tickers_info` — Update index tickers info
- `GET /update_spx_tickers_daily_info`, `/update_iwd_tickers_daily_info`, `/update_iwf_tickers_daily_info`, `/update_iwm_tickers_daily_info` — Update daily info for tickers
- `POST /update_tickers_daily_info` — Update daily info for a list of tickers
- `GET /update_spx_daily_ma`, `/update_iw_daily_ma` — Update moving averages
- `GET /update_market_pe` — Update market PE ratios
- `GET /update_spx_market_breadth` — Update market breadth for SPX
- `GET /update_all_above` — Run all update tasks
- `POST /update_indicators_for_tickers` — Update indicators for a list of tickers
- `GET /api/mbs/{market_index}.json` — Get market breadth scores
- `GET /api/market_pe/{index}.json` — Get market PE data (supports `spx` and `qqq`, with optional date range)

## Features

- Automated scraping and updating of financial market data
- Market breadth analytics by sector and index
- Modular, extensible design for easy integration and expansion
- REST API for programmatic access
- Distributed task execution with Celery
- Dockerized for easy deployment and scaling
- Improved deployment speed (using `uv` for Python dependencies)
- Updated to Python 3.12 and Ubuntu 24.04
- Enhanced ticker validation and Russell index ticker handling

## Automation & Background Tasks

- **Background Celery tasks** automatically update end-of-day (EOD) data, ensuring your database is always fresh and up-to-date.
- These tasks include:
  - Market P/E ratio updates
  - Daily data updates for stocks and indices
  - Market breadth calculations
- All background jobs are managed and scheduled via Celery, and can be monitored using the Flower dashboard (`http://localhost/flower`).

## Development & Testing

- Each module contains its own tests (see the `test/` directories)
- To run tests for a module:
  - Example: `cd DataMiner/test && ./run.sh`
- Celery is used for distributed/background tasks
- MongoDB, Redis, and RabbitMQ are orchestrated via Docker Compose

## Dependencies

Each module has its own `requirements.txt`. Main dependencies include:
- FastAPI, Uvicorn, Gradio, fastapi-cors (MinerService)
- Celery, Flower, Gevent (MinerWorkers)
- MongoEngine, Pymongo, jsmin, rich (Detonator, MarketBreadth, DataMiner)
- pandas, yfinance, requests, exchange_calendars, etc. (DataMiner)
- selenium, webdriver_manager (BrowserScraper)

Dependencies are installed automatically during deployment using `uv` for speed.

## TODO

- [ ] **Unify date time handling: format/storage**
- [X] Remove Tushare related docs/codes/comments (no longer used)
- [ ] Add MCP server for stock market data
- [ ] Add SEC EDGAR data
- [ ] Decide how to save tickers with symbol in it, like 'BRK-A' or "BRK.A"
    - [ ] Now we store them as 'BRK.A', maybe 'BRK-A' would be better since it matches SEC and Yahoo data, TBD
- [ ] MongoDB query performance optimization
    - [ ] Replace mongoengine with pymongo
- [X] Improve deployment speed by using uv instead of pip
- [ ] Avoid querying db for trade calendar every time before getting stock data
    - [ ] Add a cache for trade calendar, like 1 day
- [X] Regular Russell index ticker names (class A/class B stock tickers incorrect, like BFA/BFB)
    - Like correcting company ticker based on name and https://www.sec.gov/files/company_tickers.json
- [X] Add Russell index tickers bootstrap, getting history tickers record
- [X] Make MongoDB run in separated container
- [ ] ~~Config proxy from environment variable or command line~~
- [X] 增加日线数据获取失败处理(偶尔,无法从yahoo获取某些股票的日线数据,需要第二天重新获取更新)
- [X] Update Miniconda to Python 3.12
- [X] Update Ubuntu to 24.04
- [X] 优化获取 yahoo 数据时间间隔管理,减少等待时间
- [X] Reduce logs of celery
