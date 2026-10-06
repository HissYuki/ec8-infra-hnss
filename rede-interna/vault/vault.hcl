ui = true
disable_mlock = true
disable_clustering = true
api_addr = "http://127.0.0.1:8200"

storage "file" {
    path = "/vault/file"
}

listener "tcp" {
    address = "0.0.0.0:8200"
    tls_disable = 1
}

seal "transit" {
    address         = "http://kms-vault:8201"
    disable_renewal = "false"
    key_name        = "autounseal"
    mount_path      = "transit/"
    tls_skip_verify = "true"
    token           = "hvs.CAESIEr9JrqSPHLGYzcypB8rE0yCX4T2LX9SGXVaxqYkTmArGh4KHGh2cy40dDdKcmNlTklKQVFwbnVNOUl0NzJUUzQ"
}