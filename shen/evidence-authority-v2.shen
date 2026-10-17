\* Independent schema-v2 evidence authority. Input is declaration data, never
   Python's verdict or emitted authorization witnesses. No transitive closure
   of compatibility is taken. A carrier retains each premise occurrence. *\

(define capcov.v2-find
  X [] -> capcov.none
  X [[X | Rest] | _] -> [X | Rest]
  X [_ | Rest] -> (capcov.v2-find X Rest))

(define capcov.v2-col
  Rel Name -> (let D (capcov.decl Rel)
                (if (= D capcov.none) capcov.none
                    (capcov.v2-find Name (capcov.decl-columns D)))))

(define capcov.v2-context?
  Rel Name -> (let D (capcov.decl Rel)
                (and (not (= D capcov.none)) (element? Name (capcov.decl-context D)))))

(define capcov.v2-scope-ok?
  [Rel Target Mapping] ->
    (let D (capcov.decl Rel) T (capcov.decl Target)
      (and (not (= D capcov.none))
       (and (not (= T capcov.none))
        (and (= (capcov.decl-modality D) "completeness")
         (and (= (capcov.decl-completes D) Target)
          (and (= (capcov.sort-strings (map (/. P (nth 1 P)) Mapping))
                  (capcov.sort-strings (capcov.column-names D)))
           (and (= (length Mapping) (length (capcov.dedupe (capcov.sort-strings (map (/. P (nth 2 P)) Mapping)))))
            (and (capcov.all? (/. C (element? C (map (/. P (nth 2 P)) Mapping))) (capcov.decl-context T))
             (capcov.all? (/. P (let L (capcov.v2-col Rel (nth 1 P)) R (capcov.v2-col Target (nth 2 P))
                                  (and (not (= L capcov.none))
                                   (and (not (= R capcov.none)) (= (nth 2 L) (nth 2 R)))))) Mapping))))))))))

(define capcov.v2-endpoint-ok?
  W Col Dim Targets ->
    (let C (capcov.v2-col W Col)
      (and (not (= C capcov.none))
       (and (not (empty? Targets))
        (capcov.all? (/. T (let TC (capcov.v2-col T Dim)
                            (and (capcov.v2-context? T Dim)
                             (and (not (= TC capcov.none)) (= (nth 2 TC) (nth 2 C)))))) Targets)))))

(define capcov.v2-cap-ok?
  [Name W LD RD LC RC LT RT Sym] ->
    (let D (capcov.decl W)
      (and (not (= D capcov.none))
       (and (= (capcov.decl-modality D) "compatibility")
        (and (not (= LC RC))
         (and (capcov.v2-endpoint-ok? W LC LD LT)
              (capcov.v2-endpoint-ok? W RC RD RT)))))))

(define capcov.v2-bridge-ok?
  [Name LD RD LT RT] ->
    (and (not (= LD RD))
     (and (capcov.all? (/. T (capcov.v2-context? T LD)) LT)
          (capcov.all? (/. T (capcov.v2-context? T RD)) RT))))

(define capcov.v2-unique?
  Records -> (let Names (map (/. R (nth 1 R)) Records)
                (= (length Names) (length (capcov.dedupe (capcov.sort-strings Names))))))

(define capcov.v2-contracts-base-ok?
  -> (and (capcov.all? (/. Name (let D (capcov.decl Name)
                                 (and (empty? (capcov.decl-compat-targets D))
                                  (and (and (empty? (capcov.decl-compat-context D))
                                       (or (not (= (capcov.decl-modality D) "compatibility"))
                                           (empty? (capcov.decl-context D))))
                                   (or (not (= (capcov.decl-modality D) "completeness"))
                                       (not (= (capcov.v2-find Name (value capcov.*scopes*)) capcov.none)))))))
                       (value capcov.*relation-names*))
       (and (capcov.v2-unique? (value capcov.*scopes*))
        (and (capcov.v2-unique? (value capcov.*capabilities*))
         (and (capcov.v2-unique? (value capcov.*bridges*))
          (and (capcov.all? (function capcov.v2-scope-ok?) (value capcov.*scopes*))
           (and (capcov.all? (function capcov.v2-cap-ok?) (value capcov.*capabilities*))
                (capcov.all? (function capcov.v2-bridge-ok?) (value capcov.*bridges*)))))))))

(define capcov.v2-columns
  [] [] -> []
  [[Name Type _] | Cs] [Term | Ts] -> [[Name Type Term] | (capcov.v2-columns Cs Ts)]
  _ _ -> [])

(define capcov.v2-remap
  Columns Mapping -> (map (/. P (let C (capcov.v2-find (nth 1 P) Columns)
                                  [(nth 2 P) (nth 2 C) (nth 3 C)])) Mapping))

(define capcov.v2-carrier
  [Rel Terms] Positive ->
    (let D (capcov.decl Rel)
      (cond ((= D capcov.none) capcov.none)
            ((= (capcov.decl-modality D) "compatibility") capcov.none)
            ((not (= (length Terms) (capcov.decl-arity D))) capcov.none)
            ((= (capcov.decl-modality D) "completeness")
             (let S (capcov.v2-find Rel (value capcov.*scopes*))
               (if (= S capcov.none) capcov.none
                   [(nth 2 S) (capcov.v2-remap (capcov.v2-columns (capcov.decl-columns D) Terms) (nth 3 S))
                    (capcov.decl-context (capcov.decl (nth 2 S))) Positive])))
            (true [Rel (capcov.v2-columns (capcov.decl-columns D) Terms) (capcov.decl-context D) Positive]))))

(define capcov.v2-carriers
  [] -> []
  [[capcov.pos Rel Terms] | Rest] ->
    (let C (capcov.v2-carrier [Rel Terms] true)
      (if (= C capcov.none) (capcov.v2-carriers Rest) [C | (capcov.v2-carriers Rest)]))
  [[capcov.neg Rel Terms] | Rest] ->
    (let C (capcov.v2-carrier [Rel Terms] false)
      (if (= C capcov.none) (capcov.v2-carriers Rest) [C | (capcov.v2-carriers Rest)]))
  [_ | Rest] -> (capcov.v2-carriers Rest))

(define capcov.v2-same?
  [_ Type [capcov.v X]] [_ Type [capcov.v X]] -> true
  [_ Type [capcov.c X Type]] [_ Type [capcov.c X Type]] -> true
  _ _ -> false)

(define capcov.v2-value
  Carrier Dim -> (capcov.v2-find Dim (nth 2 Carrier)))

(define capcov.v2-witness-matches?
  A AD B BD W WC1 WC2 ->
    (let Columns (capcov.v2-columns (capcov.decl-columns (capcov.decl (nth 1 W))) (nth 2 W))
      (and (capcov.v2-same? (capcov.v2-value A AD) (capcov.v2-find WC1 Columns))
           (capcov.v2-same? (capcov.v2-value B BD) (capcov.v2-find WC2 Columns)))))

(define capcov.v2-direct?
  A AD B BD [Name WR LD RD LC RC LT RT Sym] Witnesses ->
    (and (= AD LD) (and (= BD RD)
      (and (element? (nth 1 A) LT) (and (element? (nth 1 B) RT)
        (capcov.any? (/. W (and (= (nth 1 W) WR) (capcov.v2-witness-matches? A AD B BD W LC RC))) Witnesses))))))

(define capcov.v2-authorized?
  A AD B BD Witnesses ->
    (capcov.any? (/. C (or (capcov.v2-direct? A AD B BD C Witnesses)
                           (and (nth 9 C) (capcov.v2-direct? B BD A AD C Witnesses))))
                  (value capcov.*capabilities*)))

(define capcov.v2-bridge-applies?
  A B [Name LD RD LT RT] ->
    (and (element? LD (nth 3 A))
     (and (element? RD (nth 3 B))
      (and (or (empty? LT) (element? (nth 1 A) LT))
           (or (empty? RT) (element? (nth 1 B) RT))))))

(define capcov.v2-pair-ok?
  A B Witnesses ->
    (and (capcov.all? (/. C (or (not (element? C (nth 3 B)))
                               (or (capcov.v2-same? (capcov.v2-value A C) (capcov.v2-value B C))
                                   (capcov.v2-authorized? A C B C Witnesses)))) (nth 3 A))
         (capcov.all? (/. P (and
           (or (not (capcov.v2-bridge-applies? A B P))
               (capcov.v2-authorized? A (nth 2 P) B (nth 3 P) Witnesses))
           (or (not (capcov.v2-bridge-applies? B A P))
               (capcov.v2-authorized? B (nth 2 P) A (nth 3 P) Witnesses)))) (value capcov.*bridges*))))

(define capcov.v2-widening?
  Rule -> (let Cs (capcov.v2-carriers (capcov.rule-body Rule)) Ws (capcov.compat-witnesses Rule)
             (capcov.all? (/. Pair (capcov.v2-pair-ok? (fst Pair) (snd Pair) Ws)) (capcov.pairs-of Cs))))

(define capcov.v2-closure-matches?
  Neg W -> (let S (capcov.v2-find (nth 1 W) (value capcov.*scopes*))
             (and (not (= S capcov.none))
              (and (= (nth 2 S) (nth 1 Neg))
               (let NC (capcov.v2-carrier Neg false) WC (capcov.v2-carrier W true)
                 (capcov.all? (/. P (capcov.v2-same? (capcov.v2-value NC (nth 2 P))
                                                    (capcov.v2-value WC (nth 2 P)))) (nth 3 S)))))))

(define capcov.v2-completeness?
  Rule -> (let Negs (capcov.declared-atoms (capcov.negative-atoms (capcov.rule-body Rule)))
               Pos (capcov.declared-atoms (capcov.positive-atoms (capcov.rule-body Rule)))
            (capcov.all? (/. N (and (not (= (capcov.atom-modality N) "compatibility"))
                               (capcov.any? (/. W (capcov.v2-closure-matches? N W)) Pos))) Negs)))

(define capcov.v2-head-bridge?
  H Dim C P Ws ->
    (or (and (= Dim (nth 2 P))
         (and (capcov.v2-bridge-applies? H C P)
              (capcov.v2-authorized? H Dim C (nth 3 P) Ws)))
        (and (= Dim (nth 3 P))
         (and (capcov.v2-bridge-applies? C H P)
              (capcov.v2-authorized? C (nth 2 P) H Dim Ws)))))

(define capcov.v2-head-dimension?
  H Dim Cs Ws ->
    (let Same (capcov.filter (/. C (element? Dim (nth 3 C))) Cs)
      (or (capcov.any? (/. C (or (capcov.v2-same? (capcov.v2-value H Dim) (capcov.v2-value C Dim))
                                (capcov.v2-authorized? H Dim C Dim Ws))) Same)
       (or (capcov.any? (/. C (capcov.any? (/. P (capcov.v2-head-bridge? H Dim C P Ws)) (value capcov.*bridges*))) Cs)
        (and (not (capcov.variable? (nth 3 (capcov.v2-value H Dim))))
         (and (empty? Same)
          (not (capcov.any? (/. C (capcov.any? (/. P (or (capcov.v2-bridge-applies? H C P)
                                                       (capcov.v2-bridge-applies? C H P))) (value capcov.*bridges*))) Cs))))))))

(define capcov.v2-head?
  Rule -> (let H (capcov.v2-carrier [(capcov.rule-head-rel Rule) (capcov.rule-head-terms Rule)] true)
               Cs (capcov.filter (/. C (nth 4 C)) (capcov.v2-carriers (capcov.rule-body Rule)))
               Ws (capcov.compat-witnesses Rule)
            (or (= H capcov.none) (capcov.all? (/. Dim (capcov.v2-head-dimension? H Dim Cs Ws)) (nth 3 H)))))

(define capcov.v2-check
  Id Predicate Rule ->
    (capcov.check Id (and (capcov.v2-contracts-ok?) (Predicate Rule)) "explicit schema-v2 evidence judgment"))

(define capcov.v2-policy-ok?
  [Name Rule Relation Digest] ->
    (let Matches (capcov.filter (/. R (= (nth 1 R) Rule)) (value capcov.*in-rules*)) D (capcov.decl Relation)
      (and (= (length Matches) 1)
       (and (not (= D capcov.none))
        (and (= (capcov.decl-modality D) "completeness")
         (and (not (capcov.decl-primitive? D))
          (and (= (nth 2 (hd Matches)) Digest) (= (nth 1 (nth 3 (hd Matches))) Relation))))))))

(define capcov.v2-policies-ok?
  -> (and (capcov.v2-unique? (value capcov.*derived-policies*))
      (and (capcov.v2-unique? (map (/. P [(nth 2 P)]) (value capcov.*derived-policies*)))
       (and (capcov.all? (function capcov.v2-policy-ok?) (value capcov.*derived-policies*))
        (capcov.all? (/. R (let D (capcov.decl (nth 1 (nth 3 R)))
                             (or (= D capcov.none)
                              (or (not (= (capcov.decl-modality D) "completeness"))
                                  (capcov.any? (/. P (= (nth 2 P) (nth 1 R))) (value capcov.*derived-policies*))))))
                    (value capcov.*in-rules*))))))

(define capcov.v2-contracts-ok?
  -> (and (capcov.v2-unique? (value capcov.*in-rules*))
          (and (capcov.v2-contracts-base-ok?) (capcov.v2-policies-ok?))))

(define capcov.v2-value-type
  X -> "symbol" where (string? X)
  X -> "integer" where (number? X)
  true -> "boolean"
  false -> "boolean"
  [capcov.arr | _] -> "json-metadata-only"
  [capcov.obj | _] -> "json-metadata-only"
  _ -> capcov.none)

(define capcov.v2-type-admits?
  Type Value -> (or (= Type (capcov.v2-value-type Value))
                  (or (and (= Type "digest") (string? Value))
                      (and (element? Type ["unsigned" "timestamp"])
                           (and (number? Value) (>= Value 0))))))

(define capcov.v2-literal-ok?
  [Name Expected [capcov.v V]] -> true
  [Name Expected [capcov.c Value Declared]] ->
    (and (or (= Declared capcov.null) (capcov.v2-type-admits? Declared Value))
         (or (= Expected (if (= Declared capcov.null) (capcov.v2-value-type Value) Declared))
             (and (element? Expected ["unsigned" "timestamp" "digest"])
                  (capcov.v2-type-admits? Expected Value))))
  _ -> false)

(define capcov.v2-atom-typed?
  [Rel Terms] -> (let D (capcov.decl Rel)
                  (and (not (= D capcov.none))
                   (and (= (length Terms) (capcov.decl-arity D))
                        (capcov.all? (function capcov.v2-literal-ok?)
                                     (capcov.v2-columns (capcov.decl-columns D) Terms))))))

(define capcov.v2-constraints
  [] -> []
  [[Name Type [capcov.v V]] | Rest] -> [[V Type] | (capcov.v2-constraints Rest)]
  [_ | Rest] -> (capcov.v2-constraints Rest))

(define capcov.v2-atoms-constraints
  [] -> []
  [[Rel Terms] | Rest] -> (append (capcov.v2-constraints (capcov.v2-columns (capcov.decl-columns (capcov.decl Rel)) Terms))
                                 (capcov.v2-atoms-constraints Rest)))

(define capcov.v2-rule-types?
  Rule -> (let Atoms [[(capcov.rule-head-rel Rule) (capcov.rule-head-terms Rule)] | (capcov.all-atoms (capcov.rule-body Rule))]
             (and (capcov.all? (function capcov.v2-atom-typed?) Atoms)
                  (let Constraints (capcov.v2-atoms-constraints Atoms)
                    (capcov.all? (/. C (= (nth 2 C) (nth 2 (capcov.v2-find (nth 1 C) Constraints)))) Constraints)))))
