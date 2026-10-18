\* An occurrence's typed positions: [cc.zip Columns Terms] : (cc-args Args)
   pairs each term with its column, Args = [[cc.arg Name Type Term] ...].
   Only an exact arity has a derivation. *\
(datatype cc-zip
  ______________________
  [cc.zip [] []] : (cc-args []);

  [cc.zip Cs Ts] : (cc-args As);
  ______________________
  [cc.zip (cons [cc.col N Ty F] Cs) (cons T Ts)] : (cc-args (cons [cc.arg N Ty T] As));)
