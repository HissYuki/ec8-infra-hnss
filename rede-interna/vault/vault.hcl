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
    token           = "hvs.CAESIJYrPwNOf3tsqxS5kVS3bUnfHHINnqTfm-lOykyZdysTGh4KHGh2cy5SQ2NTTkdxeFJ1dlF1TFo4NVFjR2QxQ0k"
}