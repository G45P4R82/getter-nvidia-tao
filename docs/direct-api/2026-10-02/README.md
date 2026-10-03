# Validacao Direta TAO - 2026-10-02

## Resultado

A execucao foi iniciada diretamente na maquina `getter-System-Product-Name`,
fora do GitHub Actions e sem comandos Docker para executar os testes.

- Host: `getter@100.79.125.82`
- TAO endpoint: `http://127.0.0.1:8090`
- Pasta de execucao: `/home/getter/tao-direct-api-2026-10-02`
- Dataset configurado: `seaweedfs://tao-storage/data/tao-test-classification-v1`
- Login FTMS: passou (`HTTP 200`).
- Contrato/API: passou, `6/6` testes.
- Pipeline TAO: bloqueado por job anterior preso em `Started`.
- Job criado nesta tentativa: cancelado enquanto estava `Pending`.
- GPU/job concluido nesta tentativa: nenhum.

## Bloqueio

O primeiro teste falhou com `HTTP 401` porque havia um problema de DNS para
`api.ngc.nvidia.com`. Depois da correcao de DNS e da configuracao correta das
chaves Personal NGC e Legacy PTM, o login passou.

O pipeline posterior encontrou o job anterior
`b4e01fe9-dc0c-4bfa-9ef4-f728bf7499db` em `Started`. O endpoint de cancelamento
retornou `404`, e o novo treino permaneceu `Pending` ate o timeout. Nenhum novo
job deve ser iniciado enquanto esse estado nao for resolvido no FTMS.

Relatorios:

- [Contrato e API](experiment_direct-api-contract.md)
- [Pipeline TAO](experiment_direct-tao-pipeline.md)
- [Status bruto](run-status.txt)

## Conclusao

O acesso SSH, o login FTMS e o contrato da API estao funcionais. O bloqueio
restante e um job TAO antigo preso em `Started`, independente do runner GitHub.
