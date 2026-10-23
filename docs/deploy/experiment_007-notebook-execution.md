# Execucao do Notebook 007

## Resultado

- Host TAO: `100.107.81.126`
- Endpoint usado pelo notebook: tunel SSH para `127.0.0.1:8090`
- Arquitetura: `classification_pyt`
- Workspace: `98c4bec1-88df-423e-8a15-af78881e9742`
- Dataset: `seaweedfs://tao-storage/data/tao-test-classification-v1`
- Contexto: `PASS`
- Base experiments encontrados: `26`
- GPU: `NVIDIA GeForce RTX 5090`

## Job real

- Job ID: `0aed00ba-42c0-4af7-8d67-bbba9cf258db`
- Ação: `train`
- Épocas: `1`
- GPUs: `1`
- Status final: `Done`

Sequência observada pelo notebook:

```text
Pending -> Started -> Running -> Done
```

## Evidências

- Notebook executado: `docs/deploy/experiment_007_executed.ipynb`
- Payload: `notebooks/experiment-007-evidence/train-payload.json`
- Submissão: `notebooks/experiment-007-evidence/train-submitted.json`
- Status final: `notebooks/experiment-007-evidence/train-status.json`

O driver NVIDIA foi corrigido antes da execução instalando o módulo para o
kernel `7.0.0-38-generic`. A validação `nvidia-smi` no host e em container
TAO confirmou a GPU disponível.

## Execucao local confirmada

O notebook foi executado localmente, célula por célula, a partir deste projeto,
acessando diretamente o endpoint Tailscale `http://100.107.81.126:8090`.

- Contexto: `PASS`
- Base experiments: `26`
- Job local: `3fbd14b4-d28d-4829-b0c5-1d9058be91ff`
- Status final: `Done`
- Sequencia: `Pending -> Started -> Running -> Done`

Notebook executado salvo em:

`docs/deploy/experiment_007_executed_latest.ipynb`
