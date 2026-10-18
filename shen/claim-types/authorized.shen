\* Compatibility authorization of ONE join (schema 2):

     [cc.authorized A AD B BD Classes] : cc-ok

   for carriers A, B and dimensions AD, BD, derivable exactly when a declared
   capability [cc.capability Name W LD RD LC RC LT RT Sym] has (AD, BD) =
   (LD, RD), A's relation in LT and B's in RT, and some positive witness
   occurrence of relation W among Classes binds column LC to A's AD position
   and RC to B's BD position (cc-same).  A symmetric capability may be used
   in the reverse orientation; an asymmetric one may not.  The judgement
   names the two carriers and dimensions, so it authorizes that join only:
   no rule composes two authorizations (compatibility is not transitive),
   and a witness bound to another occurrence's terms authorizes nothing. *\
(datatype cc-authorized
  cc.capabilities : (cc-capabilities Caps);
  [cc.some-capability Caps A AD B BD Cls] : cc-ok;
  ______________________
  [cc.authorized A AD B BD Cls] : cc-ok;

  [cc.direct Cap A AD B BD Cls] : cc-ok;
  ______________________
  [cc.some-capability (cons Cap Caps) A AD B BD Cls] : cc-ok;

  if (cc.true? Sym)
  [cc.direct [cc.capability N W LD RD LC RC LT RT Sym] B BD A AD Cls] : cc-ok;
  ______________________
  [cc.some-capability (cons [cc.capability N W LD RD LC RC LT RT Sym] Caps) A AD B BD Cls] : cc-ok;

  [cc.some-capability Caps A AD B BD Cls] : cc-ok;
  ______________________
  [cc.some-capability (cons Cap Caps) A AD B BD Cls] : cc-ok;

  if (cc.eq? AD LD) if (cc.eq? BD RD) if (cc.member? RA LT) if (cc.member? RB RT)
  [cc.arg-at AD AA] : (cc-arg VA);
  [cc.arg-at BD AB] : (cc-arg VB);
  [cc.witness-in Cls W LC RC VA VB] : cc-ok;
  ______________________
  [cc.direct [cc.capability N W LD RD LC RC LT RT Sym]
             [cc.carrier IA RA AA CA PA] AD [cc.carrier IB RB AB CB PB] BD Cls] : cc-ok;

  if (cc.eq? W W2)
  [cc.arg-at LC As] : (cc-arg WA);
  [cc.same VA WA] : cc-same;
  [cc.arg-at RC As] : (cc-arg WB);
  [cc.same VB WB] : cc-same;
  ______________________
  [cc.witness-in (cons [cc.witness J W2 As] Cs) W LC RC VA VB] : cc-ok;

  [cc.witness-in Cs W LC RC VA VB] : cc-ok;
  ______________________
  [cc.witness-in (cons C Cs) W LC RC VA VB] : cc-ok;)
