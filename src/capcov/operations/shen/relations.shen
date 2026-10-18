\\ Finite relational plans: mode/cardinality checking and Prolog execution.
(tc -)
(define cr.bound
  X B -> (if (element? X B) true (error "mode: input is not ground")))
(define cr.cap
  N -> (if (> N 1) 2 N))
(define cr.intersection
  Xs Ys -> (capop.filter (/. X (element? X Ys)) Xs))
(define cr.mode
  ["literal" X _] B C -> [(capop.union [X] B) C (if (element? X B) 0 1) 1]
  ["domain" X Vs] B C -> [(capop.union [X] B) C (if (element? X B) 0 (cr.cap (length Vs))) (if (element? X B) 1 (cr.cap (length Vs)))]
  ["equal" X Y] B C ->
    (if (or (element? X B) (element? Y B))
      [(capop.union [X Y] B) C (if (and (element? X B) (element? Y B)) 0 1) 1]
      (error "mode: equality needs a ground operand"))
  ["less" X Y] B C -> (do (cr.bound X B) (do (cr.bound Y B) [B C 0 1]))
  ["add" X Y Z] B C -> (do (cr.bound X B) (do (cr.bound Y B)
    [(capop.union [Z] B) C (if (element? Z B) 0 1) 1]))
  ["consume" X] B C ->
    (if (element? X C) [B (cv.remove X C) 1 1] (error "mode: capability missing or consumed twice"))
  ["all" Goals] B C -> (cr.sequence Goals [B C 1 1])
  ["any" []] B C -> [B C 0 0]
  ["any" [G | Gs]] B C -> (cr.branches Gs B C (cr.mode G B C)))
(define cr.sequence
  [] Acc -> Acc
  [G | Gs] [B C Min Max] ->
    (let R (cr.mode G B C)
      (cr.sequence Gs [(hd R) (nth 2 R) (cr.cap (* Min (nth 3 R))) (cr.cap (* Max (nth 4 R)))])))
(define cr.branches
  [] _ _ Acc -> Acc
  [G | Gs] B C [Out Caps Min Max] ->
    (let R (cr.mode G B C)
      (if (= (caps.sorted Caps) (caps.sorted (nth 2 R)))
        (cr.branches Gs B C [(cr.intersection Out (hd R)) Caps (cr.cap (+ Min (nth 3 R))) (cr.cap (+ Max (nth 4 R)))])
        (error "mode: branches leave different capabilities"))))
(define cr.declared?
  "det" Min Max -> (and (= Min 1) (= Max 1))
  "semidet" _ Max -> (<= Max 1)
  "multi" Min _ -> (> Min 0)
  "nondet" _ _ -> true)
(define cr.compile
  Body Inputs Outputs Caps Det ->
    (let R (cr.mode Body Inputs Caps)
      (if (and (capop.all? (/. X (element? X (hd R))) Outputs)
               (cr.declared? Det (nth 3 R) (nth 4 R))) R
          (error "mode: output not ground or determinism declaration too strong"))))
(define cr.assign
  X V E -> (let Old (capop.get X E)
    (if (= Old capop.absent) [[X V] | E] (if (= Old V) E false))))
(define cr.equal
  X Y E -> (let A (capop.get X E) B (capop.get Y E)
    (if (= A capop.absent) (cr.assign X B E) (cr.assign Y A E))))

(defprolog cr.solve
  ["literal" X V] E C Out C <-- (when (cv.tick)) (is Out (cr.assign X V E)) (when (not (= Out false)));
  ["domain" X Vs] E C Out C <-- (when (cv.tick)) (capop.member V Vs) (is Out (cr.assign X V E)) (when (not (= Out false)));
  ["equal" X Y] E C Out C <-- (when (cv.tick)) (is Out (cr.equal X Y E)) (when (not (= Out false)));
  ["less" X Y] E C E C <-- (when (cv.tick)) (when (< (caps.integer (caps.lookup X E)) (caps.integer (caps.lookup Y E))));
  ["add" X Y Z] E C Out C <-- (when (cv.tick))
    (is V (caps.int-result (+ (caps.integer (caps.lookup X E)) (caps.integer (caps.lookup Y E)))))
    (is Out (cr.assign Z V E)) (when (not (= Out false)));
  ["consume" X] E C E Out <-- (when (cv.tick)) (when (element? X C)) (is Out (cv.remove X C));
  ["all" Gs] E C Out Remaining <-- (cr.solve-all Gs E C Out Remaining);
  ["any" Gs] E C Out Remaining <-- (when (cv.tick)) (capop.member G Gs) (cr.solve G E C Out Remaining);)
(defprolog cr.solve-all
  [] E C E C <--;
  [G | Gs] E C Out Remaining <-- (cr.solve G E C Next Caps) (cr.solve-all Gs Next Caps Out Remaining);)
(define cr.run
  Body Inputs Outputs Caps Det Env Budget ->
    (do (cr.compile Body Inputs Outputs Caps Det)
      (do (set cv.search-budget Budget)
        (reverse (prolog? (findall [Out Remaining]
          (cr.solve (receive Body) (receive Env) (receive Caps) Out Remaining) Results) (return Results))))))
