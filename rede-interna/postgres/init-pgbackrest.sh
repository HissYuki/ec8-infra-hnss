#!/bin/bash

# Fica em loop infinito até que o banco de dados principal aceite conexões TCP locais.
# Isso ignorará as fases de banco de dados temporário.
until su-exec postgres pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -q; do
  sleep 2
done

echo "pgBackRest [Automação]: PostgreSQL online na porta local. Aguardando estabilização do WAL..."
sleep 5

STANZA_NAME=$(grep '\[' /etc/pgbackrest.conf | grep -v 'global' | tr -d '[]' | tr -d '\r')

# Checa se a stanza já existe para não tentar rodar a criação novamente em todo boot do contêiner
if su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=$STANZA_NAME info | grep -q "status: ok"; then
    echo "pgBackRest [Automação]: A stanza $STANZA_NAME já está configurada e saudável. Nenhuma ação necessária."
else
    echo "pgBackRest [Automação]: Configurando o ambiente pela primeira vez para a stanza $STANZA_NAME..."
    
    su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=$STANZA_NAME stanza-create
    su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=$STANZA_NAME check
    su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=$STANZA_NAME backup --type=full
    
    echo "pgBackRest [Automação]: Backup inicial de $STANZA_NAME finalizado com sucesso!"
fi