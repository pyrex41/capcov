\\ Ground finite domains, explicit choices, Prolog-generated command histories.
(tc -)
(define cv.tick
  -> (let N (value cv.search-budget)
    (if (> N 0) (do (set cv.search-budget (- N 1)) true)
      (error "search: transition budget exhausted"))))

(define cv.indexed
  [] _ -> []
  [X | Xs] N -> [[(str N) X] | (cv.indexed Xs (+ N 1))])

(define cv.emit-count
  _ [] -> 0
  K [[emit K _] | Es] -> (+ 1 (cv.emit-count K Es))
  K [_ | Es] -> (cv.emit-count K Es))

(define cv.goal?
  ["state" P] S _ -> (caps.pred P [] [] S)
  ["emitted" K N] _ Es -> (>= (cv.emit-count K Es) N)
  ["violation"] _ _ -> false)

(defprolog cv.path
  M S Calls Goal 0 Fuel Es [] <-- (when (cv.goal? Goal S Es));
  M S Calls ["violation"] 1 Fuel Es [[C "violation" R]] <--
    (capop.member C Calls) (when (cv.tick))
    (is R (caps.run M (hd C) (nth 2 C) S Fuel))
    (when (= R [rejected invariant]));
  M S Calls Goal N Fuel Es [[C I R] | Path] <--
    (when (> N 0)) (capop.member C Calls) (when (cv.tick))
    (is Result (caps.run M (hd C) (nth 2 C) S Fuel))
    (is Choices (cv.indexed (caps.admissible S Result (nth 3 C)) 0))
    (capop.member [I R] Choices)
    (is Next (nth 2 R)) (is Events (append Es (nth 3 R))) (is Less (- N 1))
    (cv.path M Next Calls Goal Less Fuel Events Path);)

(define cv.find-depth
  _ _ _ _ N Max _ -> ["exhausted"] where (> N Max)
  M S Calls Goal N Max Fuel ->
    (let Found (prolog? (cv.path (receive M) (receive S) (receive Calls) (receive Goal)
                                (receive N) (receive Fuel) [] Path) (return Path))
      (if (= Found false) (cv.find-depth M S Calls Goal (+ N 1) Max Fuel)
          ["witness" Found])))

(define cv.find
  M S Calls Goal Max Fuel Budget ->
    (if (and (caps.typechecks? M) (and (caps.state-ok? M S) (caps.invariants? M S)))
      (do (set cv.search-budget Budget) (cv.find-depth M S Calls Goal 0 Max Fuel))
      (error "search: invalid model or initial state")))
