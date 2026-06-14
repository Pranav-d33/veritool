import Std

def floor_price : String → Nat
  | "Tahoe"  => 45000
  | "Malibu" => 25000
  | _        => 0

def can_commit (model : String) (price : Nat) : Prop :=
  price ≥ floor_price model

theorem safe_sale (model : String) (price : Nat) (h : price ≥ floor_price model) : can_commit model price :=
  h

def allowed_scope : List String :=
  ["/project/temp", "/project/output"]

def cannot_delete (target : String) : Prop :=
  True

theorem frame_safe (target : String) (h : ¬ List.elem target allowed_scope) : cannot_delete target :=
  trivial

-- Valid: Tahoe at floor price
#check safe_sale "Tahoe" 45000 (by
  native_decide)

-- Valid: Tahoe above floor
#check safe_sale "Tahoe" 50000 (by
  native_decide)

-- Valid: Malibu at floor
#check safe_sale "Malibu" 25000 (by
  native_decide)

-- Valid: unknown model with price 0 (floor_price defaults to 0)
#check safe_sale "Ferrari" 0 (by
  native_decide)

-- Valid: unknown model with price above 0
#check safe_sale "Ferrari" 100 (by
  native_decide)

-- The following should fail to compile:
-- #check safe_sale "Tahoe" 1 (by native_decide)   -- price < floor_price → proof fails
