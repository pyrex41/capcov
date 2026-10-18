\\ Classical propositional sequent kernel. No proof search or model evaluator.
\\ A sequent L |- R means conjunction(L) implies disjunction(R).
(tc -)

(define cv.remove
  X [X | Xs] -> Xs
  X [Y | Ys] -> [Y | (cv.remove X Ys)]
  _ [] -> (error "proof: principal formula absent"))

(define cv.formula?
  ["atom" X] -> (string? X)
  ["true"] -> true
  ["false"] -> true
  ["not" P] -> (cv.formula? P)
  ["and" P Q] -> (and (cv.formula? P) (cv.formula? Q))
  ["or" P Q] -> (and (cv.formula? P) (cv.formula? Q))
  _ -> false)

(define cv.check
  _ _ _ 0 -> false
  L R ["identity" P] _ -> (and (element? P L) (element? P R))
  L _ ["false-left"] _ -> (element? ["false"] L)
  _ R ["true-right"] _ -> (element? ["true"] R)
  L R ["true-left" D] N ->
    (and (element? ["true"] L) (cv.check (cv.remove ["true"] L) R D (- N 1)))
  L R ["false-right" D] N ->
    (and (element? ["false"] R) (cv.check L (cv.remove ["false"] R) D (- N 1)))
  L R ["not-left" P D] N ->
    (and (element? ["not" P] L) (cv.check (cv.remove ["not" P] L) [P | R] D (- N 1)))
  L R ["not-right" P D] N ->
    (and (element? ["not" P] R) (cv.check [P | L] (cv.remove ["not" P] R) D (- N 1)))
  L R ["and-left" P Q D] N ->
    (and (element? ["and" P Q] L) (cv.check [P Q | (cv.remove ["and" P Q] L)] R D (- N 1)))
  L R ["or-right" P Q D] N ->
    (and (element? ["or" P Q] R) (cv.check L [P Q | (cv.remove ["or" P Q] R)] D (- N 1)))
  L R ["or-left" P Q D E] N ->
    (and (element? ["or" P Q] L)
      (and (cv.check [P | (cv.remove ["or" P Q] L)] R D (- N 1))
           (cv.check [Q | (cv.remove ["or" P Q] L)] R E (- N 1))))
  L R ["and-right" P Q D E] N ->
    (and (element? ["and" P Q] R)
      (and (cv.check L [P | (cv.remove ["and" P Q] R)] D (- N 1))
           (cv.check L [Q | (cv.remove ["and" P Q] R)] E (- N 1))))
  _ _ _ _ -> false)

(define cv.checked?
  L R D -> (and (capop.all? (function cv.formula?) L)
            (and (capop.all? (function cv.formula?) R) (cv.check L R D 128))))
