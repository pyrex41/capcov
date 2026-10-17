\* negative-conclusion-without-completeness: every negated premise of a
   declared relation is closed by some positive premise occurrence of the
   same body (cc-closes, schema V).  Under schema 2 a negated compatibility
   witness is never closed: authorization cannot be negated.  Negations of
   undeclared relations are left to undeclared-relation. *\
(datatype cc-complete
  [cc.negations V Body Body] : cc-ok;
  ______________________
  [cc.rule N Body H] : (cc-complete V);

  ______________________
  [cc.negations V [] All] : cc-ok;

  [cc.negations V Bs All] : cc-ok;
  ______________________
  [cc.negations V (cons [cc.occ I [cc.neg [cc.rel R cc.undeclared Cl Cp] Ts]] Bs) All] : cc-ok;

  if (not (cc.eq? M "compatibility"))
  [cc.closed-by cc.v2 [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] All] : cc-ok;
  [cc.negations cc.v2 Bs All] : cc-ok;
  ______________________
  [cc.negations cc.v2 (cons [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All] : cc-ok;

  [cc.closed-by cc.v1 [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] All] : cc-ok;
  [cc.negations cc.v1 Bs All] : cc-ok;
  ______________________
  [cc.negations cc.v1 (cons [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All] : cc-ok;

  [cc.negations V Bs All] : cc-ok;
  ______________________
  [cc.negations V (cons [cc.occ I [cc.pos R Ts]] Bs) All] : cc-ok;

  [cc.negations V Bs All] : cc-ok;
  ______________________
  [cc.negations V (cons [cc.occ I [cc.cmp L Op Rt]] Bs) All] : cc-ok;)
