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
2. ~~Set up your Tushare API key** (if needed)~~**(Not needed, since not using it any more)**
   - ~~Register at https://tushare.pro/register?reg=253543 and get an API key~~
3. **Install Docker & Docker Compose**
   - All code is developed and tested on macOS, but should work on any Unix-like system with Docker/Docker Compose
   - You should have docker and docker compose installed, you can choose whatever you like, Docker/DockerDesktop/OrbStack
4. **Deploy with one command:**

```bash
./Deploy/deploy.sh whatever-not-important <runtime_env[PROD|TEST|DEV]> [miner_data_dir]
```

## API Usage

- Visit `http://localhost/docs` for interactive API documentation (Swagger UI)
  - API endpoints
- Visit `http://localhost/flower` to monitor Celery tasks

## Features

- Automated scraping and updating of financial market data
- Market breadth analytics by sector and index
- Modular, extensible design for easy integration and expansion
- REST API for programmatic access
- Distributed task execution with Celery
- Dockerized for easy deployment and scaling

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

## TODO

- [ ] **Unify date time handling: format/storage**
- [ ] remove tushare related docs/codes/comments, since it was not being used any more
- [ ] add MCP server for stock market data
- [ ] add sec edgar data
- [ ] decide how to save tickers with symbol in it, like'BRK-A' or "BRK.A"
    - [ ] now we store them as 'BRK.A', may be 'BRK-A' would be better since it matches SEC and YH data,TBD
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
