import Std

set_option linter.unusedVariables false

structure Action where
  agent : String
  tool : String
  actionType : String
  resource : Option String := none
  value : Nat := 0
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

def exclusive_access_invariant (trace : List Action) (target : String) : Prop :=
  ∀ a ∈ trace, a.actionType = target → a.resource ≠ none →
  ∀ b ∈ trace, b.actionType = target → a.resource = b.resource → a.agent = b.agent

theorem exclusive_access_invariant_nil (target : String) :
    exclusive_access_invariant [] target := by
  intro a ha htype hres b hb hres_eq
  simp at ha

theorem exclusive_access_invariant_snoc (trace : List Action) (x : Action) (target : String) :
    exclusive_access_invariant trace target →
    (x.actionType ≠ target ∨ x.resource = none ∨ ∀ a ∈ trace, a.actionType = target → a.resource ≠ none → (a.resource ≠ x.resource ∨ a.agent = x.agent)) →
    exclusive_access_invariant (trace ++ [x]) target := by
  intro h hcase a ha htype hres b hb hbtype hres_eq
  let singleton : List Action := [x]
  have hamem := (List.mem_append (s := trace) (t := singleton)).mp ha
  have hbmem := (List.mem_append (s := trace) (t := singleton)).mp hb
  match hamem, hbmem with
  | Or.inl hat, Or.inl hbt =>
    exact h a hat htype hres b hbt hbtype hres_eq
  | Or.inl hat, Or.inr hbn =>
    have hbx : b = x := by
      simpa [singleton, List.mem_singleton] using hbn
    subst hbx
    match hcase with
    | Or.inl hneq => exact (hneq hbtype).elim
    | Or.inr (Or.inl hnone) => exact (hres (hres_eq.trans hnone)).elim
    | Or.inr (Or.inr hall) =>
      match hall a hat htype hres with
      | Or.inl hneq_res => exact (hneq_res hres_eq).elim
      | Or.inr heq_agent => exact heq_agent
  | Or.inr han, Or.inl hbt =>
    have hax : a = x := by
      simpa [singleton, List.mem_singleton] using han
    subst hax
    match hcase with
    | Or.inl hneq => exact (hneq htype).elim
    | Or.inr (Or.inl hnone) => exact (hres hnone).elim
    | Or.inr (Or.inr hall) =>
      have hbres : b.resource ≠ none := by
        intro hnone
        apply hres
        exact (hres_eq.symm ▸ hnone)
      match hall b hbt hbtype hbres with
      | Or.inl hneq_res => exact (hneq_res hres_eq.symm).elim
      | Or.inr heq_agent => exact heq_agent.symm
  | Or.inr han, Or.inr hbn =>
    have hax : a = x := by
      simpa [singleton, List.mem_singleton] using han
    have hbx : b = x := by
      simpa [singleton, List.mem_singleton] using hbn
    subst hax
    subst hbx
    rfl

def approval_invariant (trace : List Action) (target : String) (approver : String) : Prop :=
  ∀ a ∈ trace, a.actionType = target →
  ∃ b ∈ trace, b.actionType = approver ∧ b.agent ≠ a.agent

theorem approval_invariant_nil (target : String) (approver : String) :
    approval_invariant [] target approver := by
  intro a ha htype
  simp at ha

theorem approval_invariant_snoc (trace : List Action) (x : Action) (target : String) (approver : String) :
    approval_invariant trace target approver →
    (x.actionType ≠ target ∨ ∃ b ∈ trace, b.actionType = approver ∧ b.agent ≠ x.agent) →
    approval_invariant (trace ++ [x]) target approver := by
  intro h hcase a ha htype
  let singleton : List Action := [x]
  rcases (List.mem_append (s := trace) (t := singleton)).mp ha with (hat | han)
  · rcases h a hat htype with ⟨b, hb, hbtype, hbne⟩
    refine ⟨b, (List.mem_append (s := trace) (t := singleton)).mpr (Or.inl hb), hbtype, hbne⟩
  · have : a = x := by
      simpa [singleton, List.mem_singleton] using han
    subst this
    rcases hcase with (hneq | ⟨b, hb, hbtype, hbne⟩)
    · exact False.elim (hneq htype)
    · refine ⟨b, (List.mem_append (s := trace) (t := singleton)).mpr (Or.inl hb), hbtype, hbne⟩

def monotonic_invariant (trace : List Action) (target : String) : Prop :=
  match trace with
  | [] => True
  | x :: xs =>
    ((x.actionType ≠ target) ∨ (∀ a ∈ xs, a.actionType = target → a.agent = x.agent → x.value ≤ a.value))
    ∧ monotonic_invariant xs target

theorem monotonic_invariant_nil (target : String) : monotonic_invariant [] target := by
  simp [monotonic_invariant]

theorem monotonic_invariant_snoc (trace : List Action) (x : Action) (target : String) :
    monotonic_invariant trace target →
    (x.actionType ≠ target ∨ ∀ a ∈ trace, a.actionType = target → a.agent = x.agent → a.value ≤ x.value) →
    monotonic_invariant (trace ++ [x]) target := by
  intro h hcase
  induction trace with
  | nil =>
    simp [monotonic_invariant]
  | cons y ys ih =>
    have h_hd_or : (y.actionType ≠ target ∨ (∀ a ∈ ys, a.actionType = target → a.agent = y.agent → y.value ≤ a.value)) :=
      h.left
    have h_tl_rest : monotonic_invariant ys target := h.right
    have h_cond_ys : (x.actionType ≠ target ∨ ∀ a ∈ ys, a.actionType = target → a.agent = x.agent → a.value ≤ x.value) := by
      rcases hcase with (hneq | hall)
      · left; exact hneq
      · right
        intro a ha ha_type ha_agent
        apply hall a (List.mem_cons_of_mem y ha) ha_type ha_agent
    have h_rest : monotonic_invariant (ys ++ [x]) target := ih h_tl_rest h_cond_ys
    have h_first : (y.actionType ≠ target ∨ (∀ a ∈ (ys ++ [x]), a.actionType = target → a.agent = y.agent → y.value ≤ a.value)) := by
      match h_hd_or with
      | Or.inl h_neq =>
        exact Or.inl h_neq
      | Or.inr h_all =>
        by_cases hy_type_eq : y.actionType = target
        · refine Or.inr ?_
          intro a ha ha_type ha_agent
          rcases (List.mem_append.mp ha) with (ha_ys | ha_x)
          · exact h_all a ha_ys ha_type ha_agent
          · have ha_eq : a = x := by simpa using ha_x
            have a_type_x : x.actionType = target := ha_eq ▸ ha_type
            have a_agent_symm : y.agent = x.agent := by
              simpa [ha_eq] using ha_agent.symm
            rcases hcase with (hneq | hall)
            · exact (hneq a_type_x).elim
            · have hy_mem : y ∈ (y :: ys) := by simp
              rw [ha_eq]
              exact hall y hy_mem hy_type_eq a_agent_symm
        · exact Or.inl hy_type_eq
    exact And.intro h_first h_rest
