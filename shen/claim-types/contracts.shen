\* evidence-contracts (schema 2, pack level; evidence-authority-v2.shen
   capcov.v2-contracts-ok?): the witness sorts every rule judgement relies on.

     [cc.contracts Decls Scopes Caps Bridges Policies Rules] : cc-contracts

   Decls    [[cc.decl N Modality Context LegacyTargets LegacyContext] ...], every relation
   Scopes   [[cc.scope-contract Closure ClosureDecl Target TargetDecl Mapping] ...]
   Caps     [[cc.cap-contract Name WitnessDecl LD RD LC RC LTargets RTargets] ...]
   Bridges  [[cc.bridge-contract Name LD RD LTargets RTargets] ...]
   Policies [[cc.policy-contract Name Rule Relation RelationDecl Primitive Digest] ...]
   Rules    [[cc.rule-id Name Digest HeadRelation HeadDecl] ...], every input rule
   targets  [[cc.target Name Decl] ...]; a Decl is [cc.sig ...] or cc.undeclared

   A completeness scope maps EVERY closure column exactly once to a distinct
   target column of identical type and covers every target context index.
   A capability's witness is a compatibility relation whose two distinct
   endpoint columns each have exactly the type of the named dimension in
   every (non-empty) target list.  A bridge relates two distinct dimensions
   its targets carry.  Legacy (schema-1) compatibility metadata and scoped
   compatibility relations are refused, every completeness relation has a
   scope, contract and rule names are unique, and each derived completeness
   rule is bound by exactly one named policy to its exact digest. *\
(datatype cc-contracts
  if (cc.unique? (cc.field1 Rules))
  if (cc.unique? (cc.field1 Scopes)) if (cc.unique? (cc.field1 Caps)) if (cc.unique? (cc.field1 Bridges))
  if (cc.unique? (cc.field1 Policies)) if (cc.unique? (cc.field2 Policies))
  let Scoped (cc.field1 Scopes)
  let Policed (cc.field2 Policies)
  [cc.decls-ok Decls Scoped] : cc-ok;
  [cc.scopes-ok Scopes] : cc-ok;
  [cc.caps-ok Caps] : cc-ok;
  [cc.bridges-ok Bridges] : cc-ok;
  [cc.policies-ok Policies Rules] : cc-ok;
  [cc.rules-policed Rules Policed] : cc-ok;
  ______________________
  [cc.contracts Decls Scopes Caps Bridges Policies Rules] : cc-contracts;

  ______________________
  [cc.decls-ok [] Scoped] : cc-ok;

  if (cc.empty? Tg) if (cc.empty? CCtx)
  if (or (not (cc.eq? M "compatibility")) (cc.empty? Ctx))
  if (or (not (cc.eq? M "completeness")) (cc.member? N Scoped))
  [cc.decls-ok Ds Scoped] : cc-ok;
  ______________________
  [cc.decls-ok (cons [cc.decl N M Ctx Tg CCtx] Ds) Scoped] : cc-ok;

  ______________________
  [cc.scopes-ok []] : cc-ok;

  if (cc.eq? M "completeness") if (cc.eq? Co T)
  if (cc.same-sorted? (cc.lefts Map) (cc.column-names Cols))
  if (cc.unique? (cc.rights Map))
  if (cc.subset? TCtx (cc.rights Map))
  [cc.scope-types Map Cols TCols] : cc-ok;
  [cc.scopes-ok Ss] : cc-ok;
  ______________________
  [cc.scopes-ok (cons [cc.scope-contract Cl [cc.sig M B Cols Ctx Co Tg S] T [cc.sig TM TB TCols TCtx TCo TTg TS] Map] Ss)] : cc-ok;

  ______________________
  [cc.scope-types [] Cols TCols] : cc-ok;

  [cc.column-type L Cols] : (cc-type Ty);
  [cc.column-type D TCols] : (cc-type Ty);
  [cc.scope-types Ms Cols TCols] : cc-ok;
  ______________________
  [cc.scope-types (cons (cons L (cons D [])) Ms) Cols TCols] : cc-ok;

  if (cc.eq? N Name)
  ______________________
  [cc.column-type Name (cons [cc.col N Ty F] Cs)] : (cc-type Ty);

  if (not (cc.eq? N Name))
  [cc.column-type Name Cs] : (cc-type Ty);
  ______________________
  [cc.column-type Name (cons [cc.col N Ty2 F] Cs)] : (cc-type Ty);

  ______________________
  [cc.caps-ok []] : cc-ok;

  if (not (cc.eq? LC RC)) if (cc.eq? M "compatibility")
  [cc.endpoint Cols LC LD LT] : cc-ok;
  [cc.endpoint Cols RC RD RT] : cc-ok;
  [cc.caps-ok Cs] : cc-ok;
  ______________________
  [cc.caps-ok (cons [cc.cap-contract Name [cc.sig M B Cols Ctx Co Tg S] LD RD LC RC LT RT] Cs)] : cc-ok;

  if (not (cc.empty? Ts))
  [cc.column-type Col Cols] : (cc-type Ty);
  [cc.endpoint-targets Ty Dim Ts] : cc-ok;
  ______________________
  [cc.endpoint Cols Col Dim Ts] : cc-ok;

  ______________________
  [cc.endpoint-targets Ty Dim []] : cc-ok;

  if (cc.member? Dim Ctx)
  [cc.column-type Dim Cols] : (cc-type Ty);
  [cc.endpoint-targets Ty Dim Ts] : cc-ok;
  ______________________
  [cc.endpoint-targets Ty Dim (cons [cc.target T [cc.sig M B Cols Ctx Co Tg S]] Ts)] : cc-ok;

  ______________________
  [cc.bridges-ok []] : cc-ok;

  if (not (cc.eq? LD RD))
  [cc.carry-all LD LT] : cc-ok;
  [cc.carry-all RD RT] : cc-ok;
  [cc.bridges-ok Bs] : cc-ok;
  ______________________
  [cc.bridges-ok (cons [cc.bridge-contract Name LD RD LT RT] Bs)] : cc-ok;

  ______________________
  [cc.carry-all D []] : cc-ok;

  if (cc.member? D Ctx)
  [cc.carry-all D Ts] : cc-ok;
  ______________________
  [cc.carry-all D (cons [cc.target T [cc.sig M B Cols Ctx Co Tg S]] Ts)] : cc-ok;

  ______________________
  [cc.policies-ok [] Rules] : cc-ok;

  if (cc.eq? M "completeness") if (not (cc.true? Prim))
  [cc.rule-with Rule Rules] : (cc-rule-id [cc.rule-id N2 D2 H2 HD2]);
  [cc.is Digest D2] : cc-test;
  [cc.is H2 Rel] : cc-test;
  [cc.policies-ok Ps Rules] : cc-ok;
  ______________________
  [cc.policies-ok (cons [cc.policy-contract Name Rule Rel [cc.sig M B Cols Ctx Co Tg S] Prim Digest] Ps) Rules] : cc-ok;

  if (cc.eq? Rule N)
  ______________________
  [cc.rule-with Rule (cons [cc.rule-id N D H HD] Rs)] : (cc-rule-id [cc.rule-id N D H HD]);

  if (not (cc.eq? Rule N))
  [cc.rule-with Rule Rs] : (cc-rule-id R);
  ______________________
  [cc.rule-with Rule (cons [cc.rule-id N D H HD] Rs)] : (cc-rule-id R);

  ______________________
  [cc.rules-policed [] Policed] : cc-ok;

  [cc.rules-policed Rs Policed] : cc-ok;
  ______________________
  [cc.rules-policed (cons [cc.rule-id N D H cc.undeclared] Rs) Policed] : cc-ok;

  if (or (not (cc.eq? M "completeness")) (cc.member? N Policed))
  [cc.rules-policed Rs Policed] : cc-ok;
  ______________________
  [cc.rules-policed (cons [cc.rule-id N D H [cc.sig M B Cols Ctx Co Tg S]] Rs) Policed] : cc-ok;)
