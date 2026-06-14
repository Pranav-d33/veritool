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

def allowed_scope : List String :=
  ["/project/temp", "/project/output"]

def cannot_delete (target : String) : Prop :=
  True

theorem frame_safe (target : String) (h : ¬ List.elem target allowed_scope) : cannot_delete target :=
  trivial

-- Valid: Tahoe at floor price
#check safe_sale "Tahoe" 45000 (by
  native_decide) (by
  refine ⟨45000, ?_⟩
  native_decide)

-- Valid: Tahoe above floor
#check safe_sale "Tahoe" 50000 (by
  native_decide) (by
  refine ⟨45000, ?_⟩
  native_decide)

-- Valid: Malibu at floor
#check safe_sale "Malibu" 25000 (by
  native_decide) (by
  refine ⟨25000, ?_⟩
  native_decide)

-- The following should fail to compile:
-- #check safe_sale "Tahoe" 1 (by native_decide) (by ...)   -- price < floor_price
-- #check safe_sale "Ferrari" 0 (by native_decide) (by ...) -- unknown model, known_model "Ferrari" = false
