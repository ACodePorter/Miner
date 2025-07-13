from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pytz
from dataminer import MarketDataShovel, TradeCalendarShovel
from dataminer.models import IndexTickers, Ticker
from detonator import SingletonParent, make_db_connection, mongo_2_df, get_logger
from pandas import DataFrame

from .models import MarketBreadthScore, MarketBreadthSectorScore

_logger = get_logger('MarketBreadth')
_mds: MarketDataShovel = MarketDataShovel.get_instance()
_tcs: TradeCalendarShovel = TradeCalendarShovel.get_instance()

_default_start_date = datetime.now(tz=pytz.timezone(
    'America/New_York')) - timedelta(days=730)


class MarketBreadth(SingletonParent):
    def update_index_breadth(self, index_name: str) -> bool:
        _logger.info(f'updating index breadth: {index_name}')
        try:
            self._do_update_index_breadth(index_name)
            return True
        except Exception as e:
            _logger.error(
                f'Failed to update index breadth for {index_name}', exc_info=e)
            return False

    # TODO Rename this here and in `update_index_breadth`
    def _do_update_index_breadth(self, index_name: str = 'spx'):
        make_db_connection()
        first = MarketBreadthScore.objects(
            index_name=index_name).order_by('-trade_date').limit(1).first()
        start_date = first.trade_date if first else _default_start_date.strftime(
            '%Y%m%d')
        trade_dates = _tcs.us_trade_dates_since(start_date)
        last_closed_trade_date = _tcs.last_closed_us_trade_date()
        # 由于上边返回的事逆序的，这里需要顺序的数据
        trade_dates.sort()
        # _logger.debug(f'trade dates: {trade_dates}')
        index_tickers: Optional[IndexTickers] = None
        tickers: Optional[DataFrame] = None
        results = {}
        for trade_date in trade_dates:
            if trade_date > last_closed_trade_date:
                _logger.warning(
                    f'Skip {trade_date} >= {last_closed_trade_date}')
                continue
            if (not index_tickers) or index_tickers.as_of_date < trade_date:
                index_tickers = _mds.get_index_tickers_on(index_name, trade_date)
                # _logger.debug(index_tickers.tickers)
                tickers = mongo_2_df(Ticker.objects(
                    ticker__in=index_tickers.tickers))
                # _logger.debug(f'updating index tickers & tickers:{tickers}\n')
            sectors = tickers['sectorKey'].unique().tolist()
            sectors.sort()
            market_breadth_score = MarketBreadthScore(index_name=index_name,
                                                      trade_date=datetime.strptime(
                                                          trade_date, '%Y%m%d'),
                                                      sector_score20=[], sector_score50=[], sector_score200=[])
            if index_tickers and not tickers.empty:
                daily_infos = _mds.get_tickers_daily_info_on(
                    tickers=index_tickers.tickers, trade_date=trade_date)
                # _logger.debug(f'tickers:{tickers.head(2)}')
                # _logger.debug(f'daily_infos:{daily_infos.head(2)}')
                if 'ticker' not in tickers.columns or 'ticker' not in daily_infos.columns:
                    _logger.error(f"'ticker' column missing in tickers or daily_infos DataFrame")
                    _logger.error(f"tickers columns: {tickers.columns}")
                    _logger.error(f"daily_infos columns: {daily_infos.columns}")
                    continue
                if tickers.empty or daily_infos.empty:
                    _logger.error(f"tickers or daily_infos DataFrame is empty for trade_date {trade_date}")
                    continue
                full_daily = pd.merge(
                    tickers, daily_infos, how='inner', on='ticker')
                sector_score20 = []
                sector_score50 = []
                sector_score200 = []
                sma_20_score = 0
                sma_50_score = 0
                sma_200_score = 0
                for sector in sectors:
                    sector_daily = full_daily[full_daily['sectorKey'] == sector]
                    if sector == 'N/A':
                        _logger.warning(f"Skip sector {sector} on {trade_date} \n{sector_daily['ticker'].values}")
                        continue
                    sector_sma20_gte = sector_daily['sma20'] <= sector_daily['close']
                    sector_sma50_gte = sector_daily['sma50'] <= sector_daily['close']
                    sector_sma200_gte = sector_daily['sma200'] <= sector_daily['close']
                    if sector_sma20_gte.count() == 0:
                        _logger.warning(f"No data for sector {sector} on {trade_date}")
                        continue
                    sector_sma_20_score = round(100 * sector_sma20_gte.sum() / sector_sma20_gte.count(), 2)
                    sector_sma_50_score = round(100 * sector_sma50_gte.sum() / sector_sma50_gte.count(), 2)
                    sector_sma_200_score = round(100 * sector_sma200_gte.sum() / sector_sma200_gte.count(), 2)
                    market_breadth_score.sector_score20.append(
                        MarketBreadthSectorScore(sector_key=sector, score=sector_sma_20_score))
                    market_breadth_score.sector_score50.append(
                        MarketBreadthSectorScore(sector_key=sector, score=sector_sma_50_score))
                    market_breadth_score.sector_score200.append(
                        MarketBreadthSectorScore(sector_key=sector, score=sector_sma_200_score))
                    sma_20_score += sector_sma_20_score
                    sma_50_score += sector_sma_50_score
                    sma_200_score += sector_sma_200_score
                # After the sector loop, round the overall scores as well
                market_breadth_score.score_sma20 = round(sma_20_score, 2)
                market_breadth_score.score_sma50 = round(sma_50_score, 2)
                market_breadth_score.score_sma200 = round(sma_200_score, 2)
                market_breadth_score.save()
            else:
                _logger.error(
                    f'Failed to update index score for {index_name} on {trade_date}')
        return True

    def get_market_breath(self, market_index: str = 'spx', start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> DataFrame:
        # TODO: update timezone by market_index
        # TODO: add pagination
        end_date = end_date or datetime.now(
            tz=pytz.timezone('America/New_York'))
        start_date = start_date or datetime.now(
            tz=pytz.timezone('America/New_York')) - timedelta(days=35600)
        query = {
            'index_name': market_index,
            'trade_date__gte': start_date,
            'trade_date__lte': end_date
        }
        return mongo_2_df(MarketBreadthScore.objects(**query).order_by('trade_date'))
