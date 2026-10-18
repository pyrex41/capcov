\* context-index-loss (schema 1, rule-authority.shen capcov.check-context-loss):
   each context index C of the conclusion is carried.  For head term T at C
   (or [cc.absent] when the head has no column C):
     a declared positive premise declaring C holds the identical term at C, or
     a positive compatibility premise mentions T (the legacy witness), or
     T is not a variable and no declared positive premise declares C.
   An undeclared conclusion has no derivation.  Schema 1 compares terms
   syntactically, with no column-type condition.

   [cc.v1-term-at Name Args] : (cc-term T) is the positional lookup
   rule-authority.shen capcov.atom-term-at performs. *\
(datatype cc-legacy-head
  [cc.zip Cols Ts] : (cc-args As);
  [cc.v1-dims As Ctx Body] : cc-ok;
  ______________________
  [cc.rule N Body [cc.head [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] : cc-legacy-head;

  if (cc.names-arg? N As)
  [cc.arg-at N As] : (cc-arg [cc.arg N2 Ty T]);
  ______________________
  [cc.v1-term-at N As] : (cc-term T);

  if (not (cc.names-arg? N As))
  ______________________
  [cc.v1-term-at N As] : (cc-term [cc.absent]);

  ______________________
  [cc.v1-dims As [] Body] : cc-ok;

  [cc.v1-term-at C As] : (cc-term T);
  [cc.v1-dim C T Body Body] : cc-ok;
  [cc.v1-dims As Cs Body] : cc-ok;
  ______________________
  [cc.v1-dims As (cons C Cs) Body] : cc-ok;

  if (cc.member? C Ctx)
  [cc.zip Cols Ts] : (cc-args As);
  [cc.v1-term-at C As] : (cc-term U);
  [cc.is T U] : cc-test;
  ______________________
  [cc.v1-dim C T (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All] : cc-ok;

  if (cc.eq? M "compatibility") if (cc.member? T Ts)
  ______________________
  [cc.v1-dim C T (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All] : cc-ok;

  [cc.v1-dim C T Bs All] : cc-ok;
  ______________________
  [cc.v1-dim C T (cons X Bs) All] : cc-ok;

  if (not (cc.uvar? T))
  [cc.v1-uncarried C All] : cc-ok;
  ______________________
  [cc.v1-dim C T [] All] : cc-ok;

  ______________________
  [cc.v1-uncarried C []] : cc-ok;

  [cc.v1-uncarried C Bs] : cc-ok;
  ______________________
  [cc.v1-uncarried C (cons [cc.occ I [cc.neg R Ts]] Bs)] : cc-ok;

  [cc.v1-uncarried C Bs] : cc-ok;
  ______________________
  [cc.v1-uncarried C (cons [cc.occ I [cc.cmp L Op Rt]] Bs)] : cc-ok;

  [cc.v1-uncarried C Bs] : cc-ok;
  ______________________
  [cc.v1-uncarried C (cons [cc.occ I [cc.pos [cc.rel R cc.undeclared Cl Cp] Ts]] Bs)] : cc-ok;

  if (not (cc.member? C Ctx))
  [cc.v1-uncarried C Bs] : cc-ok;
  ______________________
  [cc.v1-uncarried C (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;)
