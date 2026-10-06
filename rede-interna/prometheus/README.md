# Prometheus e exporters

O Prometheus pertence à VLAN 30. Ele consulta `/metrics` nos exporters; os exporters
não enviam dados espontaneamente. O volume `prometheus_data` preserva o histórico.
O serviço `prometheus-targets` termina após gerar arquivos JSON para o mecanismo
nativo `file_sd_configs`. Não é um daemon nem precisa acessar qualquer rede.

## Laboratório local

`subir-local/local.ps1 up` inicia exporters na DMZ/VLAN 10, Dados/VLAN 20 e uma
simulação de Endpoints/VLAN 40. A bridge interna `hospital-monitoring-transit`
conecta exclusivamente o Prometheus e esses exporters. Nenhum deles acessa `db_app`.
O Prometheus também fica na bridge VLAN 30; não participa da bridge VLAN 20.

Os três exporters compartilham a mesma VM Linux do Docker Desktop. Eles validam
coleta e comunicação; não representam três máquinas físicas nem monitoram o Windows.
As raízes dos hosts não são montadas no laboratório. Para conferir:

```powershell
./subir-local/local.ps1 prometheus-test
```

Interface: http://localhost:9090/targets. Exporters locais ficam restritos ao
loopback (Dados 9100, DMZ 19110); o endpoint simulado não publica porta.

## Duas máquinas reais

1. Prepare os arquivos de ambiente individuais em `subir-servidor/DMZ` e
   `subir-servidor/Rede Interna`.
2. Na DMZ, configure `NODE_EXPORTER_BIND_IP` com a interface VLAN 10. Na Rede
   Interna, use a interface VLAN 20. Use `DMZ_NODE_EXPORTER_PORT=9100` na DMZ e
   `NODE_EXPORTER_PORT=9100` na Rede Interna.
3. Na Rede Interna, configure `PROMETHEUS_TARGET_VLAN10`, `PROMETHEUS_TARGET_VLAN20`
   e `PROMETHEUS_TARGET_VLAN40` com IP/FQDN:porta alcançáveis. Para múltiplas
   estações, separe os endereços por vírgula, sem espaços.
4. No pfSense e firewall de cada host, permita TCP 9100 exclusivamente da origem
   efetivamente usada pelo Prometheus/VLAN 30 para os exporters. Confirme o IP de
   origem após NAT do Docker: a bridge não atribui uma VLAN física ao host.
   Configure rota/interface de saída ou SNAT se necessário. Não libere para a Internet.
5. Instale um exporter por estação física da VLAN 40. Para Linux, Node Exporter;
   para Windows, Windows Exporter e porta configurada (normalmente 9182). Ajuste
   os targets. O serviço de endpoints do Compose local não é usado no servidor.
6. Publique 9090 somente na interface administrativa desejada e restrinja o acesso
   por firewall/VPN. Prometheus não tem autenticação/TLS configurados nesta etapa.
7. Execute separadamente `bash "subir-servidor/Rede Interna/subir.sh" up` e
   `bash subir-servidor/DMZ/subir.sh up`. Confira todos os targets em UP após preparar
   as estações. Não existe bridge de monitoramento compartilhada entre servidores.

Os mounts `/proc`, `/sys` e raiz somente leitura nos Compose dos servidores são
para hosts Linux. Confirme as métricas de filesystem e CPU contra o próprio host
na homologação. Os sistemas operacionais reais ainda precisam ser definidos.

Referências: https://prometheus.io/docs/guides/node-exporter/ e
https://prometheus.io/docs/guides/file-sd/.
