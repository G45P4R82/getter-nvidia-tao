# Experimento YOLO26 do cientista - 2026-10-22

## Fluxo executado

O notebook foi executado localmente usando:

- TAO API: `http://100.107.81.126:8090`
- Adapter: `http://100.107.81.126:9200`
- SeaweedFS: `http://100.107.81.126:18333`
- Workspace: `98c4bec1-88df-423e-8a15-af78881e9742`

O notebook validou o dataset, enviou 17 objetos ao bucket `tao-storage`,
registrou o dataset no TAO e submeteu o treino com todos os parâmetros
Ultralytics.

Dataset TAO criado:

```text
id=753b27ca-cfca-4d0e-993e-863d0984fb82
uri=seaweedfs://tao-storage/data/yolo26-scientist-5b8590d5
```

## Jobs

| Etapa | Job | Status |
| --- | --- | --- |
| Treino | `7150c4c0-c87b-4c50-a65c-98590af6aa16` | `done` |
| Avaliação | `eaef76ff-e364-475d-97e6-2fd6d8482b78` | `done` |
| Exportação ONNX | `4cf705e2-bf3f-4cb1-b396-ddd2631b4f86` | `done` |

## Parâmetros enviados

- Arquitetura: `yolo26n`
- Épocas: `1`
- Imagem: `640`
- Batch: `2`
- Patience: `20`
- Device: `0`
- Workers: `1`
- Optimizer: `auto`
- `lr0`: `0.01`
- `weight_decay`: `0.0005`
- AMP: habilitado
- Seed: `42`

## Métricas

- Precision: `0.00905`
- Recall: `1.0`
- mAP50: `0.695`
- mAP50-95: `0.5659`

Artefatos:

- Checkpoint: `/shared-storage/models/yolo26/yolo26-scientist-5b8590d5/best.pt`
- ONNX: `/shared-storage/models/yolo26/yolo26-scientist-5b8590d5/best.onnx`

Notebook executado:

`docs/deploy/experiment_013_yolo26_executed.ipynb`

## Execucao posterior confirmada

Uma nova execução do notebook, com retry de conexão durante o polling, concluiu
o treino real com:

- Dataset TAO: `0fc83b53-b695-4789-8a57-f3e0a764abf6`.
- URI: `seaweedfs://tao-storage/data/yolo26-scientist-34f5a85f`.
- Job de treino: `7dcad886-6531-460d-b963-87002fc5390c`.
- Modelo: `yolo26-scientist-34f5a85f:v2`.
- Status: `done`.
- Artefato: `/shared-storage/models/yolo26/yolo26-scientist-34f5a85f/best.pt`.

O reset de conexão observado no notebook foi transitório; o job continuou no
servidor e terminou normalmente. O notebook agora repete requisições `GET` de
status com backoff antes de falhar.
