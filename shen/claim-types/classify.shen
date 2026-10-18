\* What a premise occurrence can carry, exactly evidence-authority-v2.shen
   capcov.v2-carrier: [cc.classify I Item] : (cc-class C) with C one of

     [cc.carrier I Relation Args Context Positive]  context-carrying occurrence
     [cc.witness I Relation Args]                   positive compatibility witness
     [cc.inert I]                                   carries nothing

   A completeness premise carries its scope TARGET's relation, context and
   positions, mapped through the explicit scope (cc.remap); a compatibility
   witness never carries context; an undeclared relation, a negated witness,
   a wrong arity or a comparison carries nothing.  The guards are mutually
   exclusive: an occurrence has at most one classification, so a reifier
   cannot hide a carrier by calling it inert.

   [cc.classify-body Body] : (cc-classes Cs) classifies every occurrence in
   order; each class keeps its occurrence index I, so later judgements name
   the exact occurrences they relate. *\
(datatype cc-classify
  ______________________
  [cc.classify-body []] : (cc-classes []);

  [cc.classify I It] : (cc-class C);
  [cc.classify-body Bs] : (cc-classes Cs);
  ______________________
  [cc.classify-body (cons [cc.occ I It] Bs)] : (cc-classes (cons C Cs));

  ______________________
  [cc.classify I [cc.cmp L Op R]] : (cc-class [cc.inert I]);

  [cc.atom I Ref Ts true] : (cc-class C);
  ______________________
  [cc.classify I [cc.pos Ref Ts]] : (cc-class C);

  [cc.atom I Ref Ts false] : (cc-class C);
  ______________________
  [cc.classify I [cc.neg Ref Ts]] : (cc-class C);

  ______________________
  [cc.atom I [cc.rel R cc.undeclared Cl Cp] Ts P] : (cc-class [cc.inert I]);

  if (cc.eq? M "compatibility") if (cc.true? P)
  [cc.zip Cols Ts] : (cc-args As);
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts P] : (cc-class [cc.witness I R As]);

  if (cc.eq? M "compatibility") if (not (cc.true? P))
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts P] : (cc-class [cc.inert I]);

  if (cc.length-differs? Cols Ts) if (not (cc.eq? M "compatibility"))
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts P] : (cc-class [cc.inert I]);

  if (cc.length-differs? Cols Ts) if (cc.eq? M "compatibility") if (cc.true? P)
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts P] : (cc-class [cc.inert I]);

  if (not (cc.member? M ["compatibility" "completeness"]))
  [cc.zip Cols Ts] : (cc-args As);
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts P] : (cc-class [cc.carrier I R As Ctx P]);

  if (cc.eq? M "completeness") if (not (cc.length-differs? Cols Ts))
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg cc.unscoped] Cl Cp] Ts P] : (cc-class [cc.inert I]);

  if (cc.eq? M "completeness")
  [cc.zip Cols Ts] : (cc-args Own);
  [cc.remap Map Own] : (cc-args As);
  ______________________
  [cc.atom I [cc.rel R [cc.sig M B Cols Ctx Co Tg [cc.scope T Map [cc.sig TM TB TCols TCtx TCo TTg TS]]] Cl Cp] Ts P]
    : (cc-class [cc.carrier I T As TCtx P]);)
