\\ Datatypes for the completion judgment, not a claim that the authority
\\ workbench or the semantic proof-checking functions have been typechecked.
(datatype cl-formula
  X : string;
  ______________________
  ["atom" X] : cl-formula;
  ______________________
  ["true"] : cl-formula;
  ______________________
  ["false"] : cl-formula;
  P : cl-formula;
  ______________________
  ["not" P] : cl-formula;
  P : cl-formula; Q : cl-formula;
  ______________________
  ["and" P Q] : cl-formula;
  P : cl-formula; Q : cl-formula;
  ______________________
  ["or" P Q] : cl-formula;)

(datatype cl-context
  ______________________
  [] : cl-context;
  P : cl-formula; Ps : cl-context;
  ______________________
  [P | Ps] : cl-context;)

(datatype cl-partition
  I : cl-formula; Q : cl-formula; L : cl-context;
  W : cl-formula; Post : cl-formula;
  ______________________
  ["snapshot-partition" I Q L W Post] : cl-partition;)

(tc -)
(define cl.partition-typechecks?
  J -> (= cl-partition (shen.typecheck (capop.syntax J) cl-partition)))
