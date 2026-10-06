#!/bin/sh

docker-entrypoint.sh server &
VAULT_PID=$!
echo "Aguardando o KMS Vault iniciar..."
sleep 5

vault operator unseal fTUyGMckWE7IgHC1qddqVhk77p21t8WtbBhwXTb63O2x
vault operator unseal c+r5X1YSGh/rAnPywoyHK6MkNAz1CD71i7l8GbTyZTgq
vault operator unseal azZn5ALuNtB70RzIIW4rQledqrm+2pByL/H6oVxK7pVX

echo "KMS Vault destrancado!"

wait $VAULT_PID