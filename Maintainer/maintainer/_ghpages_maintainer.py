from detonator import make_db_connection, mongo_2_df, SingletonParent, IDX_COUNTRY_EXCHANGE_MAP
from dataminer.models import MarketPe
from marketbreadth import MarketBreadth
from typing import Literal
from detonator import get_logger
from git import Repo
from git.remote import PushInfoList
import os

import tempfile
from datetime import datetime, timedelta
import json

REPO_URL = 'git@github.com:zhangyuz/Miner.git'

_logger = get_logger('Maintainer')


class GhPagesMaintainer(SingletonParent):
    def __init__(self, repo_url: str = REPO_URL, branch: str = 'main'):
        self.repo_url = repo_url
        self.branch = branch
        make_db_connection()

    def _export_market_pe(self, index: Literal['spx', 'qqq', 'ndx', 'hsi'], file: str, start_date: str | None = None, end_date: str | None = None):
        _, _, timezone = IDX_COUNTRY_EXCHANGE_MAP[index]
        end_date = datetime.now(tz=timezone).strftime('%Y-%m-%d')
        # Default to 20 years ago
        start_date = (datetime.now(tz=timezone) -
                      timedelta(days=365*20)).strftime('%Y-%m-%d')

        # Convert dates to datetime objects for querying
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        # Query the database
        query = {
            'idx': index,
            'trade_date__gte': start_dt,
            'trade_date__lte': end_dt
        }

        df = mongo_2_df(MarketPe.objects(**query).order_by('trade_date'))

        if df.empty:
            return {
                'index': index,
                'data': [],
                'stats': {
                    'avg_20y': 0,
                    'current_pe': 0,
                    'min_pe': 0,
                    'max_pe': 0
                }
            }

        # Convert to Highcharts format [timestamp, pe_value]
        data = []
        for _, row in df.iterrows():
            # Handle trade_date which might be a string from mongo_2_df
            if isinstance(row['trade_date'], str):
                # Parse the string date format from MongoDB
                # The scraper stores dates in format "2024,01,15,00,00,00,000000"
                try:
                    # Try to parse the custom format used by the scraper
                    dt = datetime.strptime(
                        row['trade_date'], '%Y,%m,%d,%H,%M,%S,%f')
                except ValueError:
                    try:
                        # Try to parse ISO format as fallback
                        dt = datetime.fromisoformat(
                            row['trade_date'].replace('Z', '+00:00'))
                    except ValueError:
                        # Fallback to other common formats
                        dt = datetime.strptime(
                            row['trade_date'], '%Y-%m-%d %H:%M:%S')
            else:
                # If it's already a datetime object
                dt = row['trade_date']

            timestamp = int(dt.timestamp() * 1000)  # Convert to milliseconds
            data.append([timestamp, round(float(row['pe']), 2)])

        # Calculate statistics
        pe_values = df['pe'].values
        avg_20y = float(pe_values.mean())
        current_pe = float(pe_values[-1]) if len(pe_values) > 0 else 0
        min_pe = float(pe_values.min())
        max_pe = float(pe_values.max())

        result = {
            'index': index,
            'data': data,
            'stats': {
                'avg_20y': round(avg_20y, 2),
                'current_pe': current_pe,
                'min_pe': round(min_pe, 2),
                'max_pe': round(max_pe, 2)
            }
        }
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    def _export_market_breadth(self, index: Literal['spx'], file: str, start_date: str = None, end_date: str = None):
        _, _, timezone = IDX_COUNTRY_EXCHANGE_MAP[index]
        if end_date:
            end_date = datetime.strptime(end_date, '%Y%m%d')
        else:
            end_date = datetime.now(tz=timezone)

        if start_date:
            start_date = datetime.strptime(start_date, '%Y%m%d')
        else:
            start_date = end_date - timedelta(days=36500)
        result = MarketBreadth.get_instance().get_market_breath(market_index=index, start_date=start_date,
                                                                end_date=end_date).to_dict(orient='records')
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result

    def _export_static_json(self, dir_of_miner: str):
        # Ensure all target directories exist
        os.makedirs(os.path.join(dir_of_miner, 'StkGuru', 'public', 'api', 'market_pe'), exist_ok=True)
        os.makedirs(os.path.join(dir_of_miner, 'StkGuru', 'public', 'api', 'mbs'), exist_ok=True)
        self._export_market_pe('spx', os.path.join(
            dir_of_miner, 'StkGuru', 'public', 'api', 'market_pe', 'spx.json'))
        self._export_market_pe('hsi', os.path.join(
            dir_of_miner, 'StkGuru', 'public', 'api', 'market_pe', 'hsi.json'))
        self._export_market_breadth('spx', os.path.join(
            dir_of_miner, 'StkGuru', 'public', 'api', 'mbs', 'spx.json'))

    def update_gh_pages(self) -> bool:
        try:
            # 1. Clone the repo to a temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                repo = Repo.clone_from(
                    url=self.repo_url, to_path=tmpdir, branch=self.branch)
                # 2. Pull the latest code (should be up-to-date after clone)
                repo.git.checkout(self.branch)
                repo.remotes.origin.pull()
                _logger.debug(f'{os.listdir(tmpdir)}')

                # 3. Run static export to the checked-out repo
                self._export_static_json(tmpdir)

                # 4. Check for changes
                repo.git.add(A=True)
                if repo.is_dirty(untracked_files=True):
                    repo.index.commit(
                        f'Update static data exports {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                    push_result: PushInfoList = repo.remotes.origin.push()
                    if  len(push_result) == 0:
                        _logger.error(f'Push failed: {push_result[0]}')
                        return False
                    else:
                        _logger.info(f'\n{repo.git.show()}\n')
                else:
                    # No changes to commit
                    _logger.info('No changes to commit')
                    return True

            return True
        except Exception as e:
            _logger.error(f"Failed to update gh-pages: {e}")
            return False
