\* A completeness premise carries its TARGET's positions through the explicit
   scope mapping [[ClosureColumn TargetColumn] ...]:
   [cc.remap Mapping ClosureArgs] : (cc-args TargetArgs), in mapping order,
   each position keeping the closure column's type (scope contracts require
   identical endpoint types).  An unmapped closure column has no
   derivation; nothing is carried by name coincidence. *\
(datatype cc-remap
  ______________________
  [cc.remap [] Args] : (cc-args []);

  [cc.arg-at L Args] : (cc-arg [cc.arg L Ty T]);
  [cc.remap Ms Args] : (cc-args As);
  ______________________
  [cc.remap (cons (cons L (cons D [])) Ms) Args] : (cc-args (cons [cc.arg D Ty T] As));)
