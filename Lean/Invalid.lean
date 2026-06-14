import Std
set_option linter.unusedVariables false

def known_model : String → Bool
  | "Tahoe"  => true
  | "Malibu" => true
  | _        => false

def floor_price : String → Option Nat
  | "Tahoe"  => some 45000
  | "Malibu" => some 25000
  | _        => none

def can_commit (model : String) (price : Nat) : Prop :=
  ∃ (floor : Nat), floor_price model = some floor ∧ price ≥ floor

theorem safe_sale (model : String) (price : Nat)
    (hm : known_model model = true)
    (hp : ∃ floor, floor_price model = some floor ∧ price ≥ floor) : can_commit model price :=
  hp

-- This should FAIL: Tahoe at $1 is below floor_price of $45000
#check safe_sale "Tahoe" 1 (by
  native_decide) (by
  refine ⟨45000, ?_⟩
  native_decide)

-- This should FAIL: Ferrari is not a known model
#check safe_sale "Ferrari" 0 (by
  native_decide) (by
  native_decide)
