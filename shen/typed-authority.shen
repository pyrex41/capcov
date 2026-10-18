\* capcov typed claim authority (roadmap W2).  A third authority over the
   elaborated claim IR, decided by Shen's type checker.

   Loaded untyped after the workbench, rule-authority.shen and
   evidence-authority-v2.shen, then the claim-types prelude and datatypes.
   It never consults the untyped authority's verdicts.  For each rule it
   REIFIES the elaborated record as the typed IR of claim-types/telescope.shen
   -- typed terms, resolved relation references, premise occurrences, the
   conclusion -- inside a telescope of variable sorts, capabilities and
   bridges.  A unit is

       (shen.typecheck <unit syntax> [cc-judged <sort>])

   run after (tc +); it holds iff the checker derives the type, and a failed
   derivation, a raised error or an exhausted per-unit inference budget is a
   failure.  Each check is its own unit: a conjunction of checks was measured
   to retry every combination of its conjuncts' alternative proofs when a
   late conjunct fails (~1M inferences for a five-premise rule whose single
   failing check needs 6k).  Ids, order and the
   schema-2 contract conjunction are those of rule-authority.shen
   capcov.rule-verdict, so verdicts compare id for id.

   The reifier transcribes; it does not judge.  Trusted here: copying each
   declaration, scope and contract into the reference that names it; the
   pack-level assumption-projection closure (capcov.assumption-relations);
   the recursive-component analysis (capcov.same-scc?); the stratification
   and frozen-checksum results, reported with basis "trusted-elaborator".
   Proposed, then checked: each variable's sort (from its first typed
   occurrence; every occurrence is checked against it).  A rule with an
   aggregation is refused per check (basis "unsupported"): the typed IR has
   no aggregation sort.  docs/typed-claim-authority.md lists the boundary. *\

(set capcov.*typed-units* 0)
(set capcov.*ta-assumed* [])
\\ Inference budget per unit; exhausting it fails that unit (a bounded search
\\ that finds no derivation is a refusal, never an admission).
(set capcov.*unit-inferences* 1000000)
\\ The checker's binding store defaults to 1000 Prolog variables per
\\ typecheck; the pairwise judgements of a 23-premise rule need more (an
\\ overflow raises, which would refuse an admissible rule).
(prolog-memory 200000)

\\ ---------------------------------------------------------------- reified syntax

(define capcov.ta-term
  [capcov.v X] -> [cc.uvar X]
  [capcov.c V T] -> [cc.const V T])

(define capcov.ta-terms
  Ts -> (map (function capcov.ta-term) Ts))

(define capcov.ta-scope
  Rel -> (capcov.v2-find Rel (value capcov.*scopes*)))

(define capcov.ta-sig
  \\ a declaration as [cc.sig ...]; Scoped says whether to resolve its scope
  D Scoped -> [cc.sig (capcov.decl-modality D) (capcov.decl-binding D)
                      (map (/. C [cc.col (nth 1 C) (nth 2 C) (nth 3 C)]) (capcov.decl-columns D))
                      (capcov.decl-context D) (capcov.decl-completes D) (capcov.decl-compat-targets D)
                      (if Scoped (capcov.ta-scope-ref (capcov.decl-name D)) cc.unscoped)])

(define capcov.ta-decl
  Name Scoped -> (let D (capcov.decl Name)
                   (if (= D capcov.none) cc.undeclared (capcov.ta-sig D Scoped))))

(define capcov.ta-scope-ref
  Name -> (let S (capcov.ta-scope Name)
            (if (= S capcov.none)
                cc.unscoped
                [cc.scope (nth 2 S) (nth 3 S) (capcov.ta-decl (nth 2 S) false)])))

(define capcov.ta-ref
  \\ a resolved relation reference [cc.rel Name Decl Class Component]
  Name Comp -> [cc.rel Name (capcov.ta-decl Name true)
                       (if (element? Name (value capcov.*ta-assumed*)) cc.assumption cc.evidence)
                       Comp])

(define capcov.ta-component
  Head Rel -> (if (and (capcov.recursive? Head) (capcov.same-scc? Rel Head)) cc.own cc.other))

(define capcov.ta-item
  H [capcov.pos R Ts] -> [cc.pos (capcov.ta-ref R (capcov.ta-component H R)) (capcov.ta-terms Ts)]
  H [capcov.neg R Ts] -> [cc.neg (capcov.ta-ref R cc.other) (capcov.ta-terms Ts)]
  H [capcov.cmp L Op R] -> [cc.cmp (capcov.ta-term L) Op (capcov.ta-term R)])

(define capcov.ta-body
  H [] _ -> []
  H [X | Xs] I -> [[cc.occ I (capcov.ta-item H X)] | (capcov.ta-body H Xs (+ I 1))])

(define capcov.ta-rule
  R -> (let H (capcov.rule-head-rel R)
         [cc.rule (capcov.rule-name R) (capcov.ta-body H (capcov.rule-body R) 0)
                  [cc.head (capcov.ta-ref H cc.other) (capcov.ta-terms (capcov.rule-head-terms R))]]))

\\ ---------------------------------------------------------------- telescope

(define capcov.ta-wrap
  \\ fold binders [[Tag Arg ...] ...] around K, first binder outermost
  [] K -> K
  [B | Bs] K -> (append B [(capcov.ta-wrap Bs K)]))

(define capcov.ta-atoms
  R -> [[(capcov.rule-head-rel R) (capcov.rule-head-terms R)] | (capcov.all-atoms (capcov.rule-body R))])

(define capcov.ta-sorts
  \\ proposed sort of each variable: the column type of its first occurrence
  \\ in a declared atom of matching arity.  Only a proposal: cc-conforms
  \\ checks every occurrence against it.
  R -> (capcov.ta-sorts-h (capcov.ta-atoms R) []))

(define capcov.ta-sorts-h
  [] Acc -> (map (/. P [cc.let-sort (fst P) (snd P)]) (reverse Acc))
  [[Rel Ts] | As] Acc ->
    (let D (capcov.decl Rel)
      (if (or (= D capcov.none) (not (= (length Ts) (capcov.decl-arity D))))
          (capcov.ta-sorts-h As Acc)
          (capcov.ta-sorts-h As (capcov.ta-sort-cols (capcov.decl-columns D) Ts Acc)))))

(define capcov.ta-sort-cols
  [] [] Acc -> Acc
  [[_ Type _] | Cs] [[capcov.v X] | Ts] Acc ->
    (capcov.ta-sort-cols Cs Ts (if (capcov.any? (/. P (= (fst P) X)) Acc) Acc [(@p X Type) | Acc]))
  [_ | Cs] [_ | Ts] Acc -> (capcov.ta-sort-cols Cs Ts Acc))

(define capcov.ta-unit
  R -> (capcov.ta-wrap (append (if (= (value capcov.*schema-version*) 2) (capcov.ta-sorts R) [])
                               [[cc.let-capabilities (map (/. C [cc.capability | C]) (value capcov.*capabilities*))]
                                [cc.let-bridges (map (/. B [cc.bridge | B]) (value capcov.*bridges*))]])
                       [cc.goal (capcov.ta-rule R)]))

\\ ---------------------------------------------------------------- judging

(define capcov.ta-judge
  \\ one unit: the checker either derives [cc-judged Sort] or it does not
  Unit Sort -> (= (capcov.ta-run Unit Sort (value capcov.*unit-inferences*)) cc.derived))

(define capcov.ta-run
  \\ cc.derived | cc.refused | cc.exhausted, under the unit's own inference
  \\ budget (Shen's limit counts inferences since process start, so without a
  \\ per-unit limit a batch starves its later units).  An exhausted search is
  \\ a refusal, never an admission.
  Unit Sort Budget ->
    (do (set capcov.*typed-units* (+ 1 (value capcov.*typed-units*)))
        (maxinferences (+ (inferences) Budget))
        (trap-error (if (= false (shen.typecheck (cc.syntax Unit) [cc-judged Sort])) cc.refused cc.derived)
                    (/. E (if (= (error-to-string E) "maximum inferences exceeded") cc.exhausted cc.errored)))))

(define capcov.ta-sort-name
  [S V] -> (cn (str S) (cn " " (str V)))
  S -> (str S))

(define capcov.ta-checks
  \\ [Id Sort ContractConjoined] in rule-authority.shen capcov.rule-verdict order
  cc.v2 -> [["typed-rule" cc-typed false]
            ["undeclared-relation" cc-declared false]
            ["ungrounded-conclusion-variable" cc-conclusion false]
            ["ungrounded-side-condition-variable" cc-side false]
            ["context-index-loss" cc-head true]
            ["unsupported-context-widening" cc-widening true]
            ["negative-conclusion-without-completeness" [cc-complete cc.v2] true]
            ["declaration-promoted-to-effect" [cc-promotion cc.v2] false]
            ["non-linear-recursion" cc-linear false]]
  cc.v1 -> [["undeclared-relation" cc-declared false]
            ["ungrounded-conclusion-variable" cc-conclusion false]
            ["ungrounded-side-condition-variable" cc-side false]
            ["context-index-loss" cc-legacy-head false]
            ["unsupported-context-widening" cc-legacy-widening false]
            ["negative-conclusion-without-completeness" [cc-complete cc.v1] false]
            ["declaration-promoted-to-effect" [cc-promotion cc.v1] false]
            ["non-linear-recursion" cc-linear false]])

(define capcov.ta-check
  [Id Sort Conjoined] Result Contracts ->
    (capcov.obj [(@p "id" Id)
                 (@p "ok" (if Conjoined (and Contracts (= Result cc.derived)) (= Result cc.derived)))
                 (@p "basis" (if Conjoined "typed+contracts" "typed"))
                 (@p "detail" (cn "sequent judgement " (cn (capcov.ta-sort-name Sort)
                                (cn (if Conjoined " under cc-contracts" "")
                                    (cond ((= Result cc.exhausted) ": inference budget exhausted, refused")
                                          ((= Result cc.errored) ": the checker raised an error, refused")
                                          (true ""))))))]))

(define capcov.ta-unsupported
  [Id _ _] -> (capcov.obj [(@p "id" Id) (@p "ok" false) (@p "basis" "unsupported")
                           (@p "detail" "aggregation is not elaborated into the typed claim IR")]))

(define capcov.ta-rule-checks
  R V Contracts ->
    (let Unit (capcov.ta-unit R)
         Checks (capcov.ta-checks V)
      (map (/. C (capcov.ta-check C (capcov.ta-run Unit (nth 2 C) (value capcov.*unit-inferences*)) Contracts))
           Checks)))

(define capcov.ta-verdict
  R V Contracts ->
    (let Checks (if (= (capcov.rule-aggregation R) capcov.null)
                    (capcov.ta-rule-checks R V Contracts)
                    (map (function capcov.ta-unsupported) (capcov.ta-checks V)))
      (capcov.obj [(@p "rule" (capcov.rule-name R))
                   (@p "rule_digest" (capcov.rule-digest R))
                   (@p "ok" (capcov.all? (function capcov.ta-check-ok?) Checks))
                   (@p "checks" (capcov.arr Checks))])))

(define capcov.ta-check-ok?
  [capcov.obj (@p "id" _) (@p "ok" Ok) | _] -> Ok)

\\ ---------------------------------------------------------------- pack level

(define capcov.ta-targets
  Names -> (map (/. N [cc.target N (capcov.ta-decl N false)]) Names))

(define capcov.ta-contracts-unit
  -> (let Names (value capcov.*relation-names*)
          Decls (map (/. N (let D (capcov.decl N)
                             [cc.decl N (capcov.decl-modality D) (capcov.decl-context D)
                                      (capcov.decl-compat-targets D) (capcov.decl-compat-context D)]))
                     Names)
          Scopes (map (/. S [cc.scope-contract (nth 1 S) (capcov.ta-decl (nth 1 S) false)
                                               (nth 2 S) (capcov.ta-decl (nth 2 S) false) (nth 3 S)])
                      (value capcov.*scopes*))
          Caps (map (/. C [cc.cap-contract (nth 1 C) (capcov.ta-decl (nth 2 C) false)
                                           (nth 3 C) (nth 4 C) (nth 5 C) (nth 6 C)
                                           (capcov.ta-targets (nth 7 C)) (capcov.ta-targets (nth 8 C))])
                    (value capcov.*capabilities*))
          Bridges (map (/. B [cc.bridge-contract (nth 1 B) (nth 2 B) (nth 3 B)
                                                 (capcov.ta-targets (nth 4 B)) (capcov.ta-targets (nth 5 B))])
                       (value capcov.*bridges*))
          Policies (map (/. P (let D (capcov.decl (nth 3 P))
                                [cc.policy-contract (nth 1 P) (nth 2 P) (nth 3 P) (capcov.ta-decl (nth 3 P) false)
                                                    (if (= D capcov.none) true (capcov.decl-primitive? D)) (nth 4 P)]))
                        (value capcov.*derived-policies*))
          Rules (map (/. R [cc.rule-id (nth 1 R) (nth 2 R) (nth 1 (nth 3 R)) (capcov.ta-decl (nth 1 (nth 3 R)) false)])
                     (value capcov.*in-rules*))
       [cc.goal [cc.contracts Decls Scopes Caps Bridges Policies Rules]]))

(define capcov.ta-trusted
  Id Ok Detail -> (capcov.obj [(@p "id" Id) (@p "ok" Ok) (@p "basis" "trusted-elaborator") (@p "detail" Detail)]))

(define capcov.typed-authority-json
  -> (let V (if (= (value capcov.*schema-version*) 2) cc.v2 cc.v1)
          Reset (set capcov.*typed-units* 0)
          Assumed (set capcov.*ta-assumed* (capcov.assumption-relations))
          Contracts (if (= V cc.v2) (capcov.ta-judge (capcov.ta-contracts-unit) cc-contracts) true)
          Verdicts (map (/. R (capcov.ta-verdict R V Contracts)) (value capcov.*rules*))
          Pack (append (if (= V cc.v2)
                           [(capcov.obj [(@p "id" "evidence-contracts") (@p "ok" Contracts) (@p "basis" "typed")
                                         (@p "detail" "sequent judgement cc-contracts")])]
                           [])
                 [(capcov.ta-trusted "stratified-negation" (not (value capcov.*unstratifiable*))
                                     "stratification computed by the workbench elaborator")
                  (capcov.ta-trusted "frozen-pack-mismatch" true
                                     (if (= (value capcov.*in-frozen*) capcov.null)
                                         "no frozen checksum supplied; this run establishes one"
                                         "elaborated pack checksum equals the frozen checksum"))])
       (capcov.json-chunks
         (capcov.obj [(@p "kind" "typed-authority")
                      (@p "ok" (and (capcov.all? (function capcov.verdict-ok?) Verdicts)
                                    (capcov.all? (function capcov.ta-check-ok?) Pack)))
                      (@p "rules" (capcov.arr Verdicts))
                      (@p "pack" (capcov.arr Pack))
                      (@p "units" (value capcov.*typed-units*))
                      (@p "elaborated_checksum" (value capcov.*elaborated-checksum*))
                      (@p "elaborated" (capcov.json-splice (value capcov.*elaborated-chunks*)))
                      (@p "work" (value capcov.*work*))]))))
