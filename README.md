# Dashboard Gerencial de Obras - Backend

Backend FastAPI para consumir consultas do Sankhya, padronizar os dados com Polars e disponibilizar endpoints para o dashboard gerencial de obras.

## Stack

- FastAPI
- HTTPX
- Polars
- MongoDB (Motor)
- APScheduler
- Pydantic Settings

## Requisitos

- Python 3.12+
- MongoDB local ou remoto
- Credenciais válidas da API Sankhya

## Configuração

1. Crie o ambiente virtual:

```bash
python -m venv .venv
```

2. Ative o ambiente:

Windows:

```bash
.venv\Scripts\activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Copie `.env.example` para `.env` e preencha as credenciais.

5. Execute:

```bash
uvicorn app.main:app --reload
```

Documentação Swagger:

```text
http://127.0.0.1:8000/docs
```

## Endpoints principais

- `POST /api/v1/sankhya/auth/token`
- `POST /api/v1/sankhya/queries/{query_code}`
- `GET /api/v1/sankhya/queries`
- `POST /api/v1/dashboard/raw`
- `GET /api/v1/health`

## Consultas disponíveis

- `pagamentos`
- `notas`
- `itens_notas`
- `itens_remessas`
- `compras`
- `remessas`
- `pagamento_interno_obras`

## Filtro global

Todas as consultas exigem `codproj`.

Exemplo:

```json
{
  "codproj": 20000000,
  "dtneg_inicial": "2026-01-01",
  "dtneg_final": "2026-07-21",
  "nunota": null
}
```

## Observação importante

O parser de resposta do `DbExplorerSP.executeQuery` foi preparado para os formatos mais comuns do Sankhya. Caso o tenant retorne estrutura diferente, ajuste apenas `app/services/sankhya_query_service.py`, método `_extract_rows`.

## Primeiro teste no PyCharm

O ZIP já inclui um `.env` com valores vazios para as credenciais do Sankhya. Preencha:

- `SANKHYA_X_TOKEN`
- `SANKHYA_CLIENT_ID`
- `SANKHYA_CLIENT_SECRET`
- `API_KEY`

Depois configure o interpretador `.venv` no PyCharm e execute `app/main.py` com Uvicorn, ou use o terminal integrado.
