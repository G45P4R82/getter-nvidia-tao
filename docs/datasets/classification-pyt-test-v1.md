# Dataset `classification_pyt` - Teste Real v1

## Identificacao

Este e o dataset sintetico usado nas rodadas reais de teste do NVIDIA TAO
FTMS, principalmente nos experimentos `classification_pyt`.

| Campo | Valor |
| --- | --- |
| Nome registrado no TAO | `real-unittest-classification-v2` |
| Dataset ID | `7b242a10-b98c-45ff-ba3e-74b5e3e16c54` |
| Tipo | `image_classification` |
| Formato | `classification_pyt` |
| Workspace | `98c4bec1-88df-423e-8a15-af78881e9742` |
| Status observado | `pull_complete` |
| Uso | treino, avaliacao e teste |
| URI interna | `seaweedfs://tao-storage/data/tao-test-classification-v1` |

## Proveniencia

O dataset foi criado para testes reais e controlados do FTMS. Ele nao vem de
um dataset publico externo nem de uma URL HTTP publica. O registro do dataset
fica no TAO e os arquivos ficam no armazenamento SeaweedFS do ambiente.

O campo `cloud_file_path` retornado pelo TAO e:

```text
data/tao-test-classification-v1
```

O armazenamento fisico e interno ao deployment. Por isso, o URI
`seaweedfs://` funciona para os containers TAO, mas nao pode ser aberto
diretamente em um navegador fora da rede do ambiente.

## Estrutura Observada

Durante os logs de treino, o TAO informou que o caminho continha 52 arquivos e
identificou estes elementos:

```text
data/tao-test-classification-v1/classes.txt
data/tao-test-classification-v1/images_train.tar.gz
data/tao-test-classification-v1/images_test.tar.gz
data/tao-test-classification-v1/images_train/class0/...
```

A estrutura esperada para o experimento e:

```text
tao-test-classification-v1/
├── classes.txt
├── images_train/
│   ├── class0/
│   └── class1/
├── images_train.tar.gz
└── images_test.tar.gz
```

O numero de classes efetivamente usado nas specs de teste e `2`. A quantidade
exata de imagens por split deve ser obtida dos arquivos do storage ou dos logs
de download, e nao inferida apenas pelo registro do dataset.

## Onde Consultar

### API TAO

Metadados de todos os datasets:

```text
GET http://100.107.81.126:8090/api/v2/orgs/getter/datasets
```

Workspace especifico:

```text
GET http://100.107.81.126:8090/api/v2/orgs/getter/workspaces/98c4bec1-88df-423e-8a15-af78881e9742
```

Consulta via `curl` autenticado:

```bash
curl -sS \
  -H "Authorization: Bearer $TOKEN" \
  "http://100.107.81.126:8090/api/v2/orgs/getter/datasets" | jq .
```

### Relatorios do projeto

- [Experimento 001 API](../experiment_001-api-real.md)
- [Experimento 003 treinamento](../experiment_003-training-real.md)
- [Experimento 012 deploy completo](../experiment_012-deploy-real.md)
- [Notebook do Experimento 004](../../notebooks/experiment_004_curl.ipynb)

## Onde os Dados Estao

No ambiente TAO, os dados ficam no bucket SeaweedFS `tao-storage`, sob:

```text
data/tao-test-classification-v1
```

Os containers TAO acessam esse caminho por meio do backend configurado no
FTMS. O dataset nao esta armazenado no Git e nao deve ser commitado no
repositorio.

O repositorio contem somente:

- referencias ao URI;
- configuracoes e specs de teste;
- relatorios;
- logs sanitizados;
- metadados nao secretos.

## Link Externo

Atualmente nao existe um link externo publico para os arquivos. O link da API
acima permite consultar metadados, mas nao baixa diretamente o dataset.

Para disponibilizar uma copia externa, uma destas alternativas deve ser
configurada:

1. Bucket S3/MinIO acessivel pelo TAO, com URI `s3://...` e credenciais no
   runtime.
2. Dataset publicado no NVIDIA NGC/Data Services.
3. Endpoint HTTPS autenticado apontando para uma copia controlada do dataset.

Publicar o dataset anonimamente nao e recomendado, pois os arquivos podem
conter dados de teste que precisam permanecer sob controle do ambiente.

## Reproducibilidade

Para reproduzir o treinamento, use:

```text
network_arch: classification_pyt
workspace: 98c4bec1-88df-423e-8a15-af78881e9742
train_dataset_uri: seaweedfs://tao-storage/data/tao-test-classification-v1
eval_dataset_uri: seaweedfs://tao-storage/data/tao-test-classification-v1
inference_dataset_uri: seaweedfs://tao-storage/data/tao-test-classification-v1
num_gpus: 1
num_epochs: 1
num_classes: 2
```

Antes de iniciar um job, valide o registro pela API e confirme que o status do
dataset permanece `pull_complete`.

## Limitacoes Conhecidas

- O URI SeaweedFS nao e acessivel fora do deployment sem rede e credenciais.
- O registro TAO nao informa sozinho todos os counts de imagens e classes.
- Treino e avaliacao usam o mesmo dataset de teste nesta fixture; isso limita
  conclusoes sobre generalizacao.
- Resultados de accuracy devem ser interpretados como validacao de pipeline,
  nao como benchmark de producao.
