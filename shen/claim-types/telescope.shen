\* The typed claim IR and its judgement context.

   A unit is a telescope of binders ending in [cc.goal Rule]:

     [cc.let-sort X T K]       [cc.uvar X] : (cc-sort T)          for the rest
     [cc.let-capabilities L K] cc.capabilities : (cc-capabilities L)
     [cc.let-bridges L K]      cc.bridges : (cc-bridges L)
     [cc.goal G]               G is checked against the unit's sort C

   Rule syntax (reified from the elaborated pack by typed-authority.shen):

     Rule  [cc.rule Name Body [cc.head Ref Terms]]
     Body  [[cc.occ I Item] ...]           I is the source premise position
     Item  [cc.pos Ref Terms] | [cc.neg Ref Terms] | [cc.cmp Term Op Term]
     Term  [cc.uvar X]                     a unification variable (source name X)
           | [cc.const Value Tag]          a constant with its type tag or capcov.null
     Ref   [cc.rel Name Decl Class Component]   a RESOLVED relation name
     Decl  cc.undeclared
           | [cc.sig Modality Binding Columns Context Completes LegacyTargets Scope]
     Columns [[cc.col Name Type ContextFlag] ...]
     Scope cc.unscoped | [cc.scope Target Mapping TargetDecl]
     Class cc.assumption | cc.evidence     (pack-level assumption projection)
     Component cc.own | cc.other           (in the head's recursive SCC?)

   Three name spaces stay distinct: source names (relations, columns,
   dimensions) are strings inside Ref/columns; unification variables are
   [cc.uvar X] terms, sorted by cc-sort hypotheses; BOUND variables are the
   cc-bound hypotheses only cc-bind introduces, for positive premises.  A
   variable spelled like a relation never meets that relation's data.

   Context is passed as hypotheses only where it is genuinely scoped
   (binding, sorts) or pack-wide and small (capabilities, bridges); a
   declaration travels with its reference.  Measured on shen-go c12933d, a
   goal costs inferences linear in the hypotheses in scope, so a hypothesis
   per relation made every pack-sized unit quadratic. *\
(datatype cc-telescope
  [cc.uvar X] : (cc-sort T) >> K : (cc-judged C);
  ______________________
  [cc.let-sort X T K] : (cc-judged C);

  cc.capabilities : (cc-capabilities L) >> K : (cc-judged C);
  ______________________
  [cc.let-capabilities L K] : (cc-judged C);

  cc.bridges : (cc-bridges L) >> K : (cc-judged C);
  ______________________
  [cc.let-bridges L K] : (cc-judged C);

  G : C;
  ______________________
  [cc.goal G] : (cc-judged C);)
