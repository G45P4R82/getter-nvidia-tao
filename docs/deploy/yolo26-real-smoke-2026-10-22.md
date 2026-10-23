# YOLO26 real smoke test - 2026-10-22

## Ambiente

- Host: `100.107.81.126`
- GPU: NVIDIA GeForce RTX 5090
- Ultralytics: `8.4.183`
- Arquitetura: `yolo26n`
- Adapter: `tao-ultralytics-adapter:local`
- Contexto TAO: workspace `98c4bec1-88df-423e-8a15-af78881e9742`

## Dataset

Foi criado um dataset YOLO sintético pequeno para validar a integração:

- 6 imagens de treino.
- 2 imagens de validação.
- 1 classe: `object`.
- Dataset montado em `/shared-storage/datasets/yolo26-smoke`.
- `data.yaml`, `images/` e `labels/` no formato Ultralytics.

## Jobs

| Etapa | Job | Resultado |
| --- | --- | --- |
| Treino | `ea841930-5253-4f12-8abe-074f970dfa53` | `done` |
| Avaliação | `f29319b0-2630-41a9-a1c6-1ac01468f4f4` | `done` |
| Exportação ONNX | `d1836b33-3525-43d3-b5b8-7fa3f274c294` | `done` |

Modelo registrado:

```text
model_name=yolo26-smoke
version=v1
architecture=yolo26n
artifact=/shared-storage/models/yolo26/yolo26-smoke/best.pt
```

Métricas da avaliação:

```text
precision: 0.0281690141
recall: 1.0
mAP50: 0.2211111111
mAP50-95: 0.1082444444
```

A inferência também foi executada em uma imagem de validação e gravou o
resultado em:

`/shared-storage/models/yolo26/yolo26-smoke/inference/latest`

## Conclusão

O caminho TAO + contexto de workspace/dataset + adapter Ultralytics + YOLO26
funcionou com GPU real. O dataset é apenas um smoke test sintético; as métricas
não representam qualidade de produção.

Evidências copiadas para o repositório:

- `docs/deploy/yolo26-models-remote.json`
- `docs/deploy/yolo26-jobs-remote.json`
