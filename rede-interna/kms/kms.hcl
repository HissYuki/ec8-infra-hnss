# Transit deve ser habilitado manualmente após inicialização/unseal controlados.
ui = true
disable_mlock = true
disable_clustering = true
api_addr = "http://kms-vault:8200"
storage "file" {
  path = "/vault/file"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}
