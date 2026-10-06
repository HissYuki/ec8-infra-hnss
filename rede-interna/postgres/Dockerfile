FROM postgres:15-alpine

RUN apk add --no-cache pgbackrest

RUN mkdir -p /var/log/pgbackrest && chown postgres:postgres /var/log/pgbackrest

COPY custom-entrypoint.sh /usr/local/bin/
COPY init-pgbackrest.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/custom-entrypoint.sh /usr/local/bin/init-pgbackrest.sh

ENTRYPOINT ["custom-entrypoint.sh"]

CMD ["postgres"]