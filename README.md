# FP Estoque — Depósito de Bebidas

Sistema web completo para o controle interno de estoque do **FP Depósito de Bebidas**, desenvolvido com React, Tailwind CSS, Django REST Framework e PostgreSQL hospedado no Supabase.

## Funcionalidades

- Login JWT, recuperação de senha e perfis Administrador/Operador.
- Cadastro e inativação de usuários, produtos, categorias e fornecedores.
- Produtos com SKU, código de barras, preços, estoque mínimo/máximo, localização e imagem.
- Entradas em rascunho, confirmação, custo médio e cancelamento com estorno.
- Saídas em rascunho, validação de saldo, seleção de lote e consumo FEFO.
- Ajustes positivos/negativos com justificativa e permissão administrativa.
- Lotes, fabricação, validade, alertas e estoque por lote.
- Inventários físicos, divergências e ajustes controlados.
- Histórico imutável de movimentações, estornos e logs de auditoria.
- Dashboard com indicadores e gráficos por período.
- Central de alertas e notificações.
- 18 tipos de relatórios com pré-visualização e exportação PDF/CSV.
- Relatório diário completo, inclusive para dias sem movimentação.
- Swagger/OpenAPI em `/api/docs/`.

## Relatórios

- Relatório diário de movimentações.
- Posição atual e quantidade por produto/lote.
- Estoque baixo, sem estoque, próximos do vencimento e vencidos.
- Entradas e saídas por período.
- Histórico completo, por usuário e por produto.
- Valor total e valor por categoria.
- Entradas por fornecedor.
- Divergências de inventário.
- Produtos com pouca movimentação.

Os relatórios aceitam filtros aplicáveis, permitem pré-visualização e exportam PDF paginado com orientação automática ou CSV em UTF-8.

## Requisitos

- Python 3.12 ou superior.
- Node.js 20 ou superior.
- Projeto PostgreSQL no Supabase.

## Configuração local

Na raiz do repositório:

```cmd
copy .env.example .env
notepad .env
```

Preencha `DATABASE_URL` com a conexão Session Pooler do Supabase. Nunca envie o arquivo `.env` ao GitHub.

### Backend

```cmd
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_admin
python manage.py runserver
```

Backend: `http://127.0.0.1:8000/`  
Swagger: `http://127.0.0.1:8000/api/docs/`  
Admin: `http://127.0.0.1:8000/admin/`

### Frontend

Em outro terminal:

```cmd
cd frontend
npm install
npm run dev
```

Interface: `http://localhost:5173/`

## Dados de exemplo

```cmd
python manage.py seed_example_data
```

O comando cria registros somente para validação do ambiente. Os relatórios sempre consultam os dados persistidos no banco.

## Alertas

```cmd
python manage.py refresh_stock_alerts
```

O prazo de validade é configurável pela chave `expiration_alert_days` na tela **Configurações**.

## Supabase Storage

O bucket `product-images` armazena imagens dos produtos. Para habilitar upload pelo backend, configure somente no `.env` do servidor:

```env
SUPABASE_STORAGE_BUCKET=product-images
SUPABASE_SERVICE_ROLE_KEY=chave_privada_do_servidor
```

A service role nunca deve ser usada no navegador nem versionada.

## Testes

```cmd
cd backend
set USE_SQLITE_FOR_TESTS=true
python manage.py test inventory -v 2
```

Os testes cobrem login e permissões, cadastro, entradas, saídas, estoque negativo, FEFO, cancelamento/estorno, ajustes, alertas, validade, inventário e relatórios.

```cmd
cd frontend
npm install
npm run build
```

## API principal

- `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/forgot-password/` e `/api/auth/reset-password/`.
- `/api/users/`, `/api/products/`, `/api/categories/`, `/api/suppliers/`.
- `/api/lots/`, `/api/entries/`, `/api/outputs/`, `/api/movements/`.
- `/api/adjustments/`, `/api/inventories/`, `/api/alerts/`, `/api/notifications/`.
- `/api/dashboard/`.
- `/api/reports/`, `/api/reports/preview/`, `/api/reports/export.pdf` e `/api/reports/export.csv`.

## Segurança

- Senhas armazenadas pelo hash nativo do Django.
- Autenticação JWT e proteção de rotas.
- Permissões verificadas no frontend e no backend.
- CORS configurável por ambiente.
- RLS habilitada no Supabase e acesso direto de `anon`/`authenticated` bloqueado.
- Histórico e logs preservados para auditoria.
- Credenciais mantidas somente em variáveis de ambiente.

O sistema é exclusivamente interno e não contém cadastro de clientes, vendas, entregas ou pedidos comerciais.
