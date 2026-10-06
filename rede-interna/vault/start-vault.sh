#!/bin/sh

# Garante que o cliente CLI consulte o Vault local
export VAULT_ADDR="http://127.0.0.1:8200"

# 1. Inicia o servidor do Vault em segundo plano
docker-entrypoint.sh server &
VAULT_PID=$!

echo "Aguardando o servidor Vault subir..."

# 2. Loop de verificação isolando o Exit Code
while true; do
  vault status > /dev/null 2>&1
  STATUS=$?
  
  if [ $STATUS -eq 2 ]; then
    echo "Status 2: Vault detectado como NÃO inicializado."
    break
  elif [ $STATUS -eq 0 ]; then
    echo "Status 0: Vault já se encontra inicializado."
    break
  fi
  
  echo "Aguardando API do Vault... (Status atual: $STATUS)"
  sleep 2
done

# 3. Executa o init caso o status seja 2
if [ $STATUS -eq 2 ]; then
  echo "Realizando vault operator init..."
  # Executa o init. Se falhar, mostrará o erro na tela.
  vault operator init
  
  if [ $? -eq 0 ]; then
    echo "Vault inicializado."
  else
    echo "ERRO no init! Verifique se o kms-vault está acessível e destrancado."
  fi
fi

# 4. Trava o processo no servidor principal para o container não morrer
wait $VAULT_PID