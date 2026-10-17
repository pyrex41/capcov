\\ Finite-list loop induction: invariant preserved by an arbitrary captured
\\ row, and sufficient at the empty-list case. WP and universal instances are
\\ regenerated from the model by the separately identified trusted compiler.
(tc -)
(define cl.loop
  Premises I BodyWP Post Step Exit ->
    (and (element? I Premises)
      (and (cv.checked? Premises [BodyWP] Step)
           (cv.checked? [I] [Post] Exit))))

\\ Frame premise of partition induction: a step only updates its own unique
\\ snapshot key. No row creation/deletion, cross-key writes or nested loops.
(define cl.local-action?
  T ["update" T ["row-key"] _ _] -> true
  _ ["publish" _ _] -> true
  _ ["require" _ _] -> true
  T ["choose" _ As Bs] -> (and (cl.local-actions? T As) (cl.local-actions? T Bs))
  _ _ -> false)

(define cl.local-actions?
  _ [] -> true
  T [["named" _ A] | As] -> (and (cl.local-action? T A) (cl.local-actions? T As))
  _ _ -> false)

(define cl.completed
  ["snapshot-partition" I Q L W Post] T As Premises BodyWP Preserve Complete Exit ->
    (and (cl.partition-typechecks? ["snapshot-partition" I Q L W Post])
      (and (cl.local-actions? T As)
        (and (element? I Premises)
          (and (cv.checked? Premises [BodyWP] Preserve)
            (and (cv.checked? L [W] Complete)
                 (cv.checked? [I Q] [Post] Exit))))))
  _ _ _ _ _ _ _ _ -> false)
