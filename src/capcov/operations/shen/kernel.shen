\\ Pure, bounded operation semantics. No host effects or evidence admission.
(tc -)

(define capop.all?
  F [] -> true
  F [X | Xs] -> (and (F X) (capop.all? F Xs))
  _ _ -> false)

(define capop.unique?
  [] -> true
  [X | Xs] -> (and (not (element? X Xs)) (capop.unique? Xs))
  _ -> false)

(define capop.value
  [] -> []
  [cons X Xs] -> [(capop.value X) | (capop.value Xs)]
  X -> X)

(define capop.fields?
  Fs -> (and (capop.all? (function capop.field?) Fs)
             (capop.unique? (map (function hd) Fs))))

(define capop.field?
  [K V] -> (and (string? K) (string? V))
  _ -> false)

(define capop.row?
  [row T K Fs] -> (and (string? T) (and (string? K) (capop.fields? Fs)))
  _ -> false)

(define capop.state?
  S -> (and (capop.all? (function capop.row?) S)
            (and (<= (length S) 256)
                 (capop.unique? (map (/. R [(nth 2 R) (nth 3 R)]) S)))))

(define capop.get
  _ [] -> capop.absent
  F [[F V] | _] -> V
  F [_ | Fs] -> (capop.get F Fs))

(define capop.find
  _ _ [] -> capop.absent
  T K [[row T K Fs] | _] -> Fs
  T K [_ | Rs] -> (capop.find T K Rs))

(define capop.string-before?
  "" "" -> false
  "" _ -> true
  _ "" -> false
  X Y -> (if (= (pos X 0) (pos Y 0))
             (capop.string-before? (tlstr X) (tlstr Y))
             (< (string->n (pos X 0)) (string->n (pos Y 0)))))

(define capop.set-field
  F V [] -> [[F V]]
  F V [[F _] | Fs] -> [[F V] | Fs]
  F V [[K W] | Fs] -> [[F V] [K W] | Fs] where (capop.string-before? F K)
  F V [P | Fs] -> [P | (capop.set-field F V Fs)])

(define capop.filter
  _ [] -> []
  F [X | Xs] -> [X | (capop.filter F Xs)] where (F X)
  F [_ | Xs] -> (capop.filter F Xs))

(define capop.related?
  T F I [row T _ Fs] -> (= I (capop.get F Fs))
  _ _ _ _ -> false)

(define capop.related
  T F I S -> (capop.filter (/. R (capop.related? T F I R)) S))

\\ Each instruction emits effects; only the effect interpreter changes state.
(define capop.effects
  [delete-related T F] I S ->
    (map (/. R [delete T (nth 3 R)]) (capop.related T F I S))
  [set-target T F V] I S -> [[put T I F V]]
  [emit-related T F K Event] I S ->
    (map (/. R (let V (capop.get K (nth 4 R))
                 (if (= V capop.absent) (error "operation: missing event key") [emit Event V])))
         (capop.related T F I S))
  [emit-target Event] I _ -> [[emit Event I]])

(define capop.apply-one
  [delete T K] S -> (capop.filter (/. R (not (= [T K] [(nth 2 R) (nth 3 R)]))) S)
  [put T K F V] S ->
    (if (= (capop.find T K S) capop.absent)
        (error "operation: target does not exist")
        (map (/. R (if (= [T K] [(nth 2 R) (nth 3 R)])
                      [row T K (capop.set-field F V (nth 4 R))] R)) S))
  [emit _ _] S -> S)

(define capop.apply
  [] S -> S
  [E | Es] S -> (capop.apply Es (capop.apply-one E S)))

(define capop.execute
  [] _ S Effects Trace -> [result S Effects (reverse Trace)]
  [[named Name Action] | As] I S Effects Trace ->
    (let Es (capop.effects Action I S)
      (capop.execute As I (capop.apply Es S) (append Effects Es)
                     [[action Name Es] | Trace])))

\\ Construction authority is the sequent datatype, not a duplicate validator.
(define capop.program?
  P -> (capop.typechecks? P))

\\ Variants may only omit named instructions, with a nonempty divergence id.
(define capop.variant?
  intended _ -> true
  [omit Reason Names] [operation _ _ As] ->
    (and (string? Reason) (and (not (= Reason ""))
     (and (capop.all? (function string?) Names)
      (and (capop.unique? Names)
           (capop.all? (/. N (element? N (map (/. A (nth 2 A)) As))) Names)))))
  _ _ -> false)

(define capop.actions
  [operation _ _ As] intended -> As
  [operation _ _ As] [omit _ Names] ->
    (capop.filter (/. A (not (element? (nth 2 A) Names))) As))

(define capop.require
  P V S I -> (if (and (capop.program? P)
                     (and (capop.variant? V P) (and (capop.state? S) (string? I))))
                 true (error "operation: invalid program, variant, state or target")))

(define capop.live?
  [operation _ [live T F V] _] S I ->
    (let Fs (capop.find T I S)
      (and (not (= Fs capop.absent)) (= V (capop.get F Fs)))))

(define capop.run
  P V S I -> (do (capop.require P V S I)
                 (if (capop.live? P S I)
                     (capop.execute (capop.actions P V) I S [] [])
                     [refused nonlive])))

\\ Outcome interpretation assumes atomic commit of this modeled effect batch.
\\ Unknown retains alternatives; it is never silently counted as committed.
(define capop.admissible
  P V S I Out ->
    (do (capop.require P V S I)
        (cond ((= Out aborted) [[result S [] []]])
              ((= Out committed) (let R (capop.run P V S I)
                                   (if (= R [refused nonlive]) [] [R])))
              ((= Out unknown) (let R (capop.run P V S I)
                                 (if (or (= R [refused nonlive]) (= R [result S [] []]))
                                     [[result S [] []]] [[result S [] []] R])))
              (true (error "operation: unsupported outcome")))))

\\ Prolog searches only the finite alternatives supplied by the semantics.
(defprolog capop.member
  X [X | _] <--;
  X [_ | Xs] <-- (capop.member X Xs);)

(define capop.accepts?
  P V S I Out After Effects ->
    (let Alternatives (capop.admissible P V S I Out)
      (prolog? (capop.member [result (receive After) (receive Effects) Trace]
                            (receive Alternatives)))))

\\ A trace is checked against the trusted program, variant, input and pre-state.
(define capop.check-trace?
  P V S I [result After Effects Trace] -> (= [result After Effects Trace] (capop.run P V S I))
  _ _ _ _ _ -> false)

(define capop.action-writes
  [delete-related T _] -> [T]
  [set-target T _ _] -> [T]
  _ -> [])

(define capop.action-reads
  [delete-related T _] -> [T]
  [set-target T _ _] -> [T]
  [emit-related T _ _ _] -> [T]
  _ -> [])

(define capop.action-emits
  [emit-related _ _ _ E] -> [E]
  [emit-target E] -> [E]
  _ -> [])

(define capop.union
  [] Ys -> Ys
  [X | Xs] Ys -> (capop.union Xs (if (element? X Ys) Ys (append Ys [X]))))

(define capop.fold-summary
  _ [] Acc -> Acc
  F [[named _ A] | As] Acc -> (capop.fold-summary F As (capop.union (F A) Acc)))

(define capop.analyze
  P V -> (if (and (capop.program? P) (capop.variant? V P))
           (let As (capop.actions P V)
             [summary [reads (capop.fold-summary (function capop.action-reads) As [(nth 2 (nth 3 P))])]
                      [may-write (capop.fold-summary (function capop.action-writes) As [])]
                      [may-emit (capop.fold-summary (function capop.action-emits) As [])]])
           (error "operation: invalid program or variant")))

\\ Reify a value as constructor syntax for the actual Shen type checker.
(define capop.syntax
  [] -> []
  [X | Xs] -> [cons (capop.syntax X) (capop.syntax Xs)]
  X -> X)

(define capop.typechecks?
  P -> (= capop-program (shen.typecheck (capop.syntax P) capop-program)))

\\ Transport helpers. They cannot execute an instruction or admit evidence.
(define capop.string
  [] -> ""
  [N | Ns] -> (cn (n->string N) (capop.string Ns)))

(define capop.json-escape
  "" -> ""
  S -> (let C (pos S 0) N (string->n C) B (n->string 92)
         (cn (cond ((= N 34) (cn B C))
                   ((= N 92) (cn B B))
                   ((< N 32) (cn B (cn "u00" (cn (pos "0123456789abcdef" (div N 16))
                                                     (pos "0123456789abcdef" (mod N 16))))))
                   (true C))
             (capop.json-escape (tlstr S)))))

(define capop.json-items
  [] -> ""
  [X] -> (capop.json X)
  [X | Xs] -> (cn (capop.json X) (cn "," (capop.json-items Xs))))

(define capop.json
  true -> "true"
  false -> "false"
  not-requested -> "null"
  [] -> "[]"
  [X | Xs] -> (cn "[" (cn (capop.json-items [X | Xs]) "]"))
  X -> (cn (n->string 34) (cn (capop.json-escape X) (n->string 34))) where (string? X)
  X -> (capop.json (str X)))

(define capop.print-result
  X -> (output "~%CAPCOV-OPERATION-RESULT ~A~%" (capop.json X)))

(define capop.observable
  [result S E _] -> [observed S E]
  R -> R)

(defprolog capop.disagreement
  P V W States I Witness <--
    (capop.member S States)
    (is A (capop.run P V S I))
    (is B (capop.run P W S I))
    (when (not (= (capop.observable A) (capop.observable B))))
    (is Witness [counterexample S A B]);)

(define capop.find-disagreement
  P V W States I ->
    (if (and (<= (length States) 16)
             (and (capop.program? P)
              (and (capop.variant? V P) (and (capop.variant? W P)
               (and (string? I) (capop.all? (function capop.state?) States))))))
        (prolog? (capop.disagreement (receive P) (receive V) (receive W)
                                    (receive States) (receive I) Witness)
                 (return Witness))
        (error "operation: invalid or oversized search domain")))
