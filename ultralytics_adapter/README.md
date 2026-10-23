# TAO Ultralytics Adapter

Adapter de execução para modelos Ultralytics/YOLO26 controlado junto ao TAO
FTMS. O FTMS continua sendo o plano de controle para autenticação, workspace,
datasets e contexto; este serviço executa o treino, avaliação, exportação e
inferência que não são nativos do catálogo TAO.

## Execução

```bash
pip install -r ultralytics_adapter/requirements.txt
ULTRALYTICS_DATA_ROOT=/shared-storage \
ULTRALYTICS_MODEL_ROOT=/shared-storage/models \
uvicorn ultralytics_adapter.main:app --host 0.0.0.0 --port 9200
```

O dataset deve ser um dataset Ultralytics/YOLO com `data.yaml`, `images/` e
`labels/`. Um request de treino pode carregar o contexto TAO através de
`tao_workspace_id`, `tao_dataset_id` e `dataset_uri`, mas a execução lê o
dataset pelo volume compartilhado.

## Endpoints

- `POST /v1/jobs/train`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs`
- `POST /v1/jobs/{job_id}/evaluate`
- `POST /v1/jobs/{job_id}/export`
- `POST /v1/infer/image`
- `GET /v1/models`

O primeiro smoke test deve usar `architecture: "yolo26n"`, uma GPU e uma
época. A imagem/versão Ultralytics precisa suportar `yolo26n.pt`; o adapter
falha explicitamente se o checkpoint não puder ser resolvido.

`POST /v1/infer/image` retorna o caminho persistido e `image_base64` da imagem
anotada, permitindo que um notebook exiba a inferência sem montar o storage
remoto.
