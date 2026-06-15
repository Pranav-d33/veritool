import Std

set_option linter.unusedVariables false

structure Action where
  agent : String
  tool : String
  actionType : String
  resource : Option String := none
deriving Repr

def has_type_in (trace : List Action) (t : String) : Prop :=
  ∃ a ∈ trace, a.actionType = t

theorem has_type_in_append_left (t1 t2 : List Action) (t : String) :
    has_type_in t1 t → has_type_in (t1 ++ t2) t := by
  rintro ⟨a, ha, ht⟩
  refine ⟨a, (List.mem_append (s := t1) (t := t2)).mpr (Or.inl ha), ht⟩

def ordering_invariant (trace : List Action) (target : String) (prereqs : List String) : Prop :=
  ∀ a ∈ trace, a.actionType = target → ∀ p ∈ prereqs, has_type_in trace p

theorem ordering_invariant_nil (target : String) (prereqs : List String) :
    ordering_invariant [] target prereqs := by
  intro a ha htype p hp
  simp at ha

theorem ordering_invariant_snoc (trace : List Action) (x : Action) (target : String) (prereqs : List String) :
    ordering_invariant trace target prereqs →
    (x.actionType ≠ target ∨ ∀ p ∈ prereqs, has_type_in trace p) →
    ordering_invariant (trace ++ [x]) target prereqs := by
  intro h hcase a ha htype p hp
  let singleton : List Action := [x]
  rcases (List.mem_append (s := trace) (t := singleton)).mp ha with (hat | han)
  · rcases h a hat htype p hp with ⟨b, hb, hbtype⟩
    exact has_type_in_append_left trace singleton p ⟨b, hb, hbtype⟩
  · have : a = x := by
      simpa [singleton, List.mem_singleton] using han
    subst this
    rcases hcase with (hneq | hall)
    · exact False.elim (hneq htype)
    · rcases hall p hp with ⟨b, hb, hbtype⟩
      exact has_type_in_append_left trace singleton p ⟨b, hb, hbtype⟩
