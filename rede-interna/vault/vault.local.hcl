# Somente laboratório. Preserva Shamir, sem migrar o seal do volume existente.
ui = true
disable_mlock = true
disable_clustering = true
api_addr = "http://hashicorp-vault:8200"
storage "file" {
  path = "/vault/file"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}
