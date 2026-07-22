from reportlab.lib import colors

GOLD = colors.HexColor("#F5B400")
BLACK = colors.HexColor("#111111")
LIGHT = colors.HexColor("#F5F5F5")
MUTED = colors.HexColor("#666666")
RED = colors.HexColor("#C62828")
GREEN = colors.HexColor("#237A45")

REPORT_TYPES = {
    "daily_movements": "Relatório diário de movimentações",
    "current_stock": "Posição atual do estoque",
    "product_quantity": "Quantidade disponível por produto",
    "lot_quantity": "Quantidade disponível por lote",
    "low_stock": "Produtos com estoque baixo",
    "out_of_stock": "Produtos sem estoque",
    "expiring": "Produtos próximos do vencimento",
    "expired": "Produtos vencidos",
    "entries": "Entradas por período",
    "outputs": "Saídas por período",
    "movement_history": "Histórico completo de movimentações",
    "movements_by_user": "Movimentações por usuário",
    "movements_by_product": "Movimentações por produto",
    "inventory_value": "Valor total estimado do estoque",
    "inventory_value_category": "Valor do estoque por categoria",
    "entries_by_supplier": "Entradas por fornecedor",
    "inventory_divergences": "Divergências de inventário",
    "low_movement": "Produtos com pouca movimentação",
}
