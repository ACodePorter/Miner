from detonator import is_in_docker
from celery.schedules import crontab

result_serializer = 'json'

rmq_host = 'rabbitmq' if is_in_docker() else '127.0.0.1'
redis_host = 'redis' if is_in_docker() else '127.0.0.1'

broker_url = f'amqp://miner:12qw@{rmq_host}:5672//'
result_backend = f'redis://miner:12qw@{redis_host}:6379/0'

timezone = 'America/Toronto'

worker_redirect_stdouts = False
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(name)s:%(funcName)s->%(message)s'

broker_connection_retry_on_startup = True

# Beat schedule configuration
beat_schedule = {
    'daily-1630-updates': {
        'task': 'dataminer.tasks.run_daily_updates_task',
        'schedule': crontab(hour=16, minute=30),
        'options': {'expires': 300}  # Task expires after 5 minutes
    }
}
