\* Binding: [cc.bind Terms K] : T checks K : T with every unification
   variable among Terms assumed `cc-bound`.  This is the only rule that
   introduces cc-bound, and it is used only for POSITIVE premises, so a
   variable is bound exactly when a positive premise mentions it.  The
   sort T of the continuation is left open: the same binder serves every
   scoping judgement. *\
(datatype cc-bind
  K : T;
  ______________________
  [cc.bind [] K] : T;

  [cc.uvar X] : cc-bound >> [cc.bind Ts K] : T;
  ______________________
  [cc.bind (cons [cc.uvar X] Ts) K] : T;

  [cc.bind Ts K] : T;
  ______________________
  [cc.bind (cons [cc.const V D] Ts) K] : T;)
