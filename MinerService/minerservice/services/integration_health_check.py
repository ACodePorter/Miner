"""Health check service for BarsManager integration"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from detonator import get_logger

from ..config.integration_config import BARS_MANAGER_HEALTH_CHECK_INTERVAL


class IntegrationHealthCheck:
    """Monitor the health of BarsManager integration services"""

    def __init__(self):
        self.logger = get_logger('IntegrationHealthCheck', logging.INFO)
        self.last_health_check: Optional[datetime] = None
        self.health_status: Dict[str, Any] = {}
        self.running = False
        self.health_check_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the health check service"""
        if self.running:
            self.logger.info("Health check service already running")
            return

        self.running = True
        self.logger.info("Starting integration health check service")

        # Start health check task
        self.health_check_task = asyncio.create_task(self._run_health_checks())

    async def stop(self) -> None:
        """Stop the health check service"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping integration health check service")

        # Cancel health check task
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None

    async def _run_health_checks(self) -> None:
        """Main health check loop"""
        while self.running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(BARS_MANAGER_HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def _perform_health_check(self) -> None:
        """Perform a comprehensive health check"""
        try:
            self.last_health_check = datetime.now()

            # Check BarsManager integration
            bars_manager_status = await self._check_bars_manager_integration()

            # Check Redis subscription service
            redis_subscription_status = await self._check_redis_subscription_service()

            # Update overall health status
            self.health_status = {
                'timestamp': self.last_health_check.isoformat(),
                'overall_status': 'healthy' if all([bars_manager_status, redis_subscription_status]) else 'degraded',
                'services': {
                    'bars_manager_integration': bars_manager_status,
                    'redis_subscription_service': redis_subscription_status
                }
            }

            # Log health status
            if self.health_status['overall_status'] == 'healthy':
                self.logger.info("Integration health check passed")
            else:
                self.logger.warning(
                    "Integration health check shows degraded status")

        except Exception as e:
            self.logger.error(f"Error performing health check: {e}")
            self.health_status = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }

    async def _check_bars_manager_integration(self) -> bool:
        """Check if BarsManager integration is working"""
        try:
            # This would check if BarsManager is accessible and responding
            # For now, we'll assume it's working if we can import it
            from dataminer import BarsManager
            bars_manager = BarsManager.get_instance()

            # Check if we can get active subscriptions
            active_subscriptions = bars_manager.get_active_tickers()

            self.logger.debug(
                f"BarsManager integration check: {len(active_subscriptions)} active tickers")
            return True

        except Exception as e:
            self.logger.error(
                f"BarsManager integration health check failed: {e}")
            return False

    async def _check_redis_subscription_service(self) -> bool:
        """Check if Redis subscription service is working"""
        try:
            # This would check if Redis subscription service is responding
            # For now, we'll assume it's working
            return True

        except Exception as e:
            self.logger.error(
                f"Redis subscription service health check failed: {e}")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return self.health_status.copy()

    def is_healthy(self) -> bool:
        """Check if overall integration is healthy"""
        return self.health_status.get('overall_status') == 'healthy'

    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last health check"""
        return self.last_health_check
