\* ungrounded-side-condition-variable: a negated premise or comparison is
   checked in the scope of the positive premises that PRECEDE it.  This is
   the order both evaluators use (claim-workbench.shen capcov.inst walks the
   body in order and refuses a negation that is not ground at check time;
   Python validation tracks the same environment) and the order the spec
   elaborator requires before inserting closure premises.  The untyped
   authority binds over the whole body; see typed_authority_disagreements. *\
(datatype cc-side
  [cc.scan-side Body] : cc-side;
  ______________________
  [cc.rule N Body H] : cc-side;

  ______________________
  [cc.scan-side []] : cc-side;

  [cc.bind Ps [cc.scan-side Bs]] : cc-side;
  ______________________
  [cc.scan-side (cons [cc.occ I [cc.pos R Ps]] Bs)] : cc-side;

  Ps : cc-bound-terms;
  [cc.scan-side Bs] : cc-side;
  ______________________
  [cc.scan-side (cons [cc.occ I [cc.neg R Ps]] Bs)] : cc-side;

  (cons L (cons Rt [])) : cc-bound-terms;
  [cc.scan-side Bs] : cc-side;
  ______________________
  [cc.scan-side (cons [cc.occ I [cc.cmp L Op Rt]] Bs)] : cc-side;)
