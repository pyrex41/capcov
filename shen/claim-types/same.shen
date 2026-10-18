\* Exact positional identity of two typed positions (schema-v2 semantics,
   evidence-authority-v2.shen capcov.v2-same?): equal column types and
   either the same unification variable, or equal constants whose own type
   tag is that column type.  An untyped constant is never the same as
   anything, so it cannot authorize or carry a context. *\
(datatype cc-same
  if (cc.eq? Ty1 Ty2) if (cc.eq? X Y)
  ______________________
  [cc.same [cc.arg N1 Ty1 [cc.uvar X]] [cc.arg N2 Ty2 [cc.uvar Y]]] : cc-same;

  if (cc.eq? Ty1 Ty2) if (cc.eq? Ty1 D1) if (cc.eq? Ty1 D2) if (cc.eq? V1 V2)
  ______________________
  [cc.same [cc.arg N1 Ty1 [cc.const V1 D1]] [cc.arg N2 Ty2 [cc.const V2 D2]]] : cc-same;)
