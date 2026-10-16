\* Restricted specification elaboration. Only explicit completeness scopes are
   used. No closure facts, recursive templates, callbacks, or I/O are inferred. *\

(define capcov.spec-closure
  [Rel Terms] Scope ->
    (let Closure (nth 1 Scope) Mapping (nth 3 Scope)
      [capcov.pos Closure
       (map (/. C (let P (capcov.v2-find (nth 1 C) Mapping)
                    (if (= P capcov.none)
                        (error "capcov-invalid-input: unmapped closure scope")
                        (capcov.atom-term-at [Rel Terms] (nth 2 P)))))
            (capcov.decl-columns (capcov.decl Closure)))]))

(define capcov.spec-obligation
  Neg Pos ->
    (if (capcov.any? (/. W (capcov.v2-closure-matches? Neg W)) Pos)
        capcov.none
        (let Scopes (capcov.filter (/. S (= (nth 2 S) (nth 1 Neg))) (value capcov.*scopes*))
          (if (= (length Scopes) 1)
              (capcov.spec-closure Neg (hd Scopes))
              (error "capcov-invalid-input: missing or ambiguous completeness policy for ~A" (nth 1 Neg))))))

(define capcov.spec-body
  [] All Prior -> []
  [[capcov.neg Rel Terms] | Rest] All Prior ->
    (if (not (empty? (capcov.minus (capcov.term-vars Terms) (capcov.join-vars (capcov.positive-atoms Prior)))))
        (error "capcov-invalid-input: negated variables must be bound before closure elaboration")
        (let W (capcov.spec-obligation [Rel Terms] (capcov.positive-atoms (append All Prior)))
          (if (= W capcov.none)
              [[capcov.neg Rel Terms] | (capcov.spec-body Rest All Prior)]
              [W [capcov.neg Rel Terms] | (capcov.spec-body Rest All (append Prior [W]))])))
  [X | Rest] All Prior -> [X | (capcov.spec-body Rest All (append Prior [X]))])

(define capcov.spec-rule
  [Name Digest Head Body Agg] ->
    (capcov.raw-rule-json [Name Digest Head (capcov.spec-body Body Body []) Agg]))

(define capcov.spec-elaborate
  -> (do (capcov.reset-state)
         (capcov.load-decls (value capcov.*in-decls*))
         (if (not (capcov.v2-contracts-ok?))
             (error "capcov-invalid-input: malformed evidence contracts")
             (capcov.json-chunks
               (capcov.obj [(@p "kind" "spec-elaboration")
                            (@p "rules" (capcov.arr (map (function capcov.spec-rule) (value capcov.*in-rules*))))])))))
