with open(r'C:\Users\Utilisateur\Documents\ZARO\apps\zaro-api\app/models/enums.py', 'r') as f:
    content = f.read()

# Add StockMovementType enum after the existing enums
stock_movement_enum = """

class StockMovementType(StrEnum):
    \"\"\"
    Enumeration of all valid stock movement types.
    Used in stock_movements.movement_type CHECK constraint and model validation.
    \"\"\"
    PURCHASE = "purchase"
    RESERVE = "reserve"
    RELEASE = "release"
    CONSUME = "consume"
    PRODUCTION_WASTE = "production_waste"
    INVENTORY_WASTE = "inventory_waste"
    ADJUST = "adjust"
    RETURN = "return"
"""

# Add ProductionOrderStatus enum
production_order_enum = """

class ProductionOrderStatus(StrEnum):
    \"\"\"
    Enumeration of production order statuses.
    Used in production_orders.status CHECK constraint and model validation.
    Matches PostgreSQL productionorderstatus type.
    \"\"\"
    PENDING = "pending"
    PLANNED = "planned"
    MATERIALS_RESERVED = "materials_reserved"
    IN_PRODUCTION = "in_production"
    PAUSED = "paused"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
"""

content = content.rstrip() + stock_movement_enum + production_order_enum
with open(r'C:\Users\Utilisateur\Documents\ZARO\apps\zaro-api\app/models/enums.py', 'w') as f:
    f.write(content)
print('Done - added StockMovementType and ProductionOrderStatus enums')