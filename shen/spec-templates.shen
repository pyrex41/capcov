\* Declaration-template re-expansion from raw, unexpanded template data.
   Purely syntactic and total: a reference $P (P is [A-Z][A-Za-z0-9]*, taken
   maximally) in a rule or relation name is replaced by its argument text, a
   parameter term [capcov.param P T] becomes the constant [capcov.c Arg T];
   variables and constants are copied. Nothing is evaluated, no template
   instantiates another, and an unknown template, an arity mismatch or an
   unbound or malformed reference is an error, never a pass-through. Python
   (claims/spec/templates.py) expands independently and compares, in order.

   capcov.*spec-templates* = [Templates Instantiations]
     Template      [Name [Param ...] [[RuleName [HeadRel HeadTerms] Body] ...]]
     Instantiation [Name [Arg ...]]                                         *\

(define capcov.tpl-code-in?
  C Lo Hi -> (let N (string->n C) (and (>= N Lo) (<= N Hi))))

(define capcov.tpl-alnum?
  C -> (or (capcov.tpl-code-in? C 48 57) (or (capcov.tpl-code-in? C 65 90) (capcov.tpl-code-in? C 97 122))))

(define capcov.tpl-split
  \\ [Name Rest]: Name is the maximal [A-Za-z0-9]* prefix of S
  S -> (if (= S "")
           ["" ""]
           (if (capcov.tpl-alnum? (pos S 0))
               (let R (capcov.tpl-split (tlstr S)) [(cn (pos S 0) (hd R)) (hd (tl R))])
               ["" S])))

(define capcov.tpl-lookup
  P [] -> (error "capcov-invalid-input: unbound template parameter $~A" P)
  P [[Q A] | Env] -> (if (= P Q) A (capcov.tpl-lookup P Env)))

(define capcov.tpl-subst
  S Env -> (if (= S "")
               ""
               (if (= (pos S 0) "$")
                   (let Split (capcov.tpl-split (tlstr S)) P (hd Split)
                     (if (or (= P "") (not (capcov.tpl-code-in? (pos P 0) 65 90)))
                         (error "capcov-invalid-input: malformed template parameter reference")
                         (cn (capcov.tpl-lookup P Env) (capcov.tpl-subst (hd (tl Split)) Env))))
                   (cn (pos S 0) (capcov.tpl-subst (tlstr S) Env)))))

(define capcov.tpl-term
  [capcov.param P T] Env -> [capcov.c (capcov.tpl-lookup P Env) T]
  [capcov.v Name] _ -> [capcov.v Name]
  [capcov.c V T] _ -> [capcov.c V T]
  _ _ -> (error "capcov-invalid-input: malformed template term"))

(define capcov.tpl-item
  [capcov.pos Rel Terms] Env -> [capcov.pos (capcov.tpl-subst Rel Env) (map (/. X (capcov.tpl-term X Env)) Terms)]
  [capcov.neg Rel Terms] Env -> [capcov.neg (capcov.tpl-subst Rel Env) (map (/. X (capcov.tpl-term X Env)) Terms)]
  [capcov.cmp L Op R] Env -> [capcov.cmp (capcov.tpl-term L Env) Op (capcov.tpl-term R Env)]
  _ _ -> (error "capcov-invalid-input: malformed template body item"))

(define capcov.tpl-rule
  \\ the record shape capcov.raw-rule-json renders; the digest slot is unused
  [Name [Rel Terms] Body] Env ->
    [(capcov.tpl-subst Name Env) ""
     [(capcov.tpl-subst Rel Env) (map (/. X (capcov.tpl-term X Env)) Terms)]
     (map (/. X (capcov.tpl-item X Env)) Body) capcov.null]
  _ _ -> (error "capcov-invalid-input: malformed template rule"))

(define capcov.tpl-dollar?
  S -> (if (= S "") false (if (= (pos S 0) "$") true (capcov.tpl-dollar? (tlstr S)))))

(define capcov.tpl-env
  [] [] -> []
  [P | Ps] [A | As] -> (if (and (string? A) (not (capcov.tpl-dollar? A)))
                           [[P A] | (capcov.tpl-env Ps As)]
                           (error "capcov-invalid-input: template argument must be plain text"))
  _ _ -> (error "capcov-invalid-input: template arity mismatch"))

(define capcov.tpl-instantiate
  [Name Args] Templates ->
    (let Found (capcov.filter (/. T (= (hd T) Name)) Templates)
      (if (= (length Found) 1)
          (let T (hd Found) Params (nth 2 T)
            (if (= (length Params) (length Args))
                (let Env (capcov.tpl-env Params Args)
                  (map (/. R (capcov.tpl-rule R Env)) (nth 3 T)))
                (error "capcov-invalid-input: template ~A takes ~A arguments, given ~A" Name (length Params) (length Args))))
          (error "capcov-invalid-input: unknown or ambiguous template ~A" Name)))
  _ _ -> (error "capcov-invalid-input: malformed template instantiation"))

(define capcov.tpl-expand-all
  [] _ -> []
  [I | Is] Templates -> (append (capcov.tpl-instantiate I Templates) (capcov.tpl-expand-all Is Templates)))

(define capcov.spec-template-rules
  \\ raw rule JSON, in instantiation order; [] when no templates were sent
  -> (let Data (trap-error (value capcov.*spec-templates*) (/. E [[] []]))
       (map (function capcov.raw-rule-json) (capcov.tpl-expand-all (nth 2 Data) (nth 1 Data)))))
