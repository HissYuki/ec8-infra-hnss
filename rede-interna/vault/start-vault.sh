#!/bin/sh
set -eu
# status=2 significa selado OU não inicializado. Nunca inicialize por esse código.
# Init/unseal são operações administrativas; não exponha chaves/token nos logs.
exec docker-entrypoint.sh server
