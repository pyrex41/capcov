\* unsupported-context-widening (schema 2): every pair of context-carrying
   premise occurrences (positive or negated; completeness premises carrying
   their target's context) joins soundly.  For each context index of the
   earlier occurrence the later one also declares, the two positions are
   cc-same or that exact join is cc-authorized; and every required bridge
   that applies to the pair, in either direction, is cc-authorized between
   its two dimensions.  Pairs are enumerated from the classified body, by
   occurrence, so a premise duplicated in the body is one more pair to
   justify and a witness cannot be shared by substituting one occurrence
   for another. *\
(datatype cc-widening
  [cc.classify-body Body] : (cc-classes Cls);
  [cc.pairs Cls Cls] : cc-ok;
  ______________________
  [cc.rule N Body H] : cc-widening;

  ______________________
  [cc.pairs [] All] : cc-ok;

  [cc.pairs-with C Cs All] : cc-ok;
  [cc.pairs Cs All] : cc-ok;
  ______________________
  [cc.pairs (cons C Cs) All] : cc-ok;

  ______________________
  [cc.pairs-with C [] All] : cc-ok;

  ______________________
  [cc.pairs-with [cc.inert I] (cons C Cs) All] : cc-ok;

  ______________________
  [cc.pairs-with [cc.witness I W As] (cons C Cs) All] : cc-ok;

  [cc.pairs-with [cc.carrier I R As Ctx P] Cs All] : cc-ok;
  ______________________
  [cc.pairs-with [cc.carrier I R As Ctx P] (cons [cc.inert J] Cs) All] : cc-ok;

  [cc.pairs-with [cc.carrier I R As Ctx P] Cs All] : cc-ok;
  ______________________
  [cc.pairs-with [cc.carrier I R As Ctx P] (cons [cc.witness J W Ws] Cs) All] : cc-ok;

  [cc.dims [cc.carrier I R As Ctx P] [cc.carrier J R2 As2 Ctx2 P2] Ctx All] : cc-ok;
  cc.bridges : (cc-bridges Bs);
  [cc.bridged [cc.carrier I R As Ctx P] [cc.carrier J R2 As2 Ctx2 P2] Bs All] : cc-ok;
  [cc.pairs-with [cc.carrier I R As Ctx P] Cs All] : cc-ok;
  ______________________
  [cc.pairs-with [cc.carrier I R As Ctx P] (cons [cc.carrier J R2 As2 Ctx2 P2] Cs) All] : cc-ok;

  ______________________
  [cc.dims A B [] All] : cc-ok;

  if (not (cc.member? D CB))
  [cc.dims A [cc.carrier J RB AB CB PB] Ds All] : cc-ok;
  ______________________
  [cc.dims A [cc.carrier J RB AB CB PB] (cons D Ds) All] : cc-ok;

  if (cc.member? D CB)
  [cc.joined A D [cc.carrier J RB AB CB PB] D All] : cc-ok;
  [cc.dims A [cc.carrier J RB AB CB PB] Ds All] : cc-ok;
  ______________________
  [cc.dims A [cc.carrier J RB AB CB PB] (cons D Ds) All] : cc-ok;

  [cc.arg-at AD AA] : (cc-arg VA);
  [cc.arg-at BD AB] : (cc-arg VB);
  [cc.same VA VB] : cc-same;
  ______________________
  [cc.joined [cc.carrier I RA AA CA PA] AD [cc.carrier J RB AB CB PB] BD All] : cc-ok;

  if (not (cc.same-at? A AD B BD))
  [cc.authorized A AD B BD All] : cc-ok;
  ______________________
  [cc.joined A AD B BD All] : cc-ok;

  ______________________
  [cc.bridged A B [] All] : cc-ok;

  [cc.bridge-ok A B P All] : cc-ok;
  [cc.bridge-ok B A P All] : cc-ok;
  [cc.bridged A B Ps All] : cc-ok;
  ______________________
  [cc.bridged A B (cons P Ps) All] : cc-ok;

  if (not (cc.bridge-applies? A B P))
  ______________________
  [cc.bridge-ok A B P All] : cc-ok;

  if (cc.bridge-applies? A B [cc.bridge N LD RD LT RT])
  [cc.authorized A LD B RD All] : cc-ok;
  ______________________
  [cc.bridge-ok A B [cc.bridge N LD RD LT RT] All] : cc-ok;)
