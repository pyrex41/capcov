\\ Closed first-order effect programs. No source eval, FFI or arbitrary callbacks.
\\ Object-language typing checks all nodes, including unreachable ones.
(tc -)

(datatype bf-phase
  ______________________
  "route" : bf-phase;
  ______________________
  "worker" : bf-phase;)

(datatype bf-permission
  P : bf-phase;
  ______________________
  [P "Ask"] : bf-permission;
  P : bf-phase;
  ______________________
  [P "Commit"] : bf-permission;
  ______________________
  ["worker" "External"] : bf-permission;)

(define bf.permission?
  P K -> (trap-error
    (= bf-permission (shen.typecheck (capop.syntax [P K]) bf-permission))
    (/. E false)))

(define bf.lookup
  K [[K | V] | _] -> V
  K [_ | Xs] -> (bf.lookup K Xs)
  K [] -> (error "behavior: unknown name ~A" K))

(define bf.keys
  Xs -> (map (function hd) Xs))

(define bf.same-set?
  X Y -> (and (capop.unique? X) (and (capop.unique? Y)
    (and (capop.all? (/. A (element? A Y)) X)
         (capop.all? (/. A (element? A X)) Y)))))

(define bf.expression?
  ["literal" X] -> (string? X)
  ["ref" X] -> (string? X)
  _ -> false)

(define bf.inputs?
  Xs -> (and (capop.unique? (bf.keys Xs))
    (capop.all? (/. X (and (= (length X) 2)
      (and (string? (hd X)) (bf.expression? (hd (tl X)))))) Xs)))

(define bf.node?
  Phase Row Ops Ids [Id Kind Op Inputs Next] ->
    (and (bf.inputs? Inputs)
      (if (element? Kind ["Done" "Failed"])
          (and (= Op "") (= Next []))
          (and (bf.permission? Phase Kind)
            (and (element? Op Row)
              (let Def (bf.lookup Op Ops)
                (and (= Kind (nth 1 Def))
                  (and (bf.same-set? (bf.keys Inputs) (nth 2 Def))
                    (and (bf.same-set? (bf.keys Next) (bf.keys (nth 3 Def)))
                      (capop.all? (/. N (element? (nth 2 N) Ids)) Next)))))))))
  _ _ _ _ _ -> false)

(define bf.closed?
  [Phase Row Ops Nodes Entry] ->
    (let Ids (bf.keys Nodes)
      (and (capop.unique? Ids)
        (and (element? Entry Ids)
          (and (capop.unique? Row)
            (and (capop.unique? (bf.keys Ops))
              (and (capop.all? (/. R (and (element? R (bf.keys Ops))
                     (bf.permission? Phase (nth 1 (bf.lookup R Ops))))) Row)
                (capop.all? (/. N (bf.node? Phase Row Ops Ids N)) Nodes)))))))
  _ -> false)

(datatype bf-program
  if (element? Phase ["route" "worker"])
  if (bf.closed? [Phase (capop.value Row) (capop.value Ops) (capop.value Nodes) Entry])
  ______________________
  [Phase Row Ops Nodes Entry] : bf-program;)

(define bf.admit?
  P -> (trap-error (= bf-program (shen.typecheck (capop.syntax P) bf-program))
                  (/. E false)))

(define bf.eval
  ["literal" X] _ -> X
  ["ref" K] Env -> (hd (bf.lookup K Env)))

(define bf.advance
  [Phase Row Ops Nodes Entry] PC Env ->
    (let N (bf.lookup PC Nodes)
      [(nth 1 N) (nth 2 N)
       (map (/. I [(hd I) (bf.eval (nth 2 I) Env)]) (nth 3 N))]))

(define bf.resume
  [_ _ _ Nodes _] PC Outcome ->
    (hd (bf.lookup Outcome (nth 4 (bf.lookup PC Nodes)))))
