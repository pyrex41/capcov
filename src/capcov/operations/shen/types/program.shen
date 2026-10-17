(datatype capop-program
  if (<= (length (capop.value As)) 64)
  if (capop.unique? (map (/. A (nth 2 A)) (capop.value As)))
  N : string; T : string; F : string; V : string;
  As : capop-actions;
  ______________________
  [operation N [live T F V] As] : capop-program;)
