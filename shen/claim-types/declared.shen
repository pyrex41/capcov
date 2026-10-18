\* undeclared-relation: the conclusion and every (positive or negated)
   premise name a relation that resolves to a declaration.  A relation
   without one is an unapproved, possibly effectful side condition. *\
(datatype cc-declared
  [cc.declared-body Body] : cc-ok;
  ______________________
  [cc.rule N Body [cc.head [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] : cc-declared;

  ______________________
  [cc.declared-body []] : cc-ok;

  [cc.declared-body Bs] : cc-ok;
  ______________________
  [cc.declared-body (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;

  [cc.declared-body Bs] : cc-ok;
  ______________________
  [cc.declared-body (cons [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;

  [cc.declared-body Bs] : cc-ok;
  ______________________
  [cc.declared-body (cons [cc.occ I [cc.cmp L Op Rt]] Bs)] : cc-ok;)
