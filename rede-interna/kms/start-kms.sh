#!/bin/sh

docker-entrypoint.sh server &
VAULT_PID=$!
echo "Aguardando o KMS Vault iniciar..."
sleep 5

vault operator unseal ZJyQanZUVwJwxCibO3Jd8e6kBAWXQID4wiXsZXqgqL+A
vault operator unseal VwGDLA5pBaBgEwzNw/iwITJW8wwH0x3fh7Qov98u1s2P
vault operator unseal h6cXzd9l1Hr1xT9O9TFUIDTv6I+wYs4JfvP7yQAObW1O

echo "KMS Vault destrancado!"

wait $VAULT_PID