\* Value identity as a judgement.  A side condition runs before a rule's
   premises, so identity with a value a premise has only just produced (a
   looked-up position, say) is stated as a later premise [cc.is X Y] : cc-test,
   decided by the trusted prelude predicate cc.eq?. *\
(datatype cc-test
  if (cc.eq? X Y)
  ______________________
  [cc.is X Y] : cc-test;)
