\* Terms : (cc-conforms Columns): one term per column, in order, each at the
   column's type.  A variable conforms only through its cc-sort hypothesis
   (so its sort must equal the column type); a constant through the
   literal judgement. *\
(datatype cc-conforms
  ______________________
  [] : (cc-conforms []);

  [cc.uvar X] : (cc-sort Ty);
  Ts : (cc-conforms Cs);
  ______________________
  (cons [cc.uvar X] Ts) : (cc-conforms (cons [cc.col N Ty F] Cs));

  if (cc.literal-ok? Ty V D)
  Ts : (cc-conforms Cs);
  ______________________
  (cons [cc.const V D] Ts) : (cc-conforms (cons [cc.col N Ty F] Cs));)
