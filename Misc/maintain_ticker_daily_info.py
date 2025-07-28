#!/usr/bin/env python3
"""
Script to maintain TickerDailyInfo collection by removing duplicates.

This script:
1. Enumerates all documents by trade_date from trade calendar backwards
2. Checks on each trading day for duplicated documents with same ticker and interval
3. Removes duplicates and keeps only one document per ticker/interval/trade_date combination
4. Supports dry-run mode to print what would be done without making changes
"""

import argparse
import datetime
import os
from collections import defaultdict
from multiprocessing import Pool
from typing import Any, Dict, List

from dataminer import TradeCalendarShovel
from dataminer.models import TickerDailyInfo, TradeCalendar
from detonator import get_logger, make_db_connection
from mongoengine import disconnect

_logger = get_logger('MaintainTickerDailyInfo')


class TickerDailyInfoMaintainer:
    """Maintains TickerDailyInfo collection by removing duplicates."""

    def __init__(self):
        self.tcs = TradeCalendarShovel.get_instance()
        make_db_connection()

    def get_trading_dates_backwards(self, start_date: str | None = None, end_date: str | None = None, limit: int | None = None) -> List[str]:
        """
        Get trading dates in descending order (newest first).

        Args:
            start_date: Start date in YYYYMMDD format, defaults to latest available
            limit: Maximum number of dates to return, defaults to all

        Returns:
            List of trading dates in YYYYMMDD format, newest first
        """
        try:
            # Update trade calendar first
            self.tcs.update_us_trade_calendar()

            # Build query
            query = {'country': 'us', 'is_open': True}
            if start_date:
                query['cal_date__gte'] = start_date
            if end_date:
                query['cal_date__lte'] = end_date

            _logger.debug(query)
            # Get trading dates in descending order
            trade_dates = TradeCalendar.objects(**query).order_by('-cal_date')

            if limit:
                trade_dates = trade_dates.limit(limit)

            return [t.cal_date for t in trade_dates]

        except Exception as e:
            _logger.error(f'Failed to get trading dates: {e}')
            return []

    def find_duplicates_for_date(self, trade_date: str) -> Dict[str, List[TickerDailyInfo]]:
        """
        Find duplicate documents for a specific trading date.

        Args:
            trade_date: Trading date in YYYYMMDD format

        Returns:
            Dictionary mapping (ticker, interval) to list of duplicate documents
        """
        try:
            # Convert YYYYMMDD to datetime for query
            date_obj = datetime.datetime.strptime(trade_date, '%Y%m%d')

            # Get all documents for this date
            documents = TickerDailyInfo.objects(trade_date=date_obj)

            # Group by ticker and interval
            grouped = defaultdict(list)
            for doc in documents:
                key = (doc.ticker, doc.interval)
                grouped[key].append(doc)

            # Filter to only groups with duplicates
            duplicates = {key: docs for key,
                          docs in grouped.items() if len(docs) > 1}

            return duplicates

        except Exception as e:
            _logger.error(
                f'Failed to find duplicates for date {trade_date}: {e}')
            return {}

    def remove_duplicates(self, duplicates: Dict[str, List[TickerDailyInfo]], dry_run: bool = True) -> Dict[str, int]:
        """
        Remove duplicate documents, keeping only one per ticker/interval combination.

        Args:
            duplicates: Dictionary mapping (ticker, interval) to list of duplicate documents
            dry_run: If True, only print what would be done without making changes

        Returns:
            Dictionary with statistics about the operation
        """
        stats = {
            'total_groups': len(duplicates),
            'total_documents_removed': 0,
            'groups_processed': 0
        }

        for (ticker, interval), docs in duplicates.items():
            if len(docs) <= 1:
                continue

            # Sort by creation time (oldest first) to keep the first one
            docs.sort(key=lambda x: x.id.generation_time if hasattr(
                x.id, 'generation_time') else x.id)

            # Keep the first document, remove the rest
            docs_to_remove = docs[1:]

            if dry_run:
                _logger.info(
                    f'[DRY RUN] Would remove {len(docs_to_remove)} duplicates for {ticker} ({interval}) on {docs[0].trade_date.strftime("%Y-%m-%d")}')
                for doc in docs_to_remove:
                    _logger.info(
                        f'  [DRY RUN] Would remove: {doc.id} - {doc.ticker} {doc.interval} {doc.trade_date}')
            else:
                for doc in docs_to_remove:
                    try:
                        doc.delete()
                    except Exception as e:
                        _logger.error(
                            f'Failed to remove document {doc.id}: {e}')
                        continue

            stats['total_documents_removed'] += len(docs_to_remove)
            stats['groups_processed'] += 1

        return stats

    def maintain_collection(self, start_date: str = "19620102", end_date: str = "20250712", limit: int | None = None, dry_run: bool = True) -> Dict[str, Any]:
        """
        Main method to maintain the TickerDailyInfo collection.

        Args:
            start_date: Start date in YYYYMMDD format, defaults to latest available
            limit: Maximum number of trading dates to process, defaults to all
            dry_run: If True, only print what would be done without making changes

        Returns:
            Dictionary with overall statistics
        """
        _logger.info(
            f'Starting TickerDailyInfo maintenance (dry_run={dry_run})')
        if start_date:
            _logger.info(f'Starting from date: {start_date}')
        if limit:
            _logger.info(f'Processing up to {limit} trading dates')

        # Get trading dates
        trading_dates = self.get_trading_dates_backwards(
            start_date, end_date, limit)
        if not trading_dates:
            _logger.warning('No trading dates found')
            return {'error': 'No trading dates found'}

        _logger.info(f'Found {len(trading_dates)} trading dates to process')

        overall_stats = {
            'trading_dates_processed': 0,
            'total_groups_with_duplicates': 0,
            'total_documents_removed': 0,
            'dates_with_duplicates': 0
        }

        # Process each trading date
        for trade_date in trading_dates:
            _logger.info(f'Processing trading date: {trade_date}')

            # Find duplicates for this date
            duplicates = self.find_duplicates_for_date(trade_date)

            if duplicates:
                overall_stats['dates_with_duplicates'] += 1

                # Remove duplicates
                date_stats = self.remove_duplicates(duplicates, dry_run)

                overall_stats['total_groups_with_duplicates'] += date_stats['total_groups']
                overall_stats['total_documents_removed'] += date_stats['total_documents_removed']

            overall_stats['trading_dates_processed'] += 1

        # Print summary
        _logger.info('=' * 50)
        _logger.info('MAINTENANCE SUMMARY:')
        _logger.info(
            f'Trading dates processed: {overall_stats["trading_dates_processed"]}')
        _logger.info(
            f'Dates with duplicates: {overall_stats["dates_with_duplicates"]}')
        _logger.info(
            f'Total groups with duplicates: {overall_stats["total_groups_with_duplicates"]}')
        _logger.info(
            f'Total documents removed: {overall_stats["total_documents_removed"]}')
        _logger.info('=' * 50)

        return overall_stats


def do_maintain(start_date: str, end_date: str, limit: int, dry_run: bool) -> int:
    """
    Worker function for process pool to maintain a date range.

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format  
        limit: Maximum number of trading dates to process
        dry_run: If True, only print what would be done without making changes

    Returns:
        0 on success, 1 on error
    """
    try:
        # Create maintainer and run maintenance
        maintainer = TickerDailyInfoMaintainer()
        stats = maintainer.maintain_collection(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            dry_run=dry_run
        )

        if 'error' in stats:
            _logger.error(f'Maintenance failed: {stats["error"]}')
            return 1

        _logger.info('Maintenance completed successfully')
        return 0
    except Exception as e:
        _logger.error(f'Unexpected error in do_maintain: {e}')
        return 1


def distribute_dates(trading_dates: List[str], num_processes: int) -> List[tuple]:
    """
    Distribute trading dates across processes.

    Args:
        trading_dates: List of trading dates in YYYYMMDD format
        num_processes: Number of processes to distribute work across

    Returns:
        List of tuples containing (start_date, end_date, limit, dry_run) for each process
    """
    if not trading_dates:
        return []

    # Calculate chunk size
    chunk_size = max(1, len(trading_dates) // num_processes)

    # Distribute dates
    chunks = []
    for i in range(0, len(trading_dates), chunk_size):
        chunk = trading_dates[i:i + chunk_size]
        if chunk:
            start_date = chunk[-1]
            end_date = chunk[0]
            limit = len(chunk)
            # dry_run=True for safety
            chunks.append((start_date, end_date, limit, True))

    return chunks


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Maintain TickerDailyInfo collection by removing duplicates')
    parser.add_argument('--start-date', type=str,
                        help='Start date in YYYYMMDD format (default: latest available)')
    parser.add_argument('--end-date', type=str,
                        help='End date in YYYYMMDD format (default: latest available)')
    parser.add_argument(
        '--limit', type=int, help='Maximum number of trading dates to process (default: all)')
    parser.add_argument('--dry-run', action='store_true',
                        default=True, help='Dry run mode (default: True)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually execute the changes (overrides --dry-run)')
    parser.add_argument('--processes', type=int, default=None,
                        help='Number of processes to use (default: CPU count)')

    args = parser.parse_args()

    # Determine if this is a dry run
    dry_run = not args.execute

    if dry_run:
        _logger.info('Running in DRY RUN mode - no changes will be made')
    else:
        _logger.warning(
            'Running in EXECUTE mode - changes will be made to the database')

    # Get trading dates first
    maintainer = TickerDailyInfoMaintainer()
    trading_dates = maintainer.get_trading_dates_backwards(
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit
    )
    disconnect()
    if not trading_dates:
        _logger.error('No trading dates found to process')
        return 1

    _logger.info(f'Found {len(trading_dates)} trading dates to process')

    # Determine number of processes
    num_processes = args.processes or os.cpu_count() or 1
    _logger.info(f'Using {num_processes} processes')

    # Distribute dates across processes
    date_chunks = distribute_dates(trading_dates, num_processes)
    _logger.info(f'Distributed dates into {len(date_chunks)} chunks')

    # Update dry_run parameter in chunks
    date_chunks = [(start_date, end_date, limit, dry_run)
                   for start_date, end_date, limit, _ in date_chunks]

    # Process using multiprocessing pool
    try:
        with Pool(processes=num_processes) as pool:
            results = pool.starmap(do_maintain, date_chunks)

        # Check results
        failed_processes = sum(1 for result in results if result != 0)
        if failed_processes > 0:
            _logger.error(f'{failed_processes} processes failed')
            return 1
        else:
            _logger.info('All processes completed successfully')
            return 0

    except Exception as e:
        _logger.error(f'Error in process pool: {e}')
        return 1


if __name__ == '__main__':
    exit(main())
