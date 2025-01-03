FROM redis:7.2.0
ENV TZ=America/Toronto
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
COPY redis.conf /usr/local/etc/redis/redis.conf
COPY users.acl /etc/redis/users.acl
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
