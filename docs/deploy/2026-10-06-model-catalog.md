# Deploy do catalogo de modelos - 2026-10-06

## Objetivo

Publicar as novas ferramentas de modelos versionados do MCP e executar o
experimento 001 pela API REST do TAO na maquina de treinamento.

## Alteracoes prontas localmente

- Catalogo persistente em `~/.local/state/tao-mcp/models.json`.
- Registro de jobs concluidos como versoes de modelo.
- Listagem de modelos e versoes.
- Selecao de `model_name` e `model_version` para jobs de avaliacao, exportacao,
  TensorRT e inferencia.

## Tentativas de acesso remoto

O inventario Ansible define `100.107.81.126`. A documentacao de execucao
anterior registra `100.79.125.82`. Foram testados ambos, sem alterar nenhum
servico:

| Host | SSH | REST `:8090` |
| --- | --- | --- |
| `100.107.81.126` | timeout | timeout |
| `100.79.125.82` | timeout | timeout |

O deploy nao foi realizado porque a maquina nao estava acessivel a partir do
ambiente atual. Nenhum job TAO foi submetido nesta tentativa.

## Validacao local

Executado com `mcp/.venv/bin/python`:

```text
7 testes passaram
3 testes reais foram ignorados por falta de execucao TAO
```

Tambem passaram a compilacao Python e `git diff --check`.

## Deploy posterior

O host correto foi confirmado como `getter@100.93.189.81`. O codigo do MCP foi
copiado para `/home/getter/tao-ftms/mcp`, e `model_catalog.py` foi compilado com
sucesso no host remoto.

A validacao REST remota passou para:

- health e readiness;
- login NGC;
- listagem de workspace;
- schemas de `train`, `evaluate`, `export`, `gen_trt_engine` e `inference`.

O endpoint de tipos de GPU retornou `404` nesta versao do FTMS, sem impedir a
validacao dos schemas.

O pipeline ainda nao foi iniciado porque o job antigo
`b4e01fe9-dc0c-4bfa-9ef4-f728bf7499db` permanece em `Started` e a maquina possui
uma GPU configurada. O cancelamento desse job requer autorizacao explicita.

## Execucao do experimento 001

Com autorizacao, foi tentado cancelar o job antigo via API, mas o FTMS retornou
`404 job status not found`. O runner REST submeteu o job
`c165595c-06d6-4394-aad4-c045c34af9b3`, que permaneceu `Pending` porque o
scheduler ainda considerava a GPU ocupada. Esse job foi cancelado antes do
restart.

Foi executado restart dos containers Compose sem apagar volumes. O health voltou
com `liveness` e `readiness`, mas o login NGC passou a falhar porque o host nao
consegue resolver `api.ngc.nvidia.com`. Sem autenticacao, as etapas de
treinamento, registro, avaliacao, exportacao, TensorRT e inferencia nao puderam
ser concluidas.

O log completo do runner esta em:

`docs/deploy/experiment_001-rest-2026-10-06.log`

## Teste das chaves e rede

Executado no host `100.93.189.81` sem exibir os valores das chaves:

- `ngc_api_key` contra `https://api.ngc.nvidia.com/v2/users/me`, usando IP
  fixado para contornar DNS: `HTTP 200`.
- `ptm_api_key` contra o mesmo endpoint: `HTTP 401`, o que e esperado se essa
  chave for exclusiva para PTM e nao uma credencial de usuario NGC.
- Login TAO em `127.0.0.1:8090/api/v2/login` com `ngc_api_key`: `HTTP 401`.

O corpo do erro do TAO identifica `NameResolutionError` para
`api.ngc.nvidia.com`. O container `tao_api_app` tambem nao resolve esse nome.

Conclusao: a chave pessoal NGC e valida; o bloqueio restante e DNS dentro do
host/container. A chave nao precisa ser substituida.

## Bypass DNS temporario

Em `100.93.189.81`, consultas diretas para `8.8.8.8:53` e `8.8.4.4:53`
expiraram. Para o teste, foi adicionado temporariamente nos containers
`tao_api_app` e `tao_api_workflow`:

```text
44.250.73.17 api.ngc.nvidia.com
```

Com esse bypass, o login em `/api/v2/login` retornou `HTTP 200` e token valido.
Isso confirma definitivamente que o problema e a resolucao DNS local dos
containers. A entrada e efemera e sera perdida quando os containers forem
recriados ou reiniciados.

## Resultado final da tentativa de treinamento

O workflow foi recriado com `gpus: all` e confirmou acesso a uma `NVIDIA
GeForce RTX 5090` dentro do container. Mesmo assim, o scheduler informou zero
GPUs disponiveis porque havia um processo externo usando a unica GPU:

```text
/home/vst/vst_release/launch_vst - 500 MiB
```

Esse servico nao foi interrompido por pertencer a outra aplicacao. O job de
treinamento `bc1b932e-32c9-40bf-8a20-a59e5e1a9acb` permaneceu `Pending` e foi
cancelado. Nenhuma avaliacao, registro de modelo, exportacao, TensorRT ou
inferencia foi executada.

## Execucao concluida

Depois da liberacao da GPU, o experimento 001 foi executado integralmente via
REST no host `100.93.189.81`:

| Etapa | Job | Resultado |
| --- | --- | --- |
| Treinamento | `9b181c12-352d-43e2-a935-8c7a81ba5544` | `Done` |
| Avaliacao | `535ec84c-554a-4308-b29b-5720ba0176d7` | `Done` |
| Exportacao | `c200acb2-7fbe-4979-b42a-ba2883a4fe1e` | `Done` |
| TensorRT | `d92f8a8d-24db-42d7-a76b-ecfc1304a63b` | `Done` |
| Inferencia | `1517a7bf-9890-40de-8300-487710033621` | `Done` |

O treinamento foi registrado no catalogo remoto como:

```text
model_name=classification_pyt
version=v1
job_id=9b181c12-352d-43e2-a935-8c7a81ba5544
```

O log e o catalogo resultantes foram copiados para este repositorio:

- `docs/deploy/experiment_001-rest-2026-10-06.log`
- `docs/deploy/model-catalog-remote.json`

## Proximo passo

Quando a conectividade com a maquina for restabelecida, publicar o MCP,
instalar suas dependencias no host remoto, executar o teste de contrato REST e
rodar o pipeline completo: `train`, registro `v1`, `evaluate`, `export`,
`gen_trt_engine` e `inference`.
