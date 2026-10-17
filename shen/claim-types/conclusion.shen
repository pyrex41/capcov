\* ungrounded-conclusion-variable: the conclusion is checked in the scope
   of ALL positive premises (wherever they occur in the body), so every
   head variable must be bound by some positive premise.  Negated premises
   and comparisons bind nothing. *\
(datatype cc-conclusion
  [cc.scan-head Body Ts] : cc-conclusion;
  ______________________
  [cc.rule N Body [cc.head R Ts]] : cc-conclusion;

  Ts : cc-bound-terms;
  ______________________
  [cc.scan-head [] Ts] : cc-conclusion;

  [cc.bind Ps [cc.scan-head Bs Ts]] : cc-conclusion;
  ______________________
  [cc.scan-head (cons [cc.occ I [cc.pos R Ps]] Bs) Ts] : cc-conclusion;

  [cc.scan-head Bs Ts] : cc-conclusion;
  ______________________
  [cc.scan-head (cons [cc.occ I [cc.neg R Ps]] Bs) Ts] : cc-conclusion;

  [cc.scan-head Bs Ts] : cc-conclusion;
  ______________________
  [cc.scan-head (cons [cc.occ I [cc.cmp L Op Rt]] Bs) Ts] : cc-conclusion;)
