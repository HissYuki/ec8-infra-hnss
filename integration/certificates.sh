#!/bin/sh
# Exclusivamente certificados de teste local. Nunca distribuir a CA privada.
set -eu
umask 077
cd /certs
if [ -e public.key ] && [ "${1:-}" != '--regenerate' ]; then
    echo 'Certificados locais já existem; nenhuma chave foi substituída.'
    exit 0
fi
openssl req -x509 -newkey rsa:3072 -nodes -days 30 -keyout ca.key -out ca.crt \
  -subj '/CN=Hospital Local CA' -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' 2>/dev/null
for name in backend frontend public; do
    openssl req -newkey rsa:2048 -nodes -keyout "$name.key" -out "$name.csr" -subj "/CN=$name" 2>/dev/null
    case "$name" in
      backend) printf 'subjectAltName=DNS:hospital-backend\nextendedKeyUsage=serverAuth\n' > extensions ;;
      frontend) printf 'extendedKeyUsage=clientAuth\n' > extensions ;;
      public) printf 'subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n' > extensions ;;
    esac
    printf 'keyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n' >> extensions
    openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -days 30 -out "$name.crt" -extfile extensions
done
cp ca.crt backend-ca.crt
cp ca.crt client-ca.crt
# UID 10001 executa Gunicorn; permissões em Linux sem expor chaves a outros UIDs.
chown 10001:10001 backend.key
chmod 644 *.crt
