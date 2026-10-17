(datatype capop-action
  T : string; F : string;
  ______________________
  [delete-related T F] : capop-action;

  T : string; F : string; V : string;
  ______________________
  [set-target T F V] : capop-action;

  T : string; F : string; K : string; E : string;
  ______________________
  [emit-related T F K E] : capop-action;

  E : string;
  ______________________
  [emit-target E] : capop-action;)
