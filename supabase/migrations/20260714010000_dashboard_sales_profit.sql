alter table if exists public.inventory_movement
    add column if not exists unit_sale_price numeric(12, 2) not null default 0;

comment on column public.inventory_movement.unit_sale_price is
    'Preço de venda unitário registrado no momento da saída para cálculo histórico de faturamento e lucro.';
