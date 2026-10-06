#!/bin/sh
set -eu
# Targets são endereços, nunca comandos. Permite vários hosts separados por vírgula.
write_targets() {
    vlan="$1"; addresses="$2"
    case "$addresses" in ''|,*|*,|*,,*|*[!a-zA-Z0-9.:,_\[\]-]*) echo "Target inválido para VLAN $vlan" >&2; exit 1 ;; esac
    printf '[{"targets":[' > "/targets/vlan$vlan.json.tmp"
    separator=''
    old_ifs="$IFS"; IFS=','
    for address in $addresses; do
        case "$address" in *:*) ;; *) echo 'Informe hostname/IP:porta' >&2; exit 1 ;; esac
        printf '%s"%s"' "$separator" "$address" >> "/targets/vlan$vlan.json.tmp"
        separator=','
    done
    IFS="$old_ifs"
    printf '],"labels":{"vlan":"%s"}}]\n' "$vlan" >> "/targets/vlan$vlan.json.tmp"
    chmod 644 "/targets/vlan$vlan.json.tmp"
    mv "/targets/vlan$vlan.json.tmp" "/targets/vlan$vlan.json"
}
write_targets 10 "$PROMETHEUS_TARGET_VLAN10"
write_targets 20 "$PROMETHEUS_TARGET_VLAN20"
write_targets 40 "$PROMETHEUS_TARGET_VLAN40"
