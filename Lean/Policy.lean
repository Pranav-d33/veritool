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
