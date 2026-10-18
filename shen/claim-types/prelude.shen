\* shen/claim-types/prelude.shen -- primitive predicates of the typed claim authority.

   Loaded UNTYPED after the workbench and before the claim-types datatypes.
   These are the only functions a datatype side condition calls.  Each
   decides a ground, first-order fact: equality of two values, list
   membership, a length difference, the JSON value class of a literal.  They
   are TRUSTED checker functions: Shen's type checker does not check them,
   and docs/typed-claim-authority.md lists them as such.

   Every predicate is total: the checker tries rules against unrelated and
   partially bound terms while searching, and an error that unwinds out of
   shen.typecheck leaves its Prolog state unusable for every later unit in
   the process (measured on shen-go c12933d), so cc.total turns a raise into
   false.

   A side condition sees the SYNTACTIC term (a list literal arrives as
   [cons X [cons Y []]]), so every predicate first walks it back to a value
   with cc.value -- the shen/modelcheck/prelude.shen convention. *\

(define cc.total
  F -> (trap-error (= true (thaw F)) (/. E false)))

(define cc.value
  [] -> []
  [cons X Xs] -> [(cc.value X) | (cc.value Xs)]
  X -> X)

(define cc.syntax
  \\ the inverse: a value as constructor syntax for shen.typecheck
  [] -> []
  [X | Xs] -> [cons (cc.syntax X) (cc.syntax Xs)]
  X -> X)

(define cc.eq?
  X Y -> (cc.total (freeze (= (cc.value X) (cc.value Y)))))

(define cc.member?
  X L -> (cc.total (freeze (cc.member-h? (cc.value X) (cc.value L)))))

(define cc.member-h?
  X [] -> false
  X [Y | Ys] -> (or (= X Y) (cc.member-h? X Ys))
  _ _ -> false)

(define cc.empty?
  L -> (cc.total (freeze (= (cc.value L) []))))

(define cc.true?
  X -> (cc.total (freeze (= (cc.value X) true))))

(define cc.length-differs?
  A B -> (cc.total (freeze (cc.length-differs-h? (cc.value A) (cc.value B)))))

(define cc.length-differs-h?
  [] [] -> false
  [_ | Xs] [_ | Ys] -> (cc.length-differs-h? Xs Ys)
  _ _ -> true)

(define cc.uvar?
  T -> (cc.total (freeze (cc.uvar-h? (cc.value T)))))

(define cc.uvar-h?
  [cc.uvar _] -> true
  _ -> false)

\\ The JSON value class of a literal, exactly evidence-authority-v2.shen
\\ capcov.v2-value-type over the value (not its syntax).
(define cc.value-type
  X -> "symbol" where (string? X)
  X -> "integer" where (number? X)
  true -> "boolean"
  false -> "boolean"
  [capcov.arr | _] -> "json-metadata-only"
  [capcov.obj | _] -> "json-metadata-only"
  _ -> capcov.none)

(define cc.admits?
  Type Value -> (or (= Type (cc.value-type Value))
                  (or (and (= Type "digest") (string? Value))
                      (and (cc.member-h? Type ["unsigned" "timestamp"])
                           (and (number? Value) (>= Value 0))))))

(define cc.literal-ok?
  \\ a constant with declared tag D (or capcov.null) at a column of type E
  E V D -> (cc.total (freeze (cc.literal-ok-h? (cc.value E) (cc.value V) (cc.value D)))))

(define cc.literal-ok-h?
  E V D -> (and (or (= D capcov.null) (cc.admits? D V))
                (or (= E (if (= D capcov.null) (cc.value-type V) D))
                    (and (cc.member-h? E ["unsigned" "timestamp" "digest"])
                         (cc.admits? E V)))))

(define cc.bridge-applies?
  \\ evidence-authority-v2.shen capcov.v2-bridge-applies?, over carrier and
  \\ bridge syntax: [cc.carrier I R Args Ctx Pol], [cc.bridge N LD RD LT RT]
  A B P -> (cc.total (freeze (cc.bridge-applies-h? (cc.value A) (cc.value B) (cc.value P)))))

(define cc.bridge-applies-h?
  [cc.carrier _ RA _ CA _] [cc.carrier _ RB _ CB _] [cc.bridge _ LD RD LT RT]
    -> (and (cc.member-h? LD CA)
        (and (cc.member-h? RD CB)
         (and (or (= LT []) (cc.member-h? RA LT))
              (or (= RT []) (cc.member-h? RB RT)))))
  _ _ _ -> false)

(define cc.same-at?
  \\ a GUARD only, never a judgement: are carriers A and B cc-same at AD/BD?
  \\ It keeps "same" and "authorized" from both deriving one join, so a
  \\ failing unit does not retry every combination of equivalent proofs.
  A AD B BD -> (cc.total (freeze (cc.same-at-h? (cc.value A) (cc.value AD) (cc.value B) (cc.value BD)))))

(define cc.same-at-h?
  [cc.carrier _ _ AA _ _] AD [cc.carrier _ _ AB _ _] BD
    -> (cc.same-arg? (cc.arg-named AD AA) (cc.arg-named BD AB))
  _ _ _ _ -> false)

(define cc.arg-named
  N [[cc.arg N | Rest] | _] -> [cc.arg N | Rest]
  N [_ | As] -> (cc.arg-named N As)
  _ _ -> capcov.none)

(define cc.same-arg?
  [cc.arg _ T [cc.uvar X]] [cc.arg _ T [cc.uvar X]] -> true
  [cc.arg _ T [cc.const V T]] [cc.arg _ T [cc.const V T]] -> true
  _ _ -> false)

(define cc.unique?
  L -> (cc.total (freeze (cc.unique-h? (cc.value L)))))

(define cc.unique-h?
  [] -> true
  [X | Xs] -> (and (not (cc.member-h? X Xs)) (cc.unique-h? Xs))
  _ -> false)

(define cc.names-arg?
  \\ does a typed-position list [[cc.arg Name Type Term] ...] name N?
  N As -> (cc.total (freeze (cc.names-arg-h? (cc.value N) (cc.value As)))))

(define cc.names-arg-h?
  N [[cc.arg M | _] | As] -> (or (= N M) (cc.names-arg-h? N As))
  N [_ | As] -> (cc.names-arg-h? N As)
  _ _ -> false)

(define cc.runtime-effect?
  \\ a conclusion of a runtime derived or claim relation
  M B -> (cc.total (freeze (and (= (cc.value B) "runtime") (cc.member-h? (cc.value M) ["derived" "claim"])))))

\\ Record fields after the constructor tag, and mapping sides (for `let`).
(define cc.field1 L -> (cc.project (/. R (cc.nth-or 2 R)) (cc.value L)))
(define cc.field2 L -> (cc.project (/. R (cc.nth-or 3 R)) (cc.value L)))
(define cc.lefts L -> (cc.project (/. R (cc.nth-or 1 R)) (cc.value L)))
(define cc.rights L -> (cc.project (/. R (cc.nth-or 2 R)) (cc.value L)))
(define cc.column-names L -> (cc.project (/. R (cc.nth-or 2 R)) (cc.value L)))

(define cc.project
  F [] -> []
  F [X | Xs] -> [(F X) | (cc.project F Xs)]
  _ _ -> [])

(define cc.nth-or
  1 [X | _] -> X
  N [_ | Xs] -> (cc.nth-or (- N 1) Xs) where (and (number? N) (> N 1))
  _ _ -> capcov.none)

(define cc.list?
  [] -> true
  [_ | Xs] -> (cc.list? Xs)
  _ -> false)

(define cc.same-sorted?
  \\ equal as sorted string lists (evidence-authority-v2.shen compares the
  \\ sorted mapping sources with the sorted closure column names)
  A B -> (cc.total (freeze (let X (cc.value A) Y (cc.value B)
           (and (cc.list? X) (and (cc.list? Y)
            (and (capcov.all? (function string?) X)
             (and (capcov.all? (function string?) Y)
                  (= (capcov.sort-strings X) (capcov.sort-strings Y))))))))))

(define cc.subset?
  A B -> (cc.total (freeze (let X (cc.value A) Y (cc.value B)
           (and (cc.list? X) (and (cc.list? Y) (capcov.all? (/. E (cc.member-h? E Y)) X)))))))
