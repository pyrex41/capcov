\\ Finite-list loop induction: invariant preserved by an arbitrary captured
\\ row, and sufficient at the empty-list case. WP and universal instances are
\\ regenerated from the model by the separately identified trusted compiler.
(tc -)
(define cl.loop
  Premises I BodyWP Post Step Exit ->
    (and (element? I Premises)
      (and (cv.checked? Premises [BodyWP] Step)
           (cv.checked? [I] [Post] Exit))))
