\* Completeness witnesses: [cc.closes V Neg W] : cc-ok when positive premise
   occurrence W is an exact scoped completeness witness for negated
   occurrence Neg, under schema V.

   cc.v2 (evidence-authority-v2.shen capcov.v2-closure-matches?): W's
   relation has a declared scope whose target is Neg's relation, and for
   EVERY mapped target column the carried positions of the two occurrences
   are cc-same -- non-context columns (request, path, window) included.

   cc.v1 (rule-authority.shen capcov.completeness-witness?): W's relation is
   a completeness relation completing Neg's relation with the identical
   context index list, and every column of Neg's relation that W also has
   holds the syntactically identical term.

   [cc.closed-by V Neg Body] searches the body for such a W. *\
(datatype cc-closes
  [cc.closes V Neg [cc.occ J [cc.pos R Ws]]] : cc-ok;
  ______________________
  [cc.closed-by V Neg (cons [cc.occ J [cc.pos R Ws]] Bs)] : cc-ok;

  [cc.closed-by V Neg Bs] : cc-ok;
  ______________________
  [cc.closed-by V Neg (cons B Bs)] : cc-ok;

  if (cc.eq? T R)
  [cc.classify I [cc.neg [cc.rel R D Cl Cp] Ts]] : (cc-class NC);
  [cc.classify J [cc.pos [cc.rel W [cc.sig M B Cols Ctx Co Tg [cc.scope T Map TD]] WCl WCp] Ws]] : (cc-class WC);
  [cc.mapped Map NC WC] : cc-ok;
  ______________________
  [cc.closes cc.v2 [cc.occ I [cc.neg [cc.rel R D Cl Cp] Ts]]
                   [cc.occ J [cc.pos [cc.rel W [cc.sig M B Cols Ctx Co Tg [cc.scope T Map TD]] WCl WCp] Ws]]] : cc-ok;

  ______________________
  [cc.mapped [] NC WC] : cc-ok;

  [cc.arg-at D NA] : (cc-arg VN);
  [cc.arg-at D WA] : (cc-arg VW);
  [cc.same VN VW] : cc-same;
  [cc.mapped Ms [cc.carrier I NR NA NCx NP] [cc.carrier J WR WA WCx WP]] : cc-ok;
  ______________________
  [cc.mapped (cons (cons L (cons D [])) Ms) [cc.carrier I NR NA NCx NP] [cc.carrier J WR WA WCx WP]] : cc-ok;

  if (cc.eq? WM "completeness") if (cc.eq? WCo R) if (cc.eq? WCtx TCtx)
  [cc.zip TCols Ts] : (cc-args NA);
  [cc.zip WCols Ws] : (cc-args WA);
  [cc.v1-agree NA WA] : cc-ok;
  ______________________
  [cc.closes cc.v1 [cc.occ I [cc.neg [cc.rel R [cc.sig TM TB TCols TCtx TCo TTg TS] Cl Cp] Ts]]
                   [cc.occ J [cc.pos [cc.rel W [cc.sig WM WB WCols WCtx WCo WTg WS] WCl WCp] Ws]]] : cc-ok;

  ______________________
  [cc.v1-agree [] WA] : cc-ok;

  if (not (cc.names-arg? N WA))
  [cc.v1-agree As WA] : cc-ok;
  ______________________
  [cc.v1-agree (cons [cc.arg N Ty T] As) WA] : cc-ok;

  if (cc.names-arg? N WA)
  [cc.arg-at N WA] : (cc-arg [cc.arg N2 Ty2 T2]);
  [cc.is T T2] : cc-test;
  [cc.v1-agree As WA] : cc-ok;
  ______________________
  [cc.v1-agree (cons [cc.arg N Ty T] As) WA] : cc-ok;)
