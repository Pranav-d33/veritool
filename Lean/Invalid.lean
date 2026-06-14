import Std

def floor_price : String → Nat
  | "Tahoe"  => 45000
  | "Malibu" => 25000
  | _        => 0

def can_commit (model : String) (price : Nat) : Prop :=
  price ≥ floor_price model

theorem safe_sale (model : String) (price : Nat) (h : price ≥ floor_price model) : can_commit model price :=
  h

-- This should FAIL to compile: Tahoe at $1 is below floor_price of $45000
#check safe_sale "Tahoe" 1 (by
  native_decide)
