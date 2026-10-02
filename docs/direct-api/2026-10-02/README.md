# Validacao Direta TAO - 2026-10-02

## Resultado

A execucao foi iniciada diretamente na maquina `getter-System-Product-Name`,
fora do GitHub Actions e sem comandos Docker para executar os testes.

- Host: `getter@100.79.125.82`
- TAO endpoint: `http://127.0.0.1:8090`
- Pasta de execucao: `/home/getter/tao-direct-api-2026-10-02`
- Dataset configurado: `seaweedfs://tao-storage/data/tao-test-classification-v1`
- Testes executados: nenhum, porque o setup falhou na autenticacao.
- GPU/job TAO criado: nenhum.

## Bloqueio

O login real do FTMS retornou `HTTP 401` ao usar a credencial NGC local da
maquina. A chave nao foi copiada nem registrada neste repositorio.

Relatorios:

- [Contrato e API](experiment_direct-api-contract.md)
- [Pipeline TAO](experiment_direct-tao-pipeline.md)
- [Status bruto](run-status.txt)

## Conclusao

O acesso SSH e os servicos locais estao acessiveis, mas a credencial NGC
disponivel na maquina nao esta autorizada pelo FTMS/NGC. E necessario atualizar
a credencial local antes de repetir a validacao direta. Esta falha e distinta
da indisponibilidade do runner GitHub.
