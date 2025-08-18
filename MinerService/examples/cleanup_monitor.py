#!/usr/bin/env python3
"""
Monitor and test WebSocket cleanup process
"""

import asyncio
import json
import time
from typing import Any, Dict, List

import aiohttp


class CleanupMonitor:
    """Monitor WebSocket cleanup process"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_websocket_status(self) -> Dict[str, Any]:
        """Get current WebSocket status"""
        try:
            async with self.session.get(f"{self.base_url}/api/websocket/status") as response:
                return await response.json()
        except Exception as e:
            return {'error': f'Failed to get status: {e}'}

    async def get_rooms(self) -> Dict[str, Any]:
        """Get current rooms"""
        try:
            async with self.session.get(f"{self.base_url}/api/websocket/rooms") as response:
                return await response.json()
        except Exception as e:
            return {'error': f'Failed to get rooms: {e}'}

    async def get_connections(self) -> Dict[str, Any]:
        """Get current connections"""
        try:
            async with self.session.get(f"{self.base_url}/api/websocket/connections") as response:
                return await response.json()
        except Exception as e:
            return {'error': f'Failed to get connections: {e}'}

    async def trigger_cleanup(self) -> Dict[str, Any]:
        """Trigger manual cleanup"""
        try:
            async with self.session.post(f"{self.base_url}/api/websocket/cleanup_disconnected") as response:
                return await response.json()
        except Exception as e:
            return {'error': f'Failed to trigger cleanup: {e}'}

    async def monitor_cleanup(self, duration: int = 60, interval: int = 5) -> None:
        """Monitor cleanup process over time"""
        print(
            f"🔍 Monitoring cleanup process for {duration} seconds (every {interval}s)")
        print("=" * 80)

        start_time = time.time()
        iteration = 0

        while time.time() - start_time < duration:
            iteration += 1
            current_time = time.time() - start_time

            print(f"\n📊 Iteration {iteration} (t={current_time:.1f}s)")
            print("-" * 40)

            # Get current status
            status = await self.get_websocket_status()
            if 'error' in status:
                print(f"❌ Status error: {status['error']}")
                continue

            # Get rooms
            rooms = await self.get_rooms()
            if 'error' in rooms:
                print(f"❌ Rooms error: {rooms['error']}")
                continue

            # Get connections
            connections = await self.get_connections()
            if 'error' in connections:
                print(f"❌ Connections error: {connections['error']}")
                continue

            # Display current state
            self._display_status(status, rooms, connections)

            # Wait for next iteration
            await asyncio.sleep(interval)

        print("\n" + "=" * 80)
        print("✅ Monitoring completed")

    def _display_status(self, status: Dict[str, Any], rooms: Dict[str, Any], connections: Dict[str, Any]) -> None:
        """Display current status in a readable format"""
        try:
            # Process info
            process = status.get('process', {})
            print(f"🖥️  Process: {process.get('process_id', 'N/A')[:8]}...")
            print(
                f"   Local connections: {process.get('local_connections', 0)}")
            print(
                f"   Total connections: {process.get('total_connections', 0)}")
            print(f"   Running: {process.get('running', False)}")

            # Room manager info
            room_manager = status.get('room_manager', {})
            if room_manager:
                print(f"🏠 Room Manager:")
                print(f"   Local rooms: {room_manager.get('local_rooms', 0)}")
                print(
                    f"   Local clients: {room_manager.get('local_clients', 0)}")

                # Show room details
                room_details = room_manager.get('room_details', {})
                if room_details:
                    print(f"   Room details:")
                    for room_id, details in room_details.items():
                        client_count = details.get('client_count', 0)
                        metadata = details.get('metadata', {})
                        print(
                            f"     {room_id}: {client_count} clients {metadata}")

            # Redis subscription service
            redis_service = status.get('redis_subscription_service', {})
            if redis_service:
                print(f"📡 Redis Service:")
                print(f"   Running: {redis_service.get('running', False)}")
                print(
                    f"   Quote subscriptions: {len(redis_service.get('active_quote_subscriptions', []))}")
                print(
                    f"   Bar subscriptions: {len(redis_service.get('active_bar_subscriptions', []))}")

            # Rooms
            rooms_list = rooms.get('rooms', [])
            print(f"🏠 Active Rooms: {len(rooms_list)}")
            for room in rooms_list[:5]:  # Show first 5 rooms
                room_id = room.get('room_id', 'N/A')
                client_count = room.get('client_count', 0)
                last_activity = room.get('last_activity', 'N/A')
                print(
                    f"   {room_id}: {client_count} clients (last: {last_activity[:19]})")

            if len(rooms_list) > 5:
                print(f"   ... and {len(rooms_list) - 5} more rooms")

            # Connections
            connections_list = connections.get('connections', [])
            print(f"🔌 Active Connections: {len(connections_list)}")

        except Exception as e:
            print(f"❌ Error displaying status: {e}")

    async def test_cleanup_cycle(self) -> None:
        """Test a complete cleanup cycle"""
        print("🧪 Testing cleanup cycle")
        print("=" * 50)

        # Get initial state
        print("📊 Initial state:")
        initial_status = await self.get_websocket_status()
        initial_rooms = await self.get_rooms()
        initial_connections = await self.get_connections()

        self._display_status(
            initial_status, initial_rooms, initial_connections)

        # Trigger cleanup
        print("\n🧹 Triggering cleanup...")
        cleanup_result = await self.trigger_cleanup()

        if 'error' in cleanup_result:
            print(f"❌ Cleanup failed: {cleanup_result['error']}")
            return

        print("✅ Cleanup completed")

        # Show cleanup summary
        summary = cleanup_result.get('cleanup_summary', {})
        connections_removed = summary.get('connections_removed', 0)
        rooms_affected = summary.get('rooms_affected', 0)

        print(f"📈 Cleanup Summary:")
        print(f"   Connections removed: {connections_removed}")
        print(f"   Rooms affected: {rooms_affected}")

        # Get final state
        print("\n📊 Final state:")
        final_status = await self.get_websocket_status()
        final_rooms = await self.get_rooms()
        final_connections = await self.get_connections()

        self._display_status(final_status, final_rooms, final_connections)

        # Show changes
        print("\n🔄 Changes:")
        initial_total = initial_status.get(
            'process', {}).get('total_connections', 0)
        final_total = final_status.get(
            'process', {}).get('total_connections', 0)
        print(
            f"   Total connections: {initial_total} → {final_total} ({final_total - initial_total:+d})")

        initial_rooms_count = len(initial_rooms.get('rooms', []))
        final_rooms_count = len(final_rooms.get('rooms', []))
        print(
            f"   Total rooms: {initial_rooms_count} → {final_rooms_count} ({final_rooms_count - initial_rooms_count:+d})")


async def main():
    """Main function"""
    print("🔍 WebSocket Cleanup Monitor")
    print("=" * 50)

    async with CleanupMonitor() as monitor:
        # Test cleanup cycle
        await monitor.test_cleanup_cycle()

        print("\n" + "=" * 50)

        # Monitor for a while
        await monitor.monitor_cleanup(duration=30, interval=5)


if __name__ == "__main__":
    asyncio.run(main())
