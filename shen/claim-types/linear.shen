\* non-linear-recursion: one recursion token per rule.  A positive premise
   whose relation is in the head's own recursive component (Component
   cc.own, from the elaborator's trusted dependency analysis) spends it; a
   second such premise has no derivation.  Negated premises and comparisons
   spend nothing. *\
(datatype cc-linear
  [cc.linear Body cc.unspent] : cc-ok;
  ______________________
  [cc.rule N Body H] : cc-linear;

  ______________________
  [cc.linear [] T] : cc-ok;

  [cc.linear Bs cc.spent] : cc-ok;
  ______________________
  [cc.linear (cons [cc.occ I [cc.pos [cc.rel R D Cl cc.own] Ts]] Bs) cc.unspent] : cc-ok;

  [cc.linear Bs T] : cc-ok;
  ______________________
  [cc.linear (cons [cc.occ I [cc.pos [cc.rel R D Cl cc.other] Ts]] Bs) T] : cc-ok;

  [cc.linear Bs T] : cc-ok;
  ______________________
  [cc.linear (cons [cc.occ I [cc.neg R Ts]] Bs) T] : cc-ok;

  [cc.linear Bs T] : cc-ok;
  ______________________
  [cc.linear (cons [cc.occ I [cc.cmp L Op Rt]] Bs) T] : cc-ok;)
