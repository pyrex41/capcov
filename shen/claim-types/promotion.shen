\* declaration-promoted-to-effect: a conclusion of a runtime derived/claim
   relation needs runtime support.  It is derivable from one of
     effective   a declared positive premise with runtime binding, outside
                 the assumption class, of a modality other than
                 compatibility, completeness and assumption;
     projection  (derived conclusions only) the body is exactly one positive
                 premise of the assumption class, which keeps its assumption
                 dependency rather than becoming observed support;
     absence     every declared positive premise is runtime completeness
                 evidence (at least one), and every declared negated premise
                 (at least one) is closed by one of them (cc-closes, schema V).
   Any other conclusion is not a runtime effect and needs nothing.  An
   undeclared conclusion has no derivation.  The assumption class (Class
   cc.assumption) is the trusted pack-level projection closure
   (rule-authority.shen capcov.assumption-relations). *\
(datatype cc-promotion
  [cc.promotes V M B Body] : cc-ok;
  ______________________
  [cc.rule N Body [cc.head [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] : (cc-promotion V);

  if (not (cc.runtime-effect? M B))
  ______________________
  [cc.promotes V M B Body] : cc-ok;

  if (cc.runtime-effect? M B)
  [cc.effective Body] : cc-ok;
  ______________________
  [cc.promotes V M B Body] : cc-ok;

  if (cc.runtime-effect? M B) if (cc.eq? M "derived")
  [cc.projection Body] : cc-ok;
  ______________________
  [cc.promotes V M B Body] : cc-ok;

  if (cc.runtime-effect? M B)
  [cc.absence V Body Body cc.none cc.none] : cc-ok;
  ______________________
  [cc.promotes V M B Body] : cc-ok;

  if (cc.eq? B "runtime") if (not (cc.member? M ["compatibility" "completeness" "assumption"]))
  ______________________
  [cc.effective (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] cc.evidence Cp] Ts]] Bs)] : cc-ok;

  [cc.effective Bs] : cc-ok;
  ______________________
  [cc.effective (cons X Bs)] : cc-ok;

  ______________________
  [cc.projection [[cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] cc.assumption Cp] Ts]]]] : cc-ok;

  ______________________
  [cc.absence V [] All cc.seen cc.seen] : cc-ok;

  [cc.absence V Bs All P Q] : cc-ok;
  ______________________
  [cc.absence V (cons [cc.occ I [cc.pos [cc.rel R cc.undeclared Cl Cp] Ts]] Bs) All P Q] : cc-ok;

  if (cc.eq? M "completeness") if (cc.eq? B "runtime")
  [cc.absence V Bs All cc.seen Q] : cc-ok;
  ______________________
  [cc.absence V (cons [cc.occ I [cc.pos [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All P Q] : cc-ok;

  [cc.absence V Bs All P Q] : cc-ok;
  ______________________
  [cc.absence V (cons [cc.occ I [cc.neg [cc.rel R cc.undeclared Cl Cp] Ts]] Bs) All P Q] : cc-ok;

  [cc.closed-by V [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] All] : cc-ok;
  [cc.absence V Bs All P cc.seen] : cc-ok;
  ______________________
  [cc.absence V (cons [cc.occ I [cc.neg [cc.rel R [cc.sig M B Cols Ctx Co Tg S] Cl Cp] Ts]] Bs) All P Q] : cc-ok;

  [cc.absence V Bs All P Q] : cc-ok;
  ______________________
  [cc.absence V (cons [cc.occ I [cc.cmp L Op Rt]] Bs) All P Q] : cc-ok;)
