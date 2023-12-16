from detonator import is_in_docker
result_serializer = 'json'


rmq_host = 'rabbitmq' if is_in_docker() else '127.0.0.1'
redis_host = 'redis' if is_in_docker() else '127.0.0.1'

broker_url = f'amqp://miner:12qw@{rmq_host}:5672//'
result_backend = f'redis://miner:12qw@{redis_host}:6379/0'

timezone = 'Asia/Shanghai'

worker_redirect_stdouts = False
