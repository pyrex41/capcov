(datatype caps-expr
  V : string;
  ______________________
  [literal V] : caps-expr;
  K : string;
  ______________________
  [argument K] : caps-expr;
  ______________________
  [row-key] : caps-expr;
  F : string;
  ______________________
  [row-field F] : caps-expr;
  T : string; K : caps-expr; F : string;
  ______________________
  [lookup T K F] : caps-expr;)

(datatype caps-pred
  ______________________
  [yes] : caps-pred;
  ______________________
  [no] : caps-pred;
  X : caps-expr; Y : caps-expr;
  ______________________
  [equal X Y] : caps-pred;
  P : caps-pred;
  ______________________
  [negate P] : caps-pred;
  P : caps-pred; Q : caps-pred;
  ______________________
  [both P Q] : caps-pred;
  P : caps-pred; Q : caps-pred;
  ______________________
  [either P Q] : caps-pred;
  T : string; K : caps-expr;
  ______________________
  [exists T K] : caps-pred;
  T : string; P : caps-pred;
  ______________________
  [some-row T P] : caps-pred;
  T : string; P : caps-pred;
  ______________________
  [every-row T P] : caps-pred;)

(datatype caps-field
  F : string; X : caps-expr;
  ______________________
  [F X] : caps-field;)

(datatype caps-action
  T : string; K : caps-expr; Fs : caps-fields;
  ______________________
  [insert T K Fs] : caps-action;
  T : string; K : caps-expr; F : string; V : caps-expr;
  ______________________
  [update T K F V] : caps-action;
  T : string; K : caps-expr;
  ______________________
  [remove T K] : caps-action;
  Kind : string; V : caps-expr;
  ______________________
  [publish Kind V] : caps-action;
  Label : string; P : caps-pred;
  ______________________
  [require Label P] : caps-action;
  P : caps-pred; As : caps-actions; Bs : caps-actions;
  ______________________
  [choose P As Bs] : caps-action;
  T : string; P : caps-pred; As : caps-actions;
  ______________________
  [for-each T P As] : caps-action;)

(datatype caps-named
  N : string; A : caps-action;
  ______________________
  [named N A] : caps-named;)

(datatype caps-foreign
  F : string; T : string;
  ______________________
  [foreign F T] : caps-foreign;)

(datatype caps-table
  T : string; Fs : caps-columns; Us : (list string); Fks : caps-foreigns;
  ______________________
  [table T Fs Us Fks] : caps-table;)

(datatype caps-command
  N : string; Args : (list string); Pre : caps-pred; As : caps-actions; Post : caps-pred;
  ______________________
  [command N Args Pre As Post] : caps-command;)

(datatype caps-invariant
  N : string; P : caps-pred;
  ______________________
  [N P] : caps-invariant;)

(datatype caps-system-shape
  N : string; Ts : caps-tables; Cs : caps-commands; Ps : caps-invariants;
  ______________________
  [system N Ts Cs Ps] : caps-system-shape;)

(datatype caps-fields
  ______________________
  [] : caps-fields;
  X : caps-field; Xs : caps-fields;
  ______________________
  (cons X Xs) : caps-fields;)

(datatype caps-actions
  ______________________
  [] : caps-actions;
  X : caps-named; Xs : caps-actions;
  ______________________
  (cons X Xs) : caps-actions;)

(datatype caps-foreigns
  ______________________
  [] : caps-foreigns;
  X : caps-foreign; Xs : caps-foreigns;
  ______________________
  (cons X Xs) : caps-foreigns;)

(datatype caps-tables
  ______________________
  [] : caps-tables;
  X : caps-table; Xs : caps-tables;
  ______________________
  (cons X Xs) : caps-tables;)

(datatype caps-commands
  ______________________
  [] : caps-commands;
  X : caps-command; Xs : caps-commands;
  ______________________
  (cons X Xs) : caps-commands;)

(datatype caps-invariants
  ______________________
  [] : caps-invariants;
  X : caps-invariant; Xs : caps-invariants;
  ______________________
  (cons X Xs) : caps-invariants;)

(datatype caps-system
  if (caps.scoped? (capop.value M))
  M : caps-system-shape;
  ______________________
  M : caps-system;)

(datatype caps-columns
  ______________________
  [] : caps-columns;
  X : caps-column; Xs : caps-columns;
  ______________________
  (cons X Xs) : caps-columns;)

(datatype caps-column
  F : string;
  ______________________
  F : caps-column;
  F : string;
  ______________________
  [column F [text]] : caps-column;
  F : string;
  ______________________
  [column F [int32]] : caps-column;
  Vs : (list string); F : string;
  ______________________
  [column F [enum Vs]] : caps-column;)

(datatype caps-expr-arithmetic
  X : caps-expr; Y : caps-expr;
  ______________________
  [int-add X Y] : caps-expr;
  X : caps-expr; Y : caps-expr;
  ______________________
  [int-sub X Y] : caps-expr;)

(datatype caps-pred-arithmetic
  X : caps-expr; Y : caps-expr;
  ______________________
  [less-than X Y] : caps-pred;)

(datatype caps-expr-state
  X : caps-expr;
  ______________________
  [before X] : caps-expr;
  T : string;
  ______________________
  [count-rows T] : caps-expr;
  T : string; F : string;
  ______________________
  [sum-field T F] : caps-expr;)
