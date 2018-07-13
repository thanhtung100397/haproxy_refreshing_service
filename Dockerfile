FROM python:3.7-alpine

ENV CONSUL_SERVER_ADDRESS = '127.0.0.1:8500' \
    CONSUL_SERVICE_NAME='user-management-service' \
    HAPROXY_SOCKET_HOST='127.0.0.1' \
    HAPROXY_SOCKET_PORT=9999 \
    HAPROXY_BACKEND_NAME='user_management_service'

COPY requirements.txt /app/

RUN pip install -r /app/requirements.txt

COPY /src/ /app/src

CMD ['python',
    '${CONSUL_SERVER_ADDRESS}',
    '${CONSUL_SERVICE_NAME}',
    '${HAPROXY_SOCKET_HOST}',
    '${HAPROXY_SOCKET_PORT}',
    '${HAPROXY_BACKEND_NAME}']
