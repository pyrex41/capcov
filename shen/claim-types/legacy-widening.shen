\* unsupported-context-widening (schema 1, rule-authority.shen
   capcov.check-widening): every pair of declared premise occurrences
   (positive or negated) holds the syntactically identical term at each
   shared context index, or the body has a positive compatibility premise
   whose legacy targets name both relations.  Schema 1 has no capabilities:
   a legacy witness covers the whole pair, which is why schema 2 replaced
   it with per-join authorization. *\
(datatype cc-legacy-widening
  [cc.v1-pairs Body Body] : cc-ok;
  ______________________
  [cc.rule N Body H] : cc-legacy-widening;

  ______________________
  [cc.v1-pairs [] All] : cc-ok;

  [cc.v1-pairs-with B Bs All] : cc-ok;
  [cc.v1-pairs Bs All] : cc-ok;
  ______________________
  [cc.v1-pairs (cons B Bs) All] : cc-ok;

  ______________________
  [cc.v1-pairs-with B [] All] : cc-ok;

  [cc.v1-pair B C All] : cc-ok;
  [cc.v1-pairs-with B Cs All] : cc-ok;
  ______________________
  [cc.v1-pairs-with B (cons C Cs) All] : cc-ok;

  [cc.v1-premise B] : (cc-atom RA AA CA);
  [cc.v1-premise C] : (cc-atom RB AB CB);
  [cc.v1-agree-dims AA AB CA CB] : cc-ok;
  ______________________
  [cc.v1-pair B C All] : cc-ok;

  [cc.v1-premise B] : (cc-atom RA AA CA);
  [cc.v1-premise C] : (cc-atom RB AB CB);
  [cc.v1-witnessed RA RB All] : cc-ok;
  ______________________
  [cc.v1-pair B C All] : cc-ok;

  [cc.v1-inert B] : cc-ok;
  ______________________
  [cc.v1-pair B C All] : cc-ok;

  [cc.v1-inert C] : cc-ok;
  ______________________
  [cc.v1-pair B C All] : cc-ok;

  [cc.zip Cols Ts] : (cc-args As);
  ______________________
  [cc.v1-premise [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]]] : (cc-atom R As Ctx);

  [cc.zip Cols Ts] : (cc-args As);
  ______________________
  [cc.v1-premise [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]]] : (cc-atom R As Ctx);

  ______________________
  [cc.v1-inert [cc.occ I [cc.cmp L Op Rt]]] : cc-ok;

  ______________________
  [cc.v1-inert [cc.occ I [cc.pos [cc.rel R cc.undeclared Cl Cp] Ts]]] : cc-ok;

  ______________________
  [cc.v1-inert [cc.occ I [cc.neg [cc.rel R cc.undeclared Cl Cp] Ts]]] : cc-ok;

  ______________________
  [cc.v1-agree-dims AA AB [] CB] : cc-ok;

  if (not (cc.member? D CB))
  [cc.v1-agree-dims AA AB Ds CB] : cc-ok;
  ______________________
  [cc.v1-agree-dims AA AB (cons D Ds) CB] : cc-ok;

  if (cc.member? D CB)
  [cc.v1-term-at D AA] : (cc-term T);
  [cc.v1-term-at D AB] : (cc-term U);
  [cc.is T U] : cc-test;
  [cc.v1-agree-dims AA AB Ds CB] : cc-ok;
  ______________________
  [cc.v1-agree-dims AA AB (cons D Ds) CB] : cc-ok;

  if (cc.eq? M "compatibility") if (cc.member? RA Tg) if (cc.member? RB Tg)
  ______________________
  [cc.v1-witnessed RA RB (cons [cc.occ I [cc.pos [cc.rel W [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs)] : cc-ok;

  [cc.v1-witnessed RA RB Bs] : cc-ok;
  ______________________
  [cc.v1-witnessed RA RB (cons X Bs)] : cc-ok;)
