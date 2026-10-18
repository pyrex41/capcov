\* typed-rule (schema 2): every atom -- the conclusion and each positive or
   negated premise -- conforms to its relation's signature: exact arity,
   each unification variable at a column of exactly its sort (one cc-sort
   hypothesis per variable, proposed by the reifier from the first typed
   occurrence and therefore refuted by any disagreeing occurrence), each
   constant a literal of the column type.  An undeclared relation has no
   signature to conform to.  Comparisons are not typed here, as in
   evidence-authority-v2.shen. *\
(datatype cc-typed
  Ts : (cc-conforms Cols);
  [cc.typed-body Body] : cc-ok;
  ______________________
  [cc.rule N Body [cc.head [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] : cc-typed;

  ______________________
  [cc.typed-body []] : cc-ok;

  Ts : (cc-conforms Cols);
  [cc.typed-body Bs] : cc-ok;
  ______________________
  [cc.typed-body (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;

  Ts : (cc-conforms Cols);
  [cc.typed-body Bs] : cc-ok;
  ______________________
  [cc.typed-body (cons [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;

  [cc.typed-body Bs] : cc-ok;
  ______________________
  [cc.typed-body (cons [cc.occ I [cc.cmp L Op Rt]] Bs)] : cc-ok;)
