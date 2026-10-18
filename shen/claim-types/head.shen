\* context-index-loss (schema 2): each context index Dim of the conclusion
   is carried.  With H the conclusion's carrier and positive carriers only:
     (a) a positive carrier declaring Dim has a cc-same position at Dim, or
         that exact join head/Dim -- carrier/Dim is cc-authorized; or
     (b) a required bridge relates Dim to some positive carrier's dimension
         and that bridged join is cc-authorized, in the bridge's direction;
     (c) the head position is an explicit constant, no positive carrier
         declares Dim, and no bridge applies between the head and any
         positive carrier (an unconflicted constant construction).
   A conclusion that carries nothing (undeclared, compatibility, wrong
   arity) has no context to lose. *\
(datatype cc-head
  [cc.classify cc.head [cc.pos R Ts]] : (cc-class C);
  [cc.classify-body Body] : (cc-classes Cls);
  [cc.head-carried C Cls] : cc-ok;
  ______________________
  [cc.rule N Body [cc.head R Ts]] : cc-head;

  ______________________
  [cc.head-carried [cc.inert I] Cls] : cc-ok;

  ______________________
  [cc.head-carried [cc.witness I W As] Cls] : cc-ok;

  [cc.head-dims [cc.carrier I R As C P] C Cls] : cc-ok;
  ______________________
  [cc.head-carried [cc.carrier I R As C P] Cls] : cc-ok;

  ______________________
  [cc.head-dims H [] Cls] : cc-ok;

  [cc.head-dim H D Cls Cls] : cc-ok;
  [cc.head-dims H Ds Cls] : cc-ok;
  ______________________
  [cc.head-dims H (cons D Ds) Cls] : cc-ok;

  [cc.head-from H D [cc.carrier J R As C true] All] : cc-ok;
  ______________________
  [cc.head-dim H D (cons [cc.carrier J R As C true] Cs) All] : cc-ok;

  [cc.head-dim H D Cs All] : cc-ok;
  ______________________
  [cc.head-dim H D (cons C Cs) All] : cc-ok;

  [cc.arg-at D As] : (cc-arg [cc.arg N Ty [cc.const V T]]);
  [cc.unconflicted [cc.carrier I R As C P] D All] : cc-ok;
  ______________________
  [cc.head-dim [cc.carrier I R As C P] D [] All] : cc-ok;

  if (cc.member? D Ctx)
  [cc.joined H D [cc.carrier J R As Ctx P] D All] : cc-ok;
  ______________________
  [cc.head-from H D [cc.carrier J R As Ctx P] All] : cc-ok;

  cc.bridges : (cc-bridges Ps);
  [cc.head-bridge H D Cr Ps All] : cc-ok;
  ______________________
  [cc.head-from H D Cr All] : cc-ok;

  if (cc.eq? D LD) if (cc.bridge-applies? H Cr [cc.bridge N LD RD LT RT])
  [cc.authorized H D Cr RD All] : cc-ok;
  ______________________
  [cc.head-bridge H D Cr (cons [cc.bridge N LD RD LT RT] Ps) All] : cc-ok;

  if (cc.eq? D RD) if (cc.bridge-applies? Cr H [cc.bridge N LD RD LT RT])
  [cc.authorized Cr LD H D All] : cc-ok;
  ______________________
  [cc.head-bridge H D Cr (cons [cc.bridge N LD RD LT RT] Ps) All] : cc-ok;

  [cc.head-bridge H D Cr Ps All] : cc-ok;
  ______________________
  [cc.head-bridge H D Cr (cons P Ps) All] : cc-ok;

  ______________________
  [cc.unconflicted H D []] : cc-ok;

  [cc.unconflicted H D Cs] : cc-ok;
  ______________________
  [cc.unconflicted H D (cons [cc.inert I] Cs)] : cc-ok;

  [cc.unconflicted H D Cs] : cc-ok;
  ______________________
  [cc.unconflicted H D (cons [cc.witness I W As] Cs)] : cc-ok;

  [cc.unconflicted H D Cs] : cc-ok;
  ______________________
  [cc.unconflicted H D (cons [cc.carrier I R As C false] Cs)] : cc-ok;

  if (not (cc.member? D C))
  cc.bridges : (cc-bridges Ps);
  [cc.no-bridge H [cc.carrier I R As C true] Ps] : cc-ok;
  [cc.unconflicted H D Cs] : cc-ok;
  ______________________
  [cc.unconflicted H D (cons [cc.carrier I R As C true] Cs)] : cc-ok;

  ______________________
  [cc.no-bridge H Cr []] : cc-ok;

  if (not (cc.bridge-applies? H Cr P)) if (not (cc.bridge-applies? Cr H P))
  [cc.no-bridge H Cr Ps] : cc-ok;
  ______________________
  [cc.no-bridge H Cr (cons P Ps)] : cc-ok;)
