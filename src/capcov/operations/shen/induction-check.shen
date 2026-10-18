\\ Safety induction over all finite transition histories; no search dependency.
(tc -)
(define ci.prime
  ["atom" X] -> ["atom" (cn "next:" X)]
  ["not" P] -> ["not" (ci.prime P)]
  ["and" P Q] -> ["and" (ci.prime P) (ci.prime Q)]
  ["or" P Q] -> ["or" (ci.prime P) (ci.prime Q)]
  ["true"] -> ["true"]
  ["false"] -> ["false"])

(define ci.steps
  _ [] [] -> true
  I [T | Ts] [D | Ds] ->
    (and (cv.checked? [I T] [(ci.prime I)] D) (ci.steps I Ts Ds))
  _ _ _ -> false)

(define ci.check
  Init I Safe Transitions [Base Safety | Steps] ->
    (and (cv.checked? [Init] [I] Base)
      (and (cv.checked? [I] [Safe] Safety) (ci.steps I Transitions Steps)))
  _ _ _ _ _ -> false)
