\* Terms whose every unification variable is in scope as `cc-bound`;
   constants need no binding. *\
(datatype cc-bound-terms
  ______________________
  [] : cc-bound-terms;

  [cc.uvar X] : cc-bound; Ts : cc-bound-terms;
  ______________________
  (cons [cc.uvar X] Ts) : cc-bound-terms;

  Ts : cc-bound-terms;
  ______________________
  (cons [cc.const V D] Ts) : cc-bound-terms;)
