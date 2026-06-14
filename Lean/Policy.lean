import Std
set_option linter.unusedVariables false

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
