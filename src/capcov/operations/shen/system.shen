\\ Compositional finite systems. All semantics run in Shen.
(tc -)

(define caps.lookup
  K Ps -> (let V (capop.get K Ps)
            (if (= V capop.absent) (error "system: unbound argument or field") V)))

(define caps.expr
  [before X] E R S -> (caps.expr X E R (caps.lookup caps.before E))
  [count-rows T] _ _ S -> (str (length (caps.rows T S)))
  [sum-field T F] _ _ S -> (caps.sum F (caps.rows T S) 0)
  [int-add X Y] E R S -> (caps.int-result (+ (caps.integer (caps.expr X E R S)) (caps.integer (caps.expr Y E R S))))
  [int-sub X Y] E R S -> (caps.int-result (- (caps.integer (caps.expr X E R S)) (caps.integer (caps.expr Y E R S))))
  [literal V] _ _ _ -> V
  [argument K] Env _ _ -> (caps.lookup K Env)
  [row-key] _ [row _ K _] _ -> K
  [row-field F] _ [row _ _ Fs] _ -> (caps.lookup F Fs)
  [lookup T K F] Env R S -> (let Fs (capop.find T (caps.expr K Env R S) S)
                            (if (= Fs capop.absent) (error "system: lookup row missing") (caps.lookup F Fs))))

(define caps.pred
  [less-than X Y] E R S -> (< (caps.integer (caps.expr X E R S)) (caps.integer (caps.expr Y E R S)))
  [yes] _ _ _ -> true
  [no] _ _ _ -> false
  [equal X Y] E R S -> (= (caps.expr X E R S) (caps.expr Y E R S))
  [negate P] E R S -> (not (caps.pred P E R S))
  [both P Q] E R S -> (and (caps.pred P E R S) (caps.pred Q E R S))
  [either P Q] E R S -> (or (caps.pred P E R S) (caps.pred Q E R S))
  [exists T K] E R S -> (not (= capop.absent (capop.find T (caps.expr K E R S) S)))
  [some-row T P] E _ S -> (not (= [] (caps.select T P E S)))
  [every-row T P] E _ S -> (capop.all? (/. R (caps.pred P E R S)) (caps.rows T S)))

(define caps.rows
  T S -> (capop.filter (/. R (= T (nth 2 R))) S))

(define caps.select
  T P E S -> (capop.filter (/. R (caps.pred P E R S)) (caps.rows T S)))

(define caps.fields
  [] _ _ _ -> []
  [[F X] | Xs] E R S -> [[F (caps.expr X E R S)] | (caps.fields Xs E R S)])

(define caps.sort-fields
  [] -> []
  [[F V] | Fs] -> (capop.set-field F V (caps.sort-fields Fs)))

(define caps.apply
  [create T K Fs] S -> (append S [[row T K (caps.sort-fields Fs)]])
  E S -> (capop.apply-one E S))

\\ A transaction carries intermediate state, ordered effects and named trace.
\\ Failure carries diagnostics only; its state/effects cannot escape commit.
(define caps.step
  [insert T K Fs] E R S ->
    (let Key (caps.expr K E R S)
      (if (= capop.absent (capop.find T Key S))
          [effects [[create T Key (caps.sort-fields (caps.fields Fs E R S))]]]
          [failed duplicate-key]))
  [update T K F X] E R S ->
    (let Key (caps.expr K E R S)
      (if (= capop.absent (capop.find T Key S)) [failed missing-row]
          [effects [[put T Key F (caps.expr X E R S)]]]))
  [remove T K] E R S ->
    (let Key (caps.expr K E R S)
      (if (= capop.absent (capop.find T Key S)) [failed missing-row]
          [effects [[delete T Key]]]))
  [publish Kind X] E R S -> [effects [[emit Kind (caps.expr X E R S)]]]
  [require Label P] E R S -> (if (caps.pred P E R S) [effects []] [failed Label]))

(define caps.apply-all
  [] S -> S
  [X | Xs] S -> (caps.apply-all Xs (caps.apply X S)))

(define caps.record
  Name [effects Es] S Effects Trace ->
    [working (caps.apply-all Es S) (append Effects Es) (append Trace [[action Name Es]])]
  _ [failed Why] _ _ _ -> [failed Why])

(define caps.action
  Name [choose P As Bs] E R S Effects Trace Fuel ->
    (caps.exec (if (caps.pred P E R S) As Bs) E R [working S Effects Trace] Fuel)
  Name [for-each T P As] E _ S Effects Trace Fuel ->
    (caps.each (caps.select T P E S) As E [working S Effects Trace] Fuel)
  Name A E R S Effects Trace Fuel ->
    [(caps.record Name (caps.step A E R S) S Effects Trace) Fuel])

(define caps.exec
  _ _ _ [failed Why] Fuel -> [[failed Why] Fuel]
  [] _ _ Acc Fuel -> [Acc Fuel]
  _ _ _ _ 0 -> (error "system: action fuel exhausted")
  [[named Name A] | As] E R [working S Effects Trace] Fuel ->
    (let Next (caps.action Name A E R S Effects Trace (- Fuel 1))
      (caps.exec As E R (hd Next) (nth 2 Next))))

(define caps.each
  _ _ _ [failed Why] Fuel -> [[failed Why] Fuel]
  [] _ _ Acc Fuel -> [Acc Fuel]
  [R | Rs] As E Acc Fuel ->
    (let Next (caps.exec As E R Acc Fuel)
      (caps.each Rs As E (hd Next) (nth 2 Next))))

(define caps.table
  T [[table T Fs Us Fks] | _] -> [table T Fs Us Fks]
  T [_ | Ts] -> (caps.table T Ts)
  _ [] -> (error "system: undeclared table"))

(define caps.tables
  [system _ _ Ts _ _] -> Ts
  [system _ Ts _ _] -> Ts)

(define caps.commands
  [system _ _ _ Cs _] -> Cs
  [system _ _ Cs _] -> Cs)

(define caps.command
  N [[command N Args Pre As Post] | _] -> [command N Args Pre As Post]
  N [_ | Cs] -> (caps.command N Cs)
  _ [] -> (error "system: undeclared command"))

(define caps.foreign-ok?
  [foreign F T] Rows S -> (capop.all? (/. R (not (= capop.absent (capop.find T (caps.lookup F (nth 4 R)) S)))) Rows))

(define caps.table-ok?
  [table T Fields Unique Foreign] S ->
    (let Rows (caps.rows T S)
      (and (capop.all? (/. R (= (caps.sorted (map (function hd) (nth 4 R)))
                               (caps.sorted (caps.field-names Fields)))) Rows)
       (and (capop.all? (/. R (capop.all? (/. C (caps.column-ok? C (nth 4 R))) Fields)) Rows)
        (and (capop.all? (/. F (capop.unique? (map (/. R (caps.lookup F (nth 4 R))) Rows))) Unique)
             (capop.all? (/. Fk (caps.foreign-ok? Fk Rows S)) Foreign))))))

(define caps.lex?
  X Y -> (capop.string-before? X Y))

(define caps.state-ok?
  M S -> (and (capop.state? S)
          (and (capop.all? (/. R (element? (nth 2 R) (map (/. T (nth 2 T)) (caps.tables M)))) S)
               (capop.all? (/. T (caps.table-ok? T S)) (caps.tables M)))))

(define caps.invariants?
  [system _ _ _ _ Ps] S -> (capop.all? (/. P (caps.pred (nth 2 P) [] [] S)) Ps)
  [system _ _ _ Ps] S -> (capop.all? (/. P (caps.pred (nth 2 P) [] [] S)) Ps))

(define caps.finish
  _ _ _ _ [failed Why] -> [rejected Why]
  M Post E Before [working S Effects Trace] ->
    (if (and (caps.state-ok? M S) (and (caps.invariants? M S) (caps.pred Post [[caps.before Before] | E] [] S)))
        [result S Effects Trace] [rejected invariant]))

(define caps.run
  M N E S Fuel ->
    (let C (caps.command N (caps.commands M))
      (if (and (capop.fields? E) (= (caps.sorted (map (function hd) E))
                                    (caps.sorted (nth 3 C))))
        (if (and (caps.state-ok? M S) (caps.invariants? M S))
          (if (caps.pred (nth 4 C) E [] S)
            (caps.finish M (nth 6 C) E S (hd (caps.exec (nth 5 C) E [] [working S [] []] Fuel)))
            [rejected precondition])
          (error "system: invalid initial state or invariant"))
        (error "system: argument names do not match command"))))

\\ R02 PR 1 (docs/ir-specification.md, sections 4.1 and 7). Adm(x) of one
\\ invocation of a command, by its outcome in the capcov.faults alphabet. A
\\ command is one transaction, so its info prefixes at commit points are
\\ exactly {nothing, everything}: under info-in-place-v1, and under
\\ atomic-publish-v1 when it publishes (caps.assumptions).
(define caps.adm
  S [result After Effects Trace] [ok] -> [[result After Effects Trace]]
  S [rejected _] [ok] -> []
  S [rejected Why] [fail [rejected L]] -> (if (= (caps.label Why) L) [[result S [] []]] [])
  S [result _ _ _] [fail [rejected _]] -> []
  S _ [fail [aborted]] -> [[result S [] []]]
  S [result After Effects Trace] [info] -> [[result S [] []] [result After Effects Trace]]
  S [rejected _] [info] -> [[result S [] []]])

\\ Rejection labels are symbols (precondition, invariant, duplicate-key,
\\ missing-row) or a require's string; on the wire both are strings.
(define caps.label
  Why -> (if (string? Why) Why (str Why)))

\\ The bridge: a v1 request outcome as an R02 outcome. rejected binds L to the
\\ model's own label, so any label is accepted as v1 does; when the model
\\ commits there is no label, and Adm of any [fail [rejected L]] is empty.
(define caps.bridge-outcome
  committed _ -> [ok]
  rejected [rejected Why] -> [fail [rejected (caps.label Why)]]
  rejected _ -> [fail [rejected ""]]
  aborted _ -> [fail [aborted]]
  unknown _ -> [info]
  O _ -> O)

(define caps.admissible
  S R O -> (caps.adm S R (caps.bridge-outcome O R)))

\\ Effect identity through the bridge: effect L of invocation Inv is
\\ [effect Inv Inv/body L]; a command's single step is "body".
(define caps.attempt
  Inv -> (cn Inv "/body"))

(define caps.identify
  Inv Alts -> (map (/. Alt (caps.identify-one Inv Alt)) Alts))

(define caps.identify-one
  Inv [result S Es T] -> [result S (map (/. L [effect Inv (caps.attempt Inv) L]) Es) T])

\\ The assumptions a model's results carry (section 7). A system that names
\\ its assumptions carries those; a v1 system is read with the bridge's, the
\\ ones its commands need (the same list R-ASSUME requires of a declaration).
(define caps.publishes?
  [command _ _ _ As _] -> (not (= [] (nth 3 (caps.summary As)))))

(define caps.publishing
  Cs -> (if (capop.all? (/. C (not (caps.publishes? C))) Cs) [] ["atomic-publish-v1"]))

(define caps.needed
  [] -> []
  Cs -> ["info-in-place-v1" | (caps.publishing Cs)])

(define caps.assumptions
  [system _ As _ _ _] -> As
  [system _ _ Cs _] -> (caps.needed Cs))

\\ R-ASSUME: known names, each once, and every one the commands need.
(define caps.assumptions-ok?
  As Cs -> (and (capop.unique? As)
            (and (capop.all? (/. A (element? A ["info-in-place-v1" "atomic-publish-v1" "single-landing-v1"])) As)
                 (capop.all? (/. A (element? A As)) (caps.needed Cs)))))

(define caps.accepts?
  Alternatives S E -> (prolog? (capop.member [result (receive S) (receive E) Trace] (receive Alternatives))))

\\ Access analysis walks the same compositional syntax, including predicates.
(define caps.reads-expr
  [before X] -> (caps.reads-expr X)
  [count-rows T] -> [T]
  [sum-field T _] -> [T]
  [int-add X Y] -> (capop.union (caps.reads-expr X) (caps.reads-expr Y))
  [int-sub X Y] -> (capop.union (caps.reads-expr X) (caps.reads-expr Y))
  [lookup T K _] -> (capop.union [T] (caps.reads-expr K))
  _ -> [])

(define caps.reads-pred
  [less-than X Y] -> (capop.union (caps.reads-expr X) (caps.reads-expr Y))
  [equal X Y] -> (capop.union (caps.reads-expr X) (caps.reads-expr Y))
  [exists T K] -> (capop.union [T] (caps.reads-expr K))
  [negate P] -> (caps.reads-pred P)
  [both P Q] -> (capop.union (caps.reads-pred P) (caps.reads-pred Q))
  [either P Q] -> (capop.union (caps.reads-pred P) (caps.reads-pred Q))
  [some-row T P] -> (capop.union [T] (caps.reads-pred P))
  [every-row T P] -> (capop.union [T] (caps.reads-pred P))
  _ -> [])

(define caps.merge-summary
  [R W E] [R2 W2 E2] -> [(capop.union R R2) (capop.union W W2) (capop.union E E2)])

(define caps.summary-action
  [insert T K Fs] -> [(capop.union [T] (capop.union (caps.reads-expr K) (caps.reads-fields Fs))) [T] []]
  [update T K _ V] -> [(capop.union [T] (capop.union (caps.reads-expr K) (caps.reads-expr V))) [T] []]
  [remove T K] -> [(capop.union [T] (caps.reads-expr K)) [T] []]
  [publish Kind V] -> [(caps.reads-expr V) [] [Kind]]
  [require _ P] -> [(caps.reads-pred P) [] []]
  [choose P As Bs] -> (caps.merge-summary [(caps.reads-pred P) [] []] (caps.merge-summary (caps.summary As) (caps.summary Bs)))
  [for-each T P As] -> (caps.merge-summary [(capop.union [T] (caps.reads-pred P)) [] []] (caps.summary As)))

(define caps.reads-fields
  [] -> []
  [[_ V] | Fs] -> (capop.union (caps.reads-expr V) (caps.reads-fields Fs)))

(define caps.summary
  [] -> [[] [] []]
  [[named _ A] | As] -> (caps.merge-summary (caps.summary-action A) (caps.summary As)))

(define caps.analyze
  M N -> (let C (caps.command N (caps.commands M))
    (caps.merge-summary [(capop.union (caps.reads-pred (nth 4 C))
                                     (capop.union (caps.reads-pred (nth 6 C)) (map (/. T (nth 2 T)) (caps.tables M)))) [] []]
                        (caps.summary (nth 5 C)))))

(define caps.insert-sorted
  X [] -> [X]
  X [Y | Ys] -> [X Y | Ys] where (caps.lex? X Y)
  X [Y | Ys] -> [Y | (caps.insert-sorted X Ys)])

(define caps.sorted
  [] -> []
  [X | Xs] -> (caps.insert-sorted X (caps.sorted Xs)))

(define caps.member-table?
  T Ts -> (element? T (map (/. Table (nth 2 Table)) Ts)))

(define caps.member-field?
  T F Ts -> (and (caps.member-table? T Ts) (element? F (caps.field-names (nth 3 (caps.table T Ts))))))

(define caps.scope-expr?
  [before X] Args Row Ts -> (and (element? caps.before Args) (caps.scope-expr? X Args Row Ts))
  [count-rows T] _ _ Ts -> (caps.member-table? T Ts)
  [sum-field T F] _ _ Ts -> (caps.member-field? T F Ts)
  [int-add X Y] Args Row Ts -> (and (caps.scope-expr? X Args Row Ts) (caps.scope-expr? Y Args Row Ts))
  [int-sub X Y] Args Row Ts -> (and (caps.scope-expr? X Args Row Ts) (caps.scope-expr? Y Args Row Ts))
  [literal _] _ _ _ -> true
  [argument K] Args _ _ -> (element? K Args)
  [row-key] _ Row _ -> (not (= Row no-row))
  [row-field F] _ Row Ts -> (and (not (= Row no-row)) (caps.member-field? Row F Ts))
  [lookup T K F] Args Row Ts -> (and (caps.member-field? T F Ts) (caps.scope-expr? K Args Row Ts)))

(define caps.scope-pred?
  [less-than X Y] Args Row Ts -> (and (caps.scope-expr? X Args Row Ts) (caps.scope-expr? Y Args Row Ts))
  [yes] _ _ _ -> true
  [no] _ _ _ -> true
  [equal X Y] Args Row Ts -> (and (caps.scope-expr? X Args Row Ts) (caps.scope-expr? Y Args Row Ts))
  [exists T K] Args Row Ts -> (and (caps.member-table? T Ts) (caps.scope-expr? K Args Row Ts))
  [negate P] Args Row Ts -> (caps.scope-pred? P Args Row Ts)
  [both P Q] Args Row Ts -> (and (caps.scope-pred? P Args Row Ts) (caps.scope-pred? Q Args Row Ts))
  [either P Q] Args Row Ts -> (and (caps.scope-pred? P Args Row Ts) (caps.scope-pred? Q Args Row Ts))
  [some-row T P] Args _ Ts -> (and (caps.member-table? T Ts) (caps.scope-pred? P Args T Ts))
  [every-row T P] Args _ Ts -> (and (caps.member-table? T Ts) (caps.scope-pred? P Args T Ts)))

(define caps.scope-action?
  [insert T K Fs] Args Row Ts ->
    (and (caps.member-table? T Ts)
     (and (caps.scope-expr? K Args Row Ts)
      (and (= (caps.sorted (map (function hd) Fs)) (caps.sorted (caps.field-names (nth 3 (caps.table T Ts)))))
           (capop.all? (/. F (caps.scope-expr? (nth 2 F) Args Row Ts)) Fs))))
  [update T K F V] Args Row Ts ->
    (and (caps.member-field? T F Ts) (and (caps.scope-expr? K Args Row Ts) (caps.scope-expr? V Args Row Ts)))
  [remove T K] Args Row Ts -> (and (caps.member-table? T Ts) (caps.scope-expr? K Args Row Ts))
  [publish _ V] Args Row Ts -> (caps.scope-expr? V Args Row Ts)
  [require _ P] Args Row Ts -> (caps.scope-pred? P Args Row Ts)
  [choose P As Bs] Args Row Ts -> (and (caps.scope-pred? P Args Row Ts)
                                    (and (caps.scope-actions? As Args Row Ts) (caps.scope-actions? Bs Args Row Ts)))
  [for-each T P As] Args _ Ts -> (and (caps.member-table? T Ts)
                                   (and (caps.scope-pred? P Args T Ts) (caps.scope-actions? As Args T Ts))))

(define caps.scope-actions?
  As Args Row Ts -> (capop.all? (/. A (caps.scope-action? (nth 3 A) Args Row Ts)) As))

(define caps.names
  [] -> []
  [[named N [choose _ As Bs]] | Rest] -> (append [N] (append (caps.names As) (append (caps.names Bs) (caps.names Rest))))
  [[named N [for-each _ _ As]] | Rest] -> (append [N] (append (caps.names As) (caps.names Rest)))
  [[named N _] | Rest] -> [N | (caps.names Rest)])

(define caps.scope-command?
  [command _ Args Pre As Post] Ts ->
    (and (capop.unique? Args)
     (and (capop.unique? (caps.names As))
      (and (<= (length (caps.names As)) 64)
       (and (caps.scope-pred? Pre Args no-row Ts)
        (and (caps.scope-actions? As Args no-row Ts) (caps.scope-pred? Post [caps.before | Args] no-row Ts)))))))

(define caps.schema?
  [table _ Fields Unique Foreign] Ts ->
    (and (capop.unique? (caps.field-names Fields))
      (and (capop.unique? Unique)
       (and (<= (length Fields) 64)
        (and (capop.all? (/. F (element? F (caps.field-names Fields))) Unique)
             (capop.all? (/. F (and (element? (nth 2 F) (caps.field-names Fields)) (caps.member-table? (nth 3 F) Ts))) Foreign))))))

(define caps.scoped?
  [system N As Ts Cs Ps] -> (and (caps.assumptions-ok? As Cs) (caps.scoped? [system N Ts Cs Ps]))
  [system _ Ts Cs Ps] ->
    (and (<= (length Ts) 64)
     (and (<= (length Cs) 512)
      (and (capop.unique? (map (/. T (nth 2 T)) Ts))
       (and (capop.unique? (map (/. C (nth 2 C)) Cs))
        (and (capop.unique? (map (function hd) Ps))
         (and (capop.all? (/. T (caps.schema? T Ts)) Ts)
          (and (capop.all? (/. C (caps.scope-command? C Ts)) Cs)
               (capop.all? (/. P (caps.scope-pred? (nth 2 P) [] no-row Ts)) Ps)))))))))

(define caps.typechecks?
  M -> (= caps-system (shen.typecheck (capop.syntax M) caps-system)))

\\ Canonical decimal int32 values avoid host float/JSON-number ambiguities.
(define caps.digits
  "" Acc -> Acc
  S Acc -> (let N (- (string->n (pos S 0)) 48)
    (if (and (<= 0 N) (<= N 9))
      (let Next (+ (* Acc 10) N)
        (if (<= Next 2147483648) (caps.digits (tlstr S) Next) (error "system: integer overflow")))
      (error "system: invalid integer"))))

(define caps.integer
  "" -> (error "system: empty integer")
  S -> (let N (if (= (pos S 0) "-") (- 0 (caps.digits (tlstr S) 0)) (caps.digits S 0))
         (if (and (<= -2147483648 N) (and (<= N 2147483647) (= S (str N))))
             N (error "system: noncanonical or out-of-range integer"))))

(define caps.int-result
  N -> (if (and (<= -2147483648 N) (<= N 2147483647)) (str N) (error "system: integer overflow")))

(define caps.field-name
  [column F _] -> F
  F -> F)

(define caps.field-names
  Fs -> (map (function caps.field-name) Fs))

(define caps.column-ok?
  [column F [text]] Fs -> (string? (caps.lookup F Fs))
  [column F [int32]] Fs -> (trap-error (do (caps.integer (caps.lookup F Fs)) true) (/. Error false))
  [column F [enum Vs]] Fs -> (element? (caps.lookup F Fs) Vs)
  F Fs -> (string? (caps.lookup F Fs)))

(define caps.sum
  _ [] N -> (caps.int-result N)
  F [R | Rs] N -> (let Next (+ N (caps.integer (caps.lookup F (nth 4 R))))
                    (do (caps.int-result Next) (caps.sum F Rs Next))))
