with open(r'C:\Users\Utilisateur\Documents\ZARO\apps\zaro-api\app/models/enums.py', 'r') as f:
    content = f.read()

# Add ProductionMaterialReservationStatus enum before StockMovementType
prod_mat_res_enum = """

class ProductionMaterialReservationStatus(StrEnum):
    """Status of a production material reservation."""
    PENDING = "pending"
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


PRODUCTION_MATERIAL_RESERVATION_TRANSITIONS: dict[ProductionMaterialReservationStatus, frozenset[ProductionMaterialReservationStatus]] = {
    ProductionMaterialReservationStatus.PENDING: frozenset({ProductionMaterialReservationStatus.RESERVED}),
    ProductionMaterialReservationStatus.RESERVED: frozenset({
        ProductionMaterialReservationStatus.CONSUMED,
        ProductionMaterialReservationStatus.RELEASED,
    }),
    ProductionMaterialReservationStatus.CONSUMED: frozenset(),
    ProductionMaterialReservationStatus.RELEASED: frozenset(),
}
"""

# Add PRODUCTION_ORDER_TRANSITIONS
prod_order_transitions_enum = """

# Allowed forward transitions of the production order lifecycle.
# Terminal states (COMPLETED, CANCELLED) map to an empty set.
PRODUCTION_ORDER_TRANSITIONS: dict[ProductionOrderStatus, frozenset[ProductionOrderStatus]] = {
    ProductionOrderStatus.PENDING: frozenset({ProductionOrderStatus.PLANNED}),
    ProductionOrderStatus.PLANNED: frozenset({ProductionOrderStatus.MATERIALS_RESERVED}),
    ProductionOrderStatus.MATERIALS_RESERVED: frozenset({ProductionOrderStatus.IN_PRODUCTION}),
    ProductionOrderStatus.IN_PRODUCTION: frozenset({
        ProductionOrderStatus.QUALITY_CHECK,
        ProductionOrderStatus.PAUSED,
    }),
    ProductionOrderStatus.QUALITY_CHECK: frozenset({ProductionOrderStatus.READY}),
    ProductionOrderStatus.PAUSED: frozenset({ProductionOrderStatus.IN_PRODUCTION}),
    ProductionOrderStatus.READY: frozenset({ProductionOrderStatus.COMPLETED}),
    ProductionOrderStatus.COMPLETED: frozenset(),
    ProductionOrderStatus.CANCELLED: frozenset(),
}
"""

# Insert before the StockMovementType class (which is at the end now)
# Find the position - after MaterialCategory and before StockMovementType
# StockMovementType starts at line 273 originally, but now with additions it's shifted
# Let me insert after MaterialCategory (which ends at line 132 originally) but before the blank line 133

# Actually, let me just append since the file ends with ProductionOrderStatus
# and I need to add the new enums + transitions after it

content = content.rstrip() + prod_mat_res_enum + prod_order_transitions_enum
with open(r'C:\Users\Utilisateur\Documents\ZARO\apps\zaro-api\app/models/enums.py', 'w') as f:
    f.write(content)
print('Done - added ProductionMaterialReservationStatus, PRODUCTION_ORDER_TRANSITIONS, PRODUCTION_MATERIAL_RESERVATION_TRANSITIONS')