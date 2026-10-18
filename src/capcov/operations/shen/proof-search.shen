\\ Invertible sequent search. Kernel checking is in a separate library.
(tc -)
(define cv.compound
  [] -> []
  [["atom" _] | Xs] -> (cv.compound Xs)
  [X | _] -> X)

(define cv.common
  [] _ -> []
  [X | _] R -> X where (element? X R)
  [_ | Xs] R -> (cv.common Xs R))

(define cv.unary
  Rule ["proved" D] -> ["proved" (append Rule [D])]
  _ Failure -> Failure)

(define cv.binary
  Rule ["proved" D] ["proved" E] -> ["proved" (append Rule [D E])]
  _ ["countermodel" L R] _ -> ["countermodel" L R]
  _ _ Failure -> Failure)

(define cv.search
  _ _ 0 -> (error "proof: search depth exhausted")
  L R N -> (let Common (cv.common L R)
    (if (not (= Common [])) ["proved" ["identity" Common]]
      (if (element? ["false"] L) ["proved" ["false-left"]]
        (if (element? ["true"] R) ["proved" ["true-right"]]
          (cv.focus (cv.compound L) (cv.compound R) L R (- N 1)))))))

(define cv.focus
  ["true"] _ L R N -> (cv.unary ["true-left"] (cv.search (cv.remove ["true"] L) R N))
  ["not" P] _ L R N -> (cv.unary ["not-left" P] (cv.search (cv.remove ["not" P] L) [P | R] N))
  ["and" P Q] _ L R N -> (cv.unary ["and-left" P Q] (cv.search [P Q | (cv.remove ["and" P Q] L)] R N))
  ["or" P Q] _ L R N ->
    (cv.binary ["or-left" P Q]
      (cv.search [P | (cv.remove ["or" P Q] L)] R N)
      (cv.search [Q | (cv.remove ["or" P Q] L)] R N))
  [] ["false"] L R N -> (cv.unary ["false-right"] (cv.search L (cv.remove ["false"] R) N))
  [] ["not" P] L R N -> (cv.unary ["not-right" P] (cv.search [P | L] (cv.remove ["not" P] R) N))
  [] ["or" P Q] L R N -> (cv.unary ["or-right" P Q] (cv.search L [P Q | (cv.remove ["or" P Q] R)] N))
  [] ["and" P Q] L R N ->
    (cv.binary ["and-right" P Q]
      (cv.search L [P | (cv.remove ["and" P Q] R)] N)
      (cv.search L [Q | (cv.remove ["and" P Q] R)] N))
  [] [] L R _ -> ["countermodel" L R])

(define cv.prove
  L R -> (if (and (capop.all? (function cv.formula?) L) (capop.all? (function cv.formula?) R))
    (let Answer (cv.search L R 128)
      (if (= (hd Answer) "proved")
        (if (cv.checked? L R (nth 2 Answer)) Answer (error "proof: kernel rejected search result"))
        Answer))
    (error "proof: malformed formula")))
