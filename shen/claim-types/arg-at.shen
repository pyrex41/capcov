\* The first position named N: [cc.arg-at N Args] : (cc-arg A).  No
   derivation when N is absent. *\
(datatype cc-arg-at
  if (cc.eq? Name N)
  ______________________
  [cc.arg-at Name (cons [cc.arg N Ty T] As)] : (cc-arg [cc.arg N Ty T]);

  if (not (cc.eq? Name N))
  [cc.arg-at Name As] : (cc-arg A);
  ______________________
  [cc.arg-at Name (cons [cc.arg N Ty T] As)] : (cc-arg A);)
