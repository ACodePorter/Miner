#!/bin/sh

uvicorn --host 0.0.0.0 --port 8888 --uds /tmp/unicorn.sock --log-level trace minerservice.main:app
