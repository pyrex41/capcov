\* capcov claim workbench (EXPERIMENT-PLAN section 18, Stage D).

   Shared runtime, rule elaboration, stratified bottom-up closure, the bounded
   top-down derivation search that mirrors claims/static/certificate.py, and
   the bounded why-not search.  Loaded first; rule-authority.shen and
   certificate-output.shen build on the definitions here.

   Everything lives in the capcov. namespace so no kernel name (sum, list,
   dict, pos, ...) is shadowed.  Strings in this Shen are byte strings (pos,
   explode and string->n operate on single UTF-8 bytes); every string walk
   below is byte-wise, which also makes canonical ordering equal to Python's
   code-point ordering of the same UTF-8 text.

   Input contract (set by the generated bundle.shen before capcov.main runs):
     capcov.*in-decls*   [[Name Modality Polarity Binding Primitive Columns
                           ContextIndices Completes Finite Nonempty
                           CompatTargets CompatContext Producers] ...]
                         column = [Name Type ContextFlag]
     capcov.*in-facts*   [[Relation Row EvidenceIds] ...]
     capcov.*in-rules*   [[Name Digest [HeadRel HeadTerms] Body Aggregation] ...]
                         term = [capcov.v "X"] | [capcov.c Value Type]
                         body = [capcov.pos Rel Terms] | [capcov.neg Rel Terms]
                              | [capcov.cmp L Op R]
                         aggregation = capcov.null
                              | [Name Rel GroupBy ValueVar Op Domain Closure]
     capcov.*in-frozen*  frozen elaborated-pack checksum string or capcov.null
     capcov.*in-bounds*  [MaxDepth MaxNodes]
     capcov.*in-digests* [BundleDigest RulesDigest]  (opaque; echoed back)
     capcov.*in-request* [capcov.authority] | [capcov.derive Rel Row]
                         | [capcov.why-not Rel Row]
   Values: strings, numbers, true, false, capcov.null,
           [capcov.obj (@p Key Value) ...], [capcov.arr Value ...].
*\

(set capcov.*dq* (n->string 34))
(set capcov.*bs* (n->string 92))
(set capcov.*nl* (n->string 10))
(set capcov.*nul* (n->string 0))
(set capcov.*begin* "<<<CAPCOV-SHEN-JSON-BEGIN>>>")
(set capcov.*end* "<<<CAPCOV-SHEN-JSON-END>>>")
(set capcov.*work-budget* 3000000)
(set capcov.*max-alternatives* 16)
(set capcov.*max-why-not-depth* 2)

\\ ---------------------------------------------------------------- lists and strings

(define capcov.dq
  \\ join parts with a double quote (the Shen reader has no string escapes)
  [] -> ""
  [P] -> P
  [P | Ps] -> (cn P (cn (value capcov.*dq*) (capcov.dq Ps))))

(define capcov.take
  0 _ -> []
  _ [] -> []
  N [X | Xs] -> [X | (capcov.take (- N 1) Xs)])

(define capcov.drop
  0 L -> L
  _ [] -> []
  N [_ | Xs] -> (capcov.drop (- N 1) Xs))

(define capcov.join
  \\ concatenate a chunk list by repeated pairwise merging: O(n) list steps
  [] -> ""
  [S] -> S
  L -> (capcov.join (capcov.pair-up L)))

(define capcov.pair-up
  [] -> []
  [A] -> [A]
  [A B | R] -> [(cn A B) | (capcov.pair-up R)])

(define capcov.intersperse
  _ [] -> []
  _ [X] -> [X]
  Sep [X | Xs] -> [X Sep | (capcov.intersperse Sep Xs)])

(define capcov.filter
  F [] -> []
  F [X | Xs] -> (if (F X) [X | (capcov.filter F Xs)] (capcov.filter F Xs)))

(define capcov.any?
  F [] -> false
  F [X | Xs] -> (if (F X) true (capcov.any? F Xs)))

(define capcov.all?
  F [] -> true
  F [X | Xs] -> (if (F X) (capcov.all? F Xs) false))

(define capcov.index-of
  \\ 0-based position of X in L, or capcov.none
  X L -> (capcov.index-of-h X L 0))

(define capcov.index-of-h
  X [] I -> capcov.none
  X [Y | Ys] I -> (if (= X Y) I (capcov.index-of-h X Ys (+ I 1))))

(define capcov.nth0
  I L -> (nth (+ I 1) L))

(define capcov.dedupe
  [] -> []
  [X] -> [X]
  [X Y | R] -> (if (= X Y) (capcov.dedupe [Y | R]) [X | (capcov.dedupe [Y | R])]))

\* Byte walks.  Every string primitive of this runtime (pos, tlstr, explode)
   costs O(length) per call, so a walk is quadratic in the string length and
   must only ever run over short strings (keys, values, chunks).  The walk
   below peels one byte at a time with tlstr; it deliberately raises no error
   and installs no handler, because trap-error under a deep call stack is
   very expensive here. *\

(define capcov.bytes
  \\ the UTF-8 bytes of S as a list of numbers
  S -> (capcov.bytes-h S []))

(define capcov.bytes-h
  "" Acc -> (reverse Acc)
  S Acc -> (capcov.bytes-h (tlstr S) [(string->n (pos S 0)) | Acc]))

(define capcov.bytes-memo
  \\ memoised bytes for strings compared repeatedly (row values, keys)
  S -> (let Cached (capcov.meta-get (cn "b:" S) capcov.none)
         (if (= Cached capcov.none)
             (capcov.meta-put (cn "b:" S) (capcov.bytes S))
             Cached)))

(define capcov.bytes<
  [] [] -> false
  [] _ -> true
  _ [] -> false
  [A | As] [B | Bs] -> (if (< A B) true (if (> A B) false (capcov.bytes< As Bs))))

(define capcov.str<
  A B -> (if (= A B) false (capcov.bytes< (capcov.bytes-memo A) (capcov.bytes-memo B))))

(define capcov.sort-strings
  L -> (sort (function capcov.str<) L))

(define capcov.sort-by-key
  \\ sort items by a string key function, canonical byte order
  KeyOf L -> (map (function snd) (sort (/. A B (capcov.str< (fst A) (fst B))) (map (/. X (@p (KeyOf X) X)) L))))

(define capcov.prefix?
  P S -> (capcov.prefix-h (capcov.bytes P) (capcov.bytes S)))

(define capcov.prefix-h
  [] _ -> true
  _ [] -> false
  [A | As] [B | Bs] -> (if (= A B) (capcov.prefix-h As Bs) false))

(define capcov.str-after
  \\ the bytes of S after its first N bytes
  S 0 -> S
  S N -> (capcov.str-after (tlstr S) (- N 1)))

(define capcov.hexdigit
  D -> (pos "0123456789abcdef" D))

(define capcov.hex2
  K -> (cn (capcov.hexdigit (div K 16)) (capcov.hexdigit (mod K 16))))

\\ ---------------------------------------------------------------- canonical JSON text

\* The renderer produces a flat list of short chunks (capcov.json-chunks);
   capcov.json-of joins them.  Keeping the chunks lets the frozen-pack
   checksum stream over short strings instead of walking the whole text. *\

(define capcov.json-esc-byte
  K -> (cond ((= K 34) (cn (value capcov.*bs*) (value capcov.*dq*)))
             ((= K 92) (cn (value capcov.*bs*) (value capcov.*bs*)))
             ((= K 10) (cn (value capcov.*bs*) "n"))
             ((= K 13) (cn (value capcov.*bs*) "r"))
             ((= K 9) (cn (value capcov.*bs*) "t"))
             ((= K 8) (cn (value capcov.*bs*) "b"))
             ((= K 12) (cn (value capcov.*bs*) "f"))
             ((< K 32) (cn (value capcov.*bs*) (cn "u00" (capcov.hex2 K))))
             (true (n->string K))))

(define capcov.json-clean?
  [] -> true
  [K | Ks] -> (if (or (< K 32) (or (= K 34) (= K 92))) false (capcov.json-clean? Ks)))

(define capcov.json-str
  \\ a JSON string literal for S, memoised (names and values repeat heavily)
  S -> (let Cached (capcov.meta-get (cn "js:" S) capcov.none)
         (if (= Cached capcov.none)
             (capcov.meta-put (cn "js:" S) (capcov.json-str-render S))
             Cached)))

(define capcov.json-str-render
  S -> (let Bytes (capcov.bytes S)
         (cn (value capcov.*dq*)
             (cn (if (capcov.json-clean? Bytes) S (capcov.join (map (function capcov.json-esc-byte) Bytes)))
                 (value capcov.*dq*)))))

(define capcov.json-chunks
  V -> (reverse (capcov.json-acc V [])))

(define capcov.json-acc
  \\ canonical JSON: sorted object keys, no whitespace (Python canonical_json);
  \\ chunks are consed onto Acc in reverse
  [] Acc -> ["[]" | Acc]
  V Acc -> ["true" | Acc] where (= V true)
  V Acc -> ["false" | Acc] where (= V false)
  capcov.null Acc -> ["null" | Acc]
  V Acc -> [(capcov.json-str V) | Acc] where (string? V)
  V Acc -> [(str V) | Acc] where (number? V)
  [capcov.json S] Acc -> [S | Acc]
  [capcov.json-spliced Chunks] Acc -> (capcov.rev-onto Chunks Acc)
  [capcov.obj | Pairs] Acc -> ["}" | (capcov.json-pairs-acc (capcov.sort-pairs Pairs) ["{" | Acc])]
  [capcov.arr | Items] Acc -> ["]" | (capcov.json-items-acc Items ["[" | Acc])]
  V Acc -> ["]" | (capcov.json-items-acc V ["[" | Acc])] where (cons? V)
  V Acc -> (error "capcov-internal: cannot render ~S as JSON" V))

(define capcov.json-items-acc
  [] Acc -> Acc
  [X] Acc -> (capcov.json-acc X Acc)
  [X | Xs] Acc -> (capcov.json-items-acc Xs ["," | (capcov.json-acc X Acc)]))

(define capcov.json-pairs-acc
  [] Acc -> Acc
  [(@p K V)] Acc -> (capcov.json-acc V [":" (capcov.json-str K) | Acc])
  [(@p K V) | Ps] Acc -> (capcov.json-pairs-acc Ps ["," | (capcov.json-acc V [":" (capcov.json-str K) | Acc])]))

(define capcov.rev-onto
  [] Acc -> Acc
  [X | Xs] Acc -> (capcov.rev-onto Xs [X | Acc]))

(define capcov.json-of
  V -> (capcov.join (capcov.json-chunks V)))

(define capcov.json-splice
  \\ already-rendered chunks to be embedded verbatim (avoids one huge string)
  Chunks -> [capcov.json-spliced Chunks])

(define capcov.sort-pairs
  Pairs -> (sort (/. A B (capcov.str< (fst A) (fst B))) Pairs))

(define capcov.obj
  Pairs -> [capcov.obj | Pairs])

(define capcov.arr
  Items -> [capcov.arr | Items])

(define capcov.json-quote
  \\ a string that must be embedded verbatim (already canonical JSON text)
  S -> [capcov.json S])

\\ ---------------------------------------------------------------- checksum (frozen pack)

\* Two-lane checksum over the bytes of a chunk list: lane A is
   a <- (4a + k + 1) mod (2^31 - 1), lane B is b <- (3b + k + 1) mod (2^31 - 19).
   The reduction is written as at most four exact subtractions because this
   runtime's mod and div cost ~50-100 microseconds per call and mod is
   inexact near 2^53; every intermediate stays far below 2^53.  Python
   recomputes the same recurrence (claims/shen.py pack_checksum).  This is a
   change-detection fingerprint for the frozen elaborated pack, not a
   cryptographic hash; the SHA-256 of the printed-back text is recorded by
   Python next to it. *\

(set capcov.*p-a* 2147483647)
(set capcov.*p-b* 2147483629)

(define capcov.reduce
  X P -> X where (< X P)
  X P -> (capcov.reduce (- X P) P))

(define capcov.checksum-chunks
  Chunks -> (capcov.checksum-fold Chunks 7 11))

(define capcov.checksum-fold
  [] A B -> (cn "ck2-" (cn (str A) (cn "-" (str B))))
  [S | Ss] A B -> (let Lanes (capcov.checksum-h (capcov.bytes S) A B)
                    (capcov.checksum-fold Ss (fst Lanes) (snd Lanes))))

(define capcov.checksum-h
  [] A B -> (@p A B)
  [K | Ks] A B -> (capcov.checksum-h Ks
                                     (capcov.reduce (+ (* A 4) (+ K 1)) (value capcov.*p-a*))
                                     (capcov.reduce (+ (* B 3) (+ K 1)) (value capcov.*p-b*))))

(define capcov.checksum
  S -> (capcov.checksum-chunks [S]))

\\ ---------------------------------------------------------------- hash tables (string keys)

(define capcov.abs
  N -> (if (< N 0) (- 0 N) N))

(define capcov.ht-new
  N -> (let V (vector N) (do (address-> V 0 N) (capcov.ht-fill V 1 N))))

(define capcov.ht-fill
  V I N -> V where (> I N)
  V I N -> (do (address-> V I []) (capcov.ht-fill V (+ I 1) N)))

(define capcov.ht-slot
  \\ hash already yields [0, N); the guard avoids mod, which is very slow here
  Key V -> (let N (<-address V 0) H (hash Key N)
             (if (and (>= H 0) (< H N)) (+ 1 H) (+ 1 (capcov.reduce (capcov.abs H) N)))))

(define capcov.assoc-str
  Key [] Default -> Default
  Key [(@p K Val) | Rest] Default -> (if (= K Key) Val (capcov.assoc-str Key Rest Default)))

(define capcov.remove-key
  Key [] -> []
  Key [(@p K Val) | Rest] -> (if (= K Key) Rest [(@p K Val) | (capcov.remove-key Key Rest)]))

(define capcov.ht-get
  Key V Default -> (capcov.assoc-str Key (<-address V (capcov.ht-slot Key V)) Default))

(define capcov.ht-put
  Key Val V -> (let Slot (capcov.ht-slot Key V)
                 (do (address-> V Slot [(@p Key Val) | (capcov.remove-key Key (<-address V Slot))]) Val)))

(define capcov.ht-has?
  Key V -> (not (= (capcov.ht-get Key V capcov.absent) capcov.absent)))

\\ ---------------------------------------------------------------- global state

(define capcov.reset-state
  -> (do (set capcov.*meta* (capcov.ht-new 4093))
         (set capcov.*rows* (capcov.ht-new 8191))
         (set capcov.*rules* [])
         (set capcov.*relation-names* [])
         (set capcov.*nodes* 0)
         (set capcov.*work* 0)
         (set capcov.*max-steps* 0)
         (set capcov.*max-nesting* 0)
         (set capcov.*phase* capcov.load)
         (set capcov.*changed* false)
         (set capcov.*unstratifiable* false)
         (set capcov.*expand-acc* [])
         (set capcov.*max-depth* (nth 1 (value capcov.*in-bounds*)))
         (set capcov.*max-nodes* (nth 2 (value capcov.*in-bounds*)))
         (set capcov.*elaborated-chunks* [])
         (set capcov.*elaborated-checksum* "")
         ok))

(define capcov.meta-get
  Key Default -> (capcov.ht-get Key (value capcov.*meta*) Default))

(define capcov.meta-put
  Key Val -> (capcov.ht-put Key Val (value capcov.*meta*)))

(define capcov.searching?
  -> (or (= (value capcov.*phase*) capcov.derive) (= (value capcov.*phase*) capcov.why-not)))

(define capcov.tick
  What -> (do (set capcov.*work* (+ 1 (value capcov.*work*)))
              (if (> (value capcov.*work*) (value capcov.*work-budget*))
                  (error "capcov-resource-exhausted: ~A: work exceeds budget=~A" What (value capcov.*work-budget*))
                  ok)
              (if (= (value capcov.*phase*) capcov.derive) (capcov.node-tick What) ok)))

(define capcov.node-tick
  What -> (do (set capcov.*nodes* (+ 1 (value capcov.*nodes*)))
              (if (> (value capcov.*nodes*) (value capcov.*max-nodes*))
                  (error "capcov-truncated: ~A: certificate exceeds max_nodes=~A" What (value capcov.*max-nodes*))
                  ok)))

(define capcov.nest
  Depth -> (do (if (> Depth (value capcov.*max-nesting*)) (set capcov.*max-nesting* Depth) ok)
               (if (> Depth (value capcov.*max-depth*))
                   (error "capcov-truncated: derivation nesting exceeds max_depth=~A" (value capcov.*max-depth*))
                   ok)))

\\ ---------------------------------------------------------------- declarations

(define capcov.load-decls
  [] -> (set capcov.*relation-names* (reverse (value capcov.*relation-names*)))
  [D | Ds] -> (do (if (= (capcov.decl (capcov.decl-name D)) capcov.none)
                      ok
                      (error "capcov-invalid-input: relation ~A declared twice" (capcov.decl-name D)))
                  (capcov.meta-put (cn "decl:" (capcov.decl-name D)) D)
                  (set capcov.*relation-names* [(capcov.decl-name D) | (value capcov.*relation-names*)])
                  (capcov.load-decls Ds)))

(define capcov.decl
  Rel -> (capcov.meta-get (cn "decl:" Rel) capcov.none))

(define capcov.decl-name D -> (nth 1 D))
(define capcov.decl-modality D -> (nth 2 D))
(define capcov.decl-polarity D -> (nth 3 D))
(define capcov.decl-binding D -> (nth 4 D))
(define capcov.decl-primitive? D -> (nth 5 D))
(define capcov.decl-columns D -> (nth 6 D))
(define capcov.decl-context D -> (nth 7 D))
(define capcov.decl-completes D -> (nth 8 D))
(define capcov.decl-finite D -> (nth 9 D))
(define capcov.decl-nonempty D -> (nth 10 D))
(define capcov.decl-compat-targets D -> (nth 11 D))
(define capcov.decl-compat-context D -> (nth 12 D))
(define capcov.decl-producers D -> (nth 13 D))
(define capcov.decl-arity D -> (length (capcov.decl-columns D)))
(define capcov.column-names D -> (map (/. C (nth 1 C)) (capcov.decl-columns D)))

\\ ---------------------------------------------------------------- rows, indexes, evidence

\* Row storage.  The native (str Row) text is used only as a hash-bucket key;
   membership is always confirmed structurally with =, so two distinct rows
   whose printed forms coincide can never be merged.  Canonical (JSON-key)
   order is established lazily per relation the first time the search phase
   touches it, because byte-wise string comparison is the interpreter's most
   expensive operation and the closure itself is order-insensitive. *\

(define capcov.rows-get
  Key Default -> (capcov.ht-get Key (value capcov.*rows*) Default))

(define capcov.rows-put
  Key Val -> (capcov.ht-put Key Val (value capcov.*rows*)))

(define capcov.skey
  \\ hash-bucket text for a row or value (str cannot print pairs; the JSON
  \\ renderer is memoised per string so this is cheap after first use)
  X -> (capcov.json-of X))

(define capcov.row-key
  Row -> (capcov.json-of Row))

(define capcov.has-key
  Rel Row -> (cn "has:" (cn Rel (cn "|" (capcov.skey Row)))))

(define capcov.index-key
  Rel I Val -> (cn "idx:" (cn Rel (cn "|" (cn (str I) (cn "|" (capcov.skey Val)))))))

(define capcov.present?
  Rel Row -> (element? Row (capcov.rows-get (capcov.has-key Rel Row) [])))

(define capcov.raw-rows
  Rel -> (capcov.rows-get (cn "rows:" Rel) []))

(define capcov.rows
  Rel -> (do (capcov.ensure-canonical Rel) (capcov.raw-rows Rel)))

(define capcov.index-rows
  Rel I Val -> (do (capcov.ensure-canonical Rel) (capcov.rows-get (capcov.index-key Rel I Val) [])))

(define capcov.add-row
  \\ true when Row was new
  Rel Row -> (let Has (capcov.has-key Rel Row) Bucket (capcov.rows-get Has [])
               (if (element? Row Bucket)
                   false
                   (do (capcov.rows-put Has [Row | Bucket])
                       (capcov.rows-put (cn "rows:" Rel) [Row | (capcov.raw-rows Rel)])
                       (capcov.add-index Rel Row Row 0)
                       (capcov.rows-put (cn "canon:" Rel) false)
                       true))))

(define capcov.add-index
  Rel Row [] I -> ok
  Rel Row [V | Vs] I -> (let Key (capcov.index-key Rel I V)
                          (do (capcov.rows-put Key [Row | (capcov.rows-get Key [])])
                              (capcov.add-index Rel Row Vs (+ I 1)))))

(define capcov.clear-index
  Rel Row [] I -> ok
  Rel Row [V | Vs] I -> (do (capcov.rows-put (capcov.index-key Rel I V) [])
                            (capcov.clear-index Rel Row Vs (+ I 1))))

(define capcov.ensure-canonical
  Rel -> (if (and (capcov.searching?) (not (capcov.rows-get (cn "canon:" Rel) false)))
             (let Sorted (capcov.sort-rows (capcov.raw-rows Rel))
               (do (capcov.rows-put (cn "rows:" Rel) Sorted)
                   (capcov.each (/. R (capcov.clear-index Rel R R 0)) Sorted)
                   (capcov.each (/. R (capcov.add-index Rel R R 0)) (reverse Sorted))
                   (capcov.rows-put (cn "canon:" Rel) true)
                   ok))
             ok))

(define capcov.each
  F [] -> ok
  F [X | Xs] -> (do (F X) (capcov.each F Xs)))

(define capcov.sort-rows
  \\ canonical row order (Python: sorted by canonical_json(row)) without
  \\ walking whole keys: values are compared natively, and only the first
  \\ differing rendered value (delimiter appended, so the order equals the
  \\ order of the full keys) is compared byte-wise
  Rows -> (map (function snd) (sort (/. A B (capcov.parts< (fst A) (fst B))) (map (/. R (@p (capcov.row-parts R) R)) Rows))))

(define capcov.row-parts
  [] -> ["[]"]
  [V] -> [(cn (capcov.json-of V) "]")]
  [V | Vs] -> [(cn (capcov.json-of V) ",") | (capcov.row-parts Vs)])

(define capcov.parts<
  [] [] -> false
  [] _ -> true
  _ [] -> false
  [X | Xs] [Y | Ys] -> (if (= X Y) (capcov.parts< Xs Ys) (capcov.bytes< (capcov.bytes-memo X) (capcov.bytes-memo Y))))

(define capcov.evidence-of
  Rel Row -> (capcov.assoc-row Row (capcov.meta-get (cn "ev:" (cn Rel (cn "|" (capcov.skey Row)))) []) []))

(define capcov.assoc-row
  Row [] Default -> Default
  Row [(@p R Ids) | Rest] Default -> (if (= R Row) Ids (capcov.assoc-row Row Rest Default)))

(define capcov.put-evidence
  Rel Row Ids -> (let Key (cn "ev:" (cn Rel (cn "|" (capcov.skey Row))))
                      Bucket (capcov.meta-get Key [])
                      Old (capcov.assoc-row Row Bucket [])
                   (capcov.meta-put Key [(@p Row (capcov.dedupe (capcov.sort-strings (append Ids Old)))) | (capcov.remove-row Row Bucket)])))

(define capcov.remove-row
  Row [] -> []
  Row [(@p R Ids) | Rest] -> (if (= R Row) Rest [(@p R Ids) | (capcov.remove-row Row Rest)]))

(define capcov.load-facts
  [] -> ok
  [[Rel Row Ids] | Fs] -> (do (if (= (capcov.decl Rel) capcov.none)
                                  (error "capcov-invalid-input: fact for undeclared relation ~A" Rel)
                                  ok)
                              (if (= (length Row) (capcov.decl-arity (capcov.decl Rel)))
                                  ok
                                  (error "capcov-invalid-input: fact for ~A has arity ~A, declared ~A" Rel (length Row) (capcov.decl-arity (capcov.decl Rel))))
                              (capcov.add-row Rel Row)
                              (if (empty? Ids) ok (capcov.put-evidence Rel Row Ids))
                              (capcov.load-facts Fs)))

\\ ---------------------------------------------------------------- terms, environments, unification

(define capcov.env-get
  Name [] -> capcov.unbound
  Name [(@p K V) | R] -> (if (= K Name) V (capcov.env-get Name R)))

(define capcov.ground
  [capcov.v Name] Env -> (capcov.env-get Name Env)
  [capcov.c C T] Env -> C)

(define capcov.ground-row
  Terms Env -> (map (/. T (capcov.ground T Env)) Terms))

(define capcov.fully-ground?
  [] -> true
  [V | Vs] -> (if (= V capcov.unbound) false (capcov.fully-ground? Vs)))

(define capcov.unify
  [] [] Env -> Env
  [] _ _ -> capcov.none
  _ [] _ -> capcov.none
  [[capcov.v Name] | Ts] [Val | Vs] Env -> (let Cur (capcov.env-get Name Env)
                                             (if (= Cur capcov.unbound)
                                                 (capcov.unify Ts Vs [(@p Name Val) | Env])
                                                 (if (= Cur Val) (capcov.unify Ts Vs Env) capcov.none)))
  [[capcov.c C T] | Ts] [Val | Vs] Env -> (if (= C Val) (capcov.unify Ts Vs Env) capcov.none))

(define capcov.term-vars
  [] -> []
  [[capcov.v Name] | Ts] -> [Name | (capcov.term-vars Ts)]
  [_ | Ts] -> (capcov.term-vars Ts))

(define capcov.variable?
  [capcov.v _] -> true
  _ -> false)

(define capcov.compare-values
  L "=" R -> (= L R)
  L "!=" R -> (not (= L R))
  L Op R -> (capcov.compare-ordered L Op R) where (and (number? L) (number? R))
  L Op R -> (capcov.compare-strings L Op R) where (and (string? L) (string? R))
  _ _ _ -> false)

(define capcov.compare-ordered
  L "<" R -> (< L R)
  L "<=" R -> (<= L R)
  L ">" R -> (> L R)
  L ">=" R -> (>= L R)
  _ _ _ -> false)

(define capcov.compare-strings
  L "<" R -> (capcov.str< L R)
  L "<=" R -> (not (capcov.str< R L))
  L ">" R -> (capcov.str< R L)
  L ">=" R -> (not (capcov.str< L R))
  _ _ _ -> false)

(define capcov.holds?
  L Op R Env -> (let LV (capcov.ground L Env) RV (capcov.ground R Env)
                  (if (or (= LV capcov.unbound) (= RV capcov.unbound)) false (capcov.compare-values LV Op RV))))

\\ ---------------------------------------------------------------- candidate rows

(define capcov.candidates
  \\ rows of Rel narrowed by the bound positions (smallest bucket, first wins ties)
  Rel Terms Env -> (capcov.best-bucket Rel Terms Env 0 capcov.none))

(define capcov.best-bucket
  Rel [] Env I Best -> (if (= Best capcov.none) (capcov.rows Rel) Best)
  Rel [T | Ts] Env I Best -> (let Val (capcov.ground T Env)
                               (if (= Val capcov.unbound)
                                   (capcov.best-bucket Rel Ts Env (+ I 1) Best)
                                   (let Bucket (capcov.index-rows Rel I Val)
                                     (if (or (= Best capcov.none) (< (length Bucket) (length Best)))
                                         (capcov.best-bucket Rel Ts Env (+ I 1) Bucket)
                                         (capcov.best-bucket Rel Ts Env (+ I 1) Best))))))

\\ ---------------------------------------------------------------- body instantiation

\* capcov.inst walks a rule body under Env in body order and calls K with
   (Env Positives Negatives Comparisons) for every full instantiation, in the
   canonical order Python's certificate extractor uses.  K returns
   capcov.continue to keep enumerating or [capcov.stop V] to finish with V.
   Positives are [Index Rel Row], negatives [Rel Row], comparisons [L Op R]. *\

(define capcov.inst
  [] Env Pos Neg Cmp I K -> (K Env (reverse Pos) (reverse Neg) (reverse Cmp))
  [[capcov.cmp L Op R] | Rest] Env Pos Neg Cmp I K ->
    (if (capcov.holds? L Op R Env)
        (capcov.inst Rest Env Pos Neg [[(capcov.ground L Env) Op (capcov.ground R Env)] | Cmp] (+ I 1) K)
        capcov.continue)
  [[capcov.neg Rel Terms] | Rest] Env Pos Neg Cmp I K ->
    (let Row (capcov.ground-row Terms Env)
      (if (not (capcov.fully-ground? Row))
          (error "capcov-inconsistent: negated atom ~A is not ground at check time" Rel)
          (if (capcov.present? Rel Row)
              capcov.continue
              (capcov.inst Rest Env Pos [[Rel Row] | Neg] Cmp (+ I 1) K))))
  [[capcov.pos Rel Terms] | Rest] Env Pos Neg Cmp I K ->
    (capcov.inst-rows (capcov.candidates Rel Terms Env) Rel Terms Rest Env Pos Neg Cmp I K))

(define capcov.inst-rows
  [] _ _ _ _ _ _ _ _ _ -> capcov.continue
  [Row | Rows] Rel Terms Rest Env Pos Neg Cmp I K ->
    (do (capcov.tick (cn "matching " Rel))
        (let Env2 (capcov.unify Terms Row Env)
          (if (= Env2 capcov.none)
              (capcov.inst-rows Rows Rel Terms Rest Env Pos Neg Cmp I K)
              (let R (capcov.inst Rest Env2 [[I Rel Row] | Pos] Neg Cmp (+ I 1) K)
                (if (= R capcov.continue)
                    (capcov.inst-rows Rows Rel Terms Rest Env Pos Neg Cmp I K)
                    R))))))

(define capcov.stop-value
  [capcov.stop V] -> V)

\\ ---------------------------------------------------------------- rules

\* elaborated rule record:
   [Name Digest HeadRel HeadTerms Body Key RecursiveAtoms Kind Aggregation Stratum] *\

(define capcov.rule-name R -> (nth 1 R))
(define capcov.rule-digest R -> (nth 2 R))
(define capcov.rule-head-rel R -> (nth 3 R))
(define capcov.rule-head-terms R -> (nth 4 R))
(define capcov.rule-body R -> (nth 5 R))
(define capcov.rule-key R -> (nth 6 R))
(define capcov.rule-recursive-atoms R -> (nth 7 R))
(define capcov.rule-kind R -> (nth 8 R))
(define capcov.rule-aggregation R -> (nth 9 R))
(define capcov.rule-stratum R -> (nth 10 R))

(define capcov.term-json
  [capcov.v Name] -> (capcov.obj [(@p "name" Name)])
  [capcov.c C T] -> (capcov.obj [(@p "type" T) (@p "value" C)]))

(define capcov.atom-json
  Negated Rel Terms -> (capcov.obj [(@p "negated" Negated) (@p "relation" Rel)
                                    (@p "terms" (capcov.arr (map (function capcov.term-json) Terms)))]))

(define capcov.body-item-json
  [capcov.pos Rel Terms] -> (capcov.atom-json false Rel Terms)
  [capcov.neg Rel Terms] -> (capcov.atom-json true Rel Terms)
  [capcov.cmp L Op R] -> (capcov.obj [(@p "left" (capcov.term-json L)) (@p "operator" Op) (@p "right" (capcov.term-json R))]))

(define capcov.aggregation-json
  capcov.null -> capcov.null
  [Name Rel GroupBy ValueVar Op Domain Closure] ->
    (capcov.obj [(@p "closure_witness" Closure) (@p "domain" Domain) (@p "group_by" (capcov.arr GroupBy))
                 (@p "name" Name) (@p "operator" Op) (@p "relation" Rel) (@p "value_variable" ValueVar)]))

(define capcov.raw-rule-json
  \\ Python canonical_dict(Rule): {"aggregation","body","head","name"}
  [Name Digest [HeadRel HeadTerms] Body Agg] ->
    (capcov.obj [(@p "aggregation" (capcov.aggregation-json Agg))
                 (@p "body" (capcov.arr (map (function capcov.body-item-json) Body)))
                 (@p "head" (capcov.atom-json false HeadRel HeadTerms))
                 (@p "name" Name)]))

(define capcov.positive-relations
  [] -> []
  [[capcov.pos Rel _] | Rest] -> [Rel | (capcov.positive-relations Rest)]
  [_ | Rest] -> (capcov.positive-relations Rest))

(define capcov.body-relations
  [] -> []
  [[capcov.pos Rel _] | Rest] -> [Rel | (capcov.body-relations Rest)]
  [[capcov.neg Rel _] | Rest] -> [Rel | (capcov.body-relations Rest)]
  [_ | Rest] -> (capcov.body-relations Rest))

(define capcov.check-rule-shape
  [Name Digest [HeadRel HeadTerms] Body Agg] -> (if (and (string? Name) (string? Digest) (string? HeadRel) (cons? Body))
                                                    ok
                                                    (error "capcov-invalid-input: malformed rule record ~A" Name))
  Other -> (error "capcov-invalid-input: malformed rule record"))

(define capcov.elaborate-rules
  \\ 1. canonical order (Python: sorted(rules, key=canonical_json))
  \\ 2. positive dependency graph, reachability, recursion structure
  \\ 3. strata
  Raw -> (let Checked (capcov.each (function capcov.check-rule-shape) Raw)
              Keyed (map (/. R (@p (capcov.json-of (capcov.raw-rule-json R)) R)) Raw)
              Sorted (sort (/. A B (capcov.str< (fst A) (fst B))) Keyed)
              Partial (map (/. P (capcov.partial-rule (snd P) (fst P))) Sorted)
           (do (capcov.record-edges Partial)
               (capcov.compute-strata Partial)
               (set capcov.*rules* (map (function capcov.finish-rule) Partial))
               (capcov.record-rules-by-head (value capcov.*rules*))
               (value capcov.*rules*))))

(define capcov.partial-rule
  [Name Digest [HeadRel HeadTerms] Body Agg] Key -> [Name Digest HeadRel HeadTerms Body Key [] capcov.plain Agg 0])

(define capcov.record-edges
  [] -> ok
  [R | Rs] -> (let H (capcov.rule-head-rel R)
                (do (capcov.meta-put (cn "edges:" H) (append (capcov.positive-relations (capcov.rule-body R)) (capcov.meta-get (cn "edges:" H) [])))
                    (capcov.record-edges Rs))))

(define capcov.edges
  Rel -> (capcov.meta-get (cn "edges:" Rel) []))

(define capcov.reach
  \\ relations reachable from Rel through positive rule bodies (memoized)
  Rel -> (let Cached (capcov.meta-get (cn "reach:" Rel) capcov.none)
           (if (= Cached capcov.none)
               (capcov.meta-put (cn "reach:" Rel) (capcov.bfs-reach (capcov.edges Rel) []))
               Cached)))

(define capcov.bfs-reach
  [] Seen -> Seen
  [R | Rs] Seen -> (if (element? R Seen)
                       (capcov.bfs-reach Rs Seen)
                       (capcov.bfs-reach (append Rs (capcov.edges R)) [R | Seen])))

(define capcov.recursive?
  Rel -> (element? Rel (capcov.reach Rel)))

(define capcov.same-scc?
  A B -> (or (= A B) (and (element? B (capcov.reach A)) (element? A (capcov.reach B)))))

(define capcov.recursive-atoms
  Head [] I -> []
  Head [[capcov.pos Rel _] | Rest] I -> (if (capcov.same-scc? Rel Head)
                                            [I | (capcov.recursive-atoms Head Rest (+ I 1))]
                                            (capcov.recursive-atoms Head Rest (+ I 1)))
  Head [_ | Rest] I -> (capcov.recursive-atoms Head Rest (+ I 1)))

(define capcov.finish-rule
  [Name Digest HeadRel HeadTerms Body Key _ _ Agg _] ->
    (let Rec (if (capcov.recursive? HeadRel) (capcov.recursive-atoms HeadRel Body 0) [])
         Kind (cond ((not (capcov.recursive? HeadRel)) capcov.plain)
                    ((empty? Rec) capcov.base)
                    ((= (length Rec) 1) capcov.step)
                    (true capcov.nonlinear))
      [Name Digest HeadRel HeadTerms Body Key Rec Kind Agg (capcov.stratum HeadRel)]))

(define capcov.stratum
  Rel -> (capcov.meta-get (cn "stratum:" Rel) 0))

(define capcov.compute-strata
  Rules -> (capcov.strata-round Rules 0 (+ 2 (length (value capcov.*relation-names*)))))

(define capcov.strata-round
  Rules Round Limit -> (do (set capcov.*unstratifiable* true) ok) where (> Round Limit)
  Rules Round Limit -> (do (set capcov.*changed* false)
                           (set capcov.*unstratifiable* false)
                           (capcov.strata-pass Rules)
                           (if (value capcov.*changed*)
                               (capcov.strata-round Rules (+ Round 1) Limit)
                               ok)))

(define capcov.strata-pass
  [] -> ok
  [R | Rs] -> (do (capcov.strata-rule (capcov.rule-head-rel R) (capcov.rule-body R)) (capcov.strata-pass Rs)))

(define capcov.strata-rule
  H [] -> ok
  H [[capcov.pos Rel _] | Rest] -> (do (capcov.raise-stratum H (capcov.stratum Rel)) (capcov.strata-rule H Rest))
  H [[capcov.neg Rel _] | Rest] -> (do (capcov.raise-stratum H (+ 1 (capcov.stratum Rel))) (capcov.strata-rule H Rest))
  H [_ | Rest] -> (capcov.strata-rule H Rest))

(define capcov.raise-stratum
  H S -> (if (> S (capcov.stratum H))
             (do (capcov.meta-put (cn "stratum:" H) S) (set capcov.*changed* true) ok)
             ok))

(define capcov.max-stratum
  [] M -> M
  [R | Rs] M -> (capcov.max-stratum Rs (if (> (capcov.rule-stratum R) M) (capcov.rule-stratum R) M)))

(define capcov.record-rules-by-head
  [] -> ok
  [R | Rs] -> (let H (capcov.rule-head-rel R)
                (do (capcov.meta-put (cn "rules:" H) (append (capcov.meta-get (cn "rules:" H) []) [R]))
                    (capcov.record-rules-by-head Rs))))

(define capcov.rules-for
  Rel -> (capcov.meta-get (cn "rules:" Rel) []))

(define capcov.rules-in-stratum
  S Rules -> (capcov.filter (/. R (= (capcov.rule-stratum R) S)) Rules))

(define capcov.require-executable
  \\ the closure and the search refuse constructs the workbench cannot evaluate
  -> (do (if (value capcov.*unstratifiable*)
             (error "capcov-unsupported-construct: negation through recursion has no stratification")
             ok)
         (capcov.each (/. R (if (= (capcov.rule-aggregation R) capcov.null)
                                ok
                                (error "capcov-unsupported-construct: rule ~A uses aggregation, which the workbench does not evaluate" (capcov.rule-name R))))
                      (value capcov.*rules*))
         ok))

\\ ---------------------------------------------------------------- bottom-up closure

(define capcov.closure
  -> (do (set capcov.*phase* capcov.closure)
         (capcov.require-executable)
         (capcov.eval-strata 0 (capcov.max-stratum (value capcov.*rules*) 0))
         ok))

(define capcov.eval-strata
  S Max -> ok where (> S Max)
  S Max -> (do (capcov.iterate (capcov.rules-in-stratum S (value capcov.*rules*)))
               (capcov.eval-strata (+ S 1) Max)))

(define capcov.iterate
  Rules -> (do (set capcov.*changed* false)
               (capcov.fire-all Rules)
               (if (value capcov.*changed*) (capcov.iterate Rules) ok)))

(define capcov.fire-all
  [] -> ok
  [R | Rs] -> (do (capcov.fire R) (capcov.fire-all Rs)))

(define capcov.fire
  R -> (let HeadRel (capcov.rule-head-rel R) HeadTerms (capcov.rule-head-terms R)
         (capcov.inst (capcov.rule-body R) [] [] [] [] 0
                      (/. Env Pos Neg Cmp
                          (do (if (capcov.add-row HeadRel (capcov.ground-row HeadTerms Env))
                                  (set capcov.*changed* true)
                                  ok)
                              capcov.continue)))))

\\ ---------------------------------------------------------------- derivation nodes

(define capcov.fact-node
  Rel Row -> (let Ids (capcov.evidence-of Rel Row)
               (if (empty? Ids)
                   (error "capcov-inconsistent: primitive row ~A~A has no attesting evidence" Rel (capcov.row-key Row))
                   [capcov.fact Rel Row Ids])))

(define capcov.rule-node
  Rule Row Premises Neg Cmp -> [capcov.rule-app (capcov.rule-name Rule) (capcov.rule-digest Rule) (capcov.rule-head-rel Rule) Row Premises Neg Cmp])

(define capcov.node-row
  [capcov.fact _ Row _] -> Row
  [capcov.rule-app _ _ _ Row _ _ _] -> Row)

\\ ---------------------------------------------------------------- top-down derivation (Horn clauses; mirrors certificate.py)

\* The derivation search is the rule's sequent form written as Shen Prolog
   clauses: capcov.derivation Rel Row Depth Node holds when Node derives
   Rel(Row), capcov.application Rule Row Depth Rec Node when Rule concludes
   Row from a first instantiation of its body, capcov.satisfies Body Env I
   Pos Neg Cmp when the body holds under Env (positive atoms matched against
   closure rows, negated atoms absent from the closure, comparisons true),
   and capcov.premises when every positive premise has a derivation one
   level deeper.  Python's extractor is reproduced exactly because the
   clause search order IS the canonical order: rules in capcov.rules-for
   order (sorted canonical rule keys), candidate rows in capcov.candidates
   order (canonical row order inside the narrowest index bucket), body atoms
   left to right, and a cut commits to the first instantiation.

   Bounds are side conditions, never failures: capcov.nest, capcov.tick and
   capcov.node-tick raise capcov-truncated / capcov-resource-exhausted at
   the same points, in the same order, as the list-recursive search they
   replace, so work, nodes and the truncation reason are unchanged.  A
   derivation of a closure row never fails either: every way it could fail
   (no rule applies, no base row, a stale step) is a named
   capcov-inconsistent / capcov-internal error, so committing before the
   premises are derived loses no derivation.

   Recursive relations keep the breadth-first strategy: the frontier is
   advanced by capcov.unvisited-predecessor (one linear step rule run
   backwards, enumerated with findall in discovery order and then sorted
   with capcov.sort-frontier), the parent table is the visited set, and the
   first frontier row with a base application is chained back to the
   requested row by re-applying each recorded step rule with its recursive
   premise fixed (capcov.chain).

   Shen data enters the queries ground (receive); every computed value is
   bound with is from a plain function, so no derivation result depends on
   hash or dictionary iteration order.  Arguments known to be ground once
   dereferenced one level (rules, rows, environments, terms) are passed to
   those functions as (1 X), which skips the full structural deref copy the
   kernel otherwise makes per call; lists the clauses build themselves
   (premises, satisfied rows, alternatives) are always fully dereferenced.
   A query's success path keeps its
   Prolog variables alive, and every derivation node, matched candidate and
   searched predecessor is a node tick, so capcov.derive sizes the binding
   store from max_nodes and the longest rule body (capcov.derive-memory);
   overflowing it is reported as capcov-resource-exhausted, not as a crash. *\

(defprolog capcov.member
  X [X | _] <--;
  X [_ | Xs] <-- (capcov.member X Xs);)

(define capcov.max-body
  [] M -> M
  [R | Rs] M -> (capcov.max-body Rs (if (> (length (capcov.rule-body R)) M) (length (capcov.rule-body R)) M)))

(define capcov.derive-memory
  \\ per node tick: the derivation/application frame plus one frame per body
  \\ atom (the go_app derivations keep about 5 variables alive per node)
  -> (+ 1000 (* (+ 1 (value capcov.*max-nodes*)) (+ 8 (* 4 (capcov.max-body (value capcov.*rules*) 0))))))

(define capcov.why-not-memory
  \\ a why-not query keeps alive only the attempt of one rule body
  -> (+ 1000 (* 32 (capcov.max-body (value capcov.*rules*) 0))))

(define capcov.binding-store
  \\ the shen-go message for a write past the end of the Prolog binding vector
  Size Message -> (if (= Message (make-string "index ~A out of range ~A" Size Size))
                      (error "capcov-resource-exhausted: derivation exceeds the Prolog binding store of ~A variables" Size)
                      (simple-error Message)))

(define capcov.derive
  \\ the canonical derivation of Rel(Row) at nesting Depth, as one Prolog query
  Rel Row Depth -> (let Size (capcov.derive-memory)
                     (do (prolog-memory Size)
                         (trap-error (prolog? (capcov.derivation (receive Rel) (receive Row) (receive Depth) Node)
                                              (return Node))
                                     (/. E (capcov.binding-store Size (error-to-string E)))))))

(define capcov.derivation-kind
  \\ the side conditions of entering one node: nesting, node budget, closure membership
  Rel Row Depth ->
    (do (capcov.nest Depth)
        (capcov.node-tick (cn "deriving " Rel))
        (let Decl (capcov.decl Rel)
          (cond ((= Decl capcov.none) (error "capcov-inconsistent: unknown relation ~A" Rel))
                ((capcov.decl-primitive? Decl)
                 (if (capcov.present? Rel Row)
                     capcov.fact
                     (error "capcov-inconsistent: primitive row ~A~A is not in the closure" Rel (capcov.row-key Row))))
                ((not (capcov.present? Rel Row))
                 (error "capcov-inconsistent: row ~A~A is not in the closure" Rel (capcov.row-key Row)))
                ((capcov.recursive? Rel) capcov.recursive)
                (true capcov.plain)))))

(define capcov.underivable
  Rel Row -> (error "capcov-inconsistent: no rule derives ~A~A from the closure" Rel (capcov.row-key Row)))

(defprolog capcov.derivation
  Rel Row Depth Node <-- (is Kind (capcov.derivation-kind (1 Rel) (1 Row) (1 Depth)))
                         (capcov.derivation-by Kind Rel Row Depth Node);)

(defprolog capcov.derivation-by
  capcov.fact Rel Row _ Node <-- (is Node (capcov.fact-node (1 Rel) (1 Row)));
  capcov.plain Rel Row Depth Node <-- (capcov.rule-for Rel Rule) (capcov.application Rule Row Depth capcov.none Node) !;
  capcov.plain Rel Row _ _ <-- (when (capcov.underivable Rel Row));
  capcov.recursive Rel Row Depth Node <-- (capcov.chain-search Rel Row Depth Node);)

(defprolog capcov.rule-for
  Rel Rule <-- (is Rules (capcov.rules-for (1 Rel))) (capcov.member Rule Rules);)

(defprolog capcov.application
  \\ Rec = capcov.none, or [I Node]: the I-th premise must be Node's row and is Node
  Rule Row Depth Rec [capcov.rule-app Name Digest Rel Row Premises Neg Cmp] <--
    (is Env (capcov.unify (capcov.rule-head-terms (1 Rule)) (1 Row) []))
    (when (not (= (1 Env) capcov.none)))
    (is Body (capcov.rule-body (1 Rule)))
    (capcov.satisfies Body Env 0 Pos Neg Cmp)
    (capcov.recursive-premise Rec Pos)
    !
    (is Name (capcov.rule-name (1 Rule)))
    (is Digest (capcov.rule-digest (1 Rule)))
    (is Rel (capcov.rule-head-rel (1 Rule)))
    (capcov.premises Pos Rec Depth Premises);)

(define capcov.ticked?
  What -> (do (capcov.tick What) true))

(define capcov.negated-row
  Rel Terms Env -> (let Row (capcov.ground-row Terms Env)
                     (if (capcov.fully-ground? Row)
                         Row
                         (error "capcov-inconsistent: negated atom ~A is not ground at check time" Rel))))

(defprolog capcov.satisfies
  \\ positives are [Index Rel Row], negatives [Rel Row], comparisons [L Op R]
  [] _ _ [] [] [] <--;
  [[capcov.cmp L Op R] | Body] Env I Pos Neg [[LV Op RV] | Cmp] <--
    (when (capcov.holds? (1 L) (1 Op) (1 R) (1 Env)))
    (is LV (capcov.ground (1 L) (1 Env)))
    (is RV (capcov.ground (1 R) (1 Env)))
    (is J (+ (1 I) 1))
    (capcov.satisfies Body Env J Pos Neg Cmp);
  [[capcov.neg Rel Terms] | Body] Env I Pos [[Rel Row] | Neg] Cmp <--
    (is Row (capcov.negated-row (1 Rel) (1 Terms) (1 Env)))
    (when (not (capcov.present? (1 Rel) (1 Row))))
    (is J (+ (1 I) 1))
    (capcov.satisfies Body Env J Pos Neg Cmp);
  [[capcov.pos Rel Terms] | Body] Env I [[I Rel Row] | Pos] Neg Cmp <--
    (is Rows (capcov.candidates (1 Rel) (1 Terms) (1 Env)))
    (capcov.member Row Rows)
    (when (capcov.ticked? (cn "matching " (1 Rel))))
    (is Env2 (capcov.unify (1 Terms) (1 Row) (1 Env)))
    (when (not (= (1 Env2) capcov.none)))
    (is J (+ (1 I) 1))
    (capcov.satisfies Body Env2 J Pos Neg Cmp);)

(defprolog capcov.concludes
  [capcov.fact _ Row _] Row <--;
  [capcov.rule-app _ _ _ Row _ _ _] Row <--;)

(defprolog capcov.recursive-premise
  capcov.none _ <--;
  [I Node] Pos <-- (capcov.concludes Node Row) (capcov.member [I PRel Row] Pos) !;)

(defprolog capcov.premises
  [] _ _ [] <--;
  [[I Rel Row] | Pos] Rec Depth [Node | Nodes] <--
    (capcov.premise I Rel Row Rec Depth Node)
    (capcov.premises Pos Rec Depth Nodes);)

(defprolog capcov.premise
  I _ _ [I Node] _ Node <-- !;
  _ Rel Row _ Depth Node <-- (is Deeper (+ (1 Depth) 1)) (capcov.derivation Rel Row Deeper Node);)

\\ recursion: breadth-first backwards through the linear step rules, with an
\\ explicit parent table as the visited set; the derivation chain is rebuilt
\\ from the table

(define capcov.split-rules
  \\ (@p BaseRules StepRules) for Rel; a non-linear recursive rule is unsupported
  Rel -> (capcov.split-h (capcov.rules-for Rel) [] []))

(define capcov.split-h
  [] Base Step -> (@p (reverse Base) (reverse Step))
  [R | Rs] Base Step -> (cond ((= (capcov.rule-kind R) capcov.base) (capcov.split-h Rs [R | Base] Step))
                              ((= (capcov.rule-kind R) capcov.step) (capcov.split-h Rs Base [R | Step]))
                              ((= (capcov.rule-kind R) capcov.plain) (capcov.split-h Rs [R | Base] Step))
                              (true (error "capcov-unsupported-construct: rule ~A is non-linear recursive" (capcov.rule-name R)))))

(define capcov.base-rules
  Rel -> (fst (capcov.split-rules Rel)))

(define capcov.step-rules
  Rel -> (snd (capcov.split-rules Rel)))

(define capcov.rk
  Rel Row -> (cn Rel (cn "|" (capcov.skey Row))))

(define capcov.parent-get
  Parent Rel Row -> (capcov.assoc-row [Rel Row] (capcov.ht-get (capcov.rk Rel Row) Parent []) capcov.none))

(define capcov.parent-put
  Parent Rel Row Link -> (let Key (capcov.rk Rel Row)
                           (capcov.ht-put Key [(@p [Rel Row] Link) | (capcov.ht-get Key Parent [])] Parent)))

(define capcov.parent-table
  Rel Row -> (let Parent (capcov.ht-new 1021)
               (do (capcov.parent-put Parent Rel Row capcov.root) Parent)))

(define capcov.within-steps?
  Rel Steps -> (if (> Steps (value capcov.*max-depth*))
                   (error "capcov-truncated: recursive derivation of ~A exceeds max_depth=~A steps" Rel (value capcov.*max-depth*))
                   true))

(define capcov.note-steps
  Steps -> (do (if (> Steps (value capcov.*max-steps*)) (set capcov.*max-steps* Steps) ok) true))

(define capcov.visit!
  \\ true (after a node tick) when PredRel(Pred) is reached for the first time
  Parent Rel PredRel Pred Link -> (if (= (capcov.parent-get Parent PredRel Pred) capcov.none)
                                      (do (capcov.tick (cn "searching " Rel))
                                          (capcov.parent-put Parent PredRel Pred Link)
                                          true)
                                      false))

(define capcov.sort-frontier
  \\ Python: sorted by (relation, canonical row key); NUL-joined text orders identically
  Items -> (capcov.sort-by-key (/. Item (cn (nth 1 Item) (cn (value capcov.*nul*) (capcov.row-key (nth 2 Item))))) Items))

(define capcov.next-frontier
  \\ Found is findall's (reversed) discovery order
  Rel Row [] -> (error "capcov-inconsistent: recursive row ~A~A has no base derivation within the closure" Rel (capcov.row-key Row))
  _ _ Found -> (capcov.sort-frontier (reverse Found)))

(define capcov.stale-step
  -> (error "capcov-internal: recorded step instantiation no longer applies"))

(defprolog capcov.chain-search
  Rel Row Depth Node <-- (is Parent (capcov.parent-table Rel Row))
                         (capcov.bfs Rel Row [[Rel Row]] Parent Depth 0 Node);)

(defprolog capcov.bfs
  Rel Row Frontier Parent Depth Steps Node <--
    (when (capcov.within-steps? Rel Steps))
    (capcov.bfs-step Rel Row Frontier Parent Depth Steps Node);)

(defprolog capcov.bfs-step
  _ _ Frontier Parent Depth Steps Node <--
    (capcov.base-in Frontier Depth Steps Item Base) !
    (when (capcov.note-steps Steps))
    (capcov.chain Parent Item Base Depth Steps Node);
  Rel Row Frontier Parent Depth Steps Node <--
    (findall Pred (capcov.unvisited-predecessor Rel Frontier Parent Pred) Found)
    (is Next (capcov.next-frontier Rel Row Found))
    (is More (+ Steps 1))
    (capcov.bfs Rel Row Next Parent Depth More Node);)

(defprolog capcov.base-in
  \\ the first frontier row (in order) with a base application at nesting Depth + Steps
  Frontier Depth Steps [R Rw] Base <--
    (capcov.member [R Rw] Frontier)
    (is Rules (capcov.base-rules (1 R)))
    (capcov.member Rule Rules)
    (is At (+ Depth Steps))
    (capcov.application Rule Rw At capcov.none Base);)

(defprolog capcov.predecessor
  \\ step rule Rule concludes R(Rw) with PredRel(Pred) as its RecIdx-th premise
  R Rw Rule RecIdx PredRel Pred <--
    (is Rules (capcov.step-rules (1 R)))
    (capcov.member Rule Rules)
    (is Env (capcov.unify (capcov.rule-head-terms (1 Rule)) (1 Rw) []))
    (when (not (= (1 Env) capcov.none)))
    (is Body (capcov.rule-body (1 Rule)))
    (capcov.satisfies Body Env 0 Pos Neg Cmp)
    (is RecIdx (hd (capcov.rule-recursive-atoms (1 Rule))))
    (capcov.member [RecIdx PredRel Pred] Pos);)

(defprolog capcov.unvisited-predecessor
  Rel Frontier Parent [PredRel Pred] <--
    (capcov.member [R Rw] Frontier)
    (capcov.predecessor R Rw Rule RecIdx PredRel Pred)
    (when (capcov.visit! Parent Rel PredRel Pred [[R Rw] Rule RecIdx]));)

(defprolog capcov.chain
  Parent [Rel Row] Node Depth Remaining Out <--
    (is Link (capcov.parent-get (1 Parent) (1 Rel) (1 Row)))
    (capcov.chain-link Link Parent Node Depth Remaining Out);)

(defprolog capcov.chain-link
  capcov.root _ Node _ _ Node <-- !;
  [[PRel PRow] Rule RecIdx] Parent Node Depth Remaining Out <--
    (is At (+ Depth (- Remaining 1)))
    (capcov.application Rule PRow At [RecIdx Node] Rebuilt) !
    (is Left (- Remaining 1))
    (capcov.chain Parent [PRel PRow] Rebuilt Depth Left Out);
  _ _ _ _ _ _ <-- (when (capcov.stale-step));)

\\ ---------------------------------------------------------------- why-not (bounded missing-premise alternatives)

\* For a row absent from the closure, capcov.attempt Rel Row Depth Alt
   enumerates, in the same canonical clause order as the derivation, every
   attempt to conclude it that stops: per rule, a head that does not unify,
   or a body walked left to right (matched positive rows are kept as
   satisfied premises) up to its first failing premise (a positive atom no
   candidate row matches, a negated atom that is present or not ground, or a
   false comparison).  A missing derived premise that is fully ground is
   explained one level deeper.  capcov.wn-alternatives records each attempt
   as it is found (a failure-driven loop), so the *max-alternatives* bound,
   *max-why-not-depth* and the work budget stop the enumeration at exactly
   the attempt, and tick, where they are exceeded; the result carries an
   explicit truncated flag. *\

(define capcov.why-not
  Rel Row -> (do (set capcov.*alts* [])
                 (set capcov.*alt-count* 0)
                 (set capcov.*wn-truncated* false)
                 (set capcov.*wn-reason* capcov.null)
                 (prolog-memory (capcov.why-not-memory))
                 (trap-error (capcov.wn-alternatives Rel Row 0)
                             (/. E (if (capcov.prefix? "capcov-truncated: " (error-to-string E))
                                       (do (set capcov.*wn-truncated* true)
                                           (set capcov.*wn-reason* (capcov.str-after (error-to-string E) 18)))
                                       (error (error-to-string E)))))
                 (reverse (value capcov.*alts*))))

(define capcov.wn-alternatives
  Rel Row Depth -> (do (prolog? (capcov.attempt (receive Rel) (receive Row) (receive Depth) Alt)
                                (when (capcov.recorded-then-fail Alt)))
                       ok))

(define capcov.recorded-then-fail
  [Name Digest Env Sat Missing] -> (do (capcov.record-alt Name Digest Env Sat Missing) false))

(define capcov.primitive-relation?
  Rel -> (let Decl (capcov.decl Rel)
           (if (= Decl capcov.none)
               (error "capcov-invalid-input: unknown relation ~A" Rel)
               (capcov.decl-primitive? Decl))))

(define capcov.missing-fact
  Rel Row -> (capcov.obj [(@p "kind" "fact") (@p "relation" Rel) (@p "row" (capcov.arr Row))
                          (@p "detail" "no evidence attests this primitive row")]))

(define capcov.missing-rule
  Rel Row -> (capcov.obj [(@p "kind" "no-rule") (@p "relation" Rel) (@p "row" (capcov.arr Row))
                          (@p "detail" "no rule concludes this relation")]))

(define capcov.head-alt
  Rule Row -> [(capcov.rule-name Rule) (capcov.rule-digest Rule) [] []
               [(capcov.obj [(@p "kind" "head") (@p "relation" (capcov.rule-head-rel Rule)) (@p "row" (capcov.arr Row))
                             (@p "detail" "rule head does not unify with the requested row")])]])

(define capcov.comparison-alt
  Rule L Op R Env Sat -> [(capcov.rule-name Rule) (capcov.rule-digest Rule) Env Sat
                          [(capcov.obj [(@p "kind" "comparison") (@p "left" (capcov.wn-term L Env)) (@p "operator" Op) (@p "right" (capcov.wn-term R Env))])]])

(define capcov.absent?
  Rel Terms Env -> (let Row (capcov.ground-row Terms Env)
                     (and (capcov.fully-ground? Row) (not (capcov.present? Rel Row)))))

(define capcov.absence-alt
  Rule Rel Terms Env Sat -> (let Row (capcov.ground-row Terms Env)
                              [(capcov.rule-name Rule) (capcov.rule-digest Rule) Env Sat
                               [(capcov.obj [(@p "kind" "absence") (@p "relation" Rel) (@p "row" (capcov.arr (capcov.partial-row Terms Env)))
                                             (@p "detail" (if (capcov.fully-ground? Row) "negated row is present in the closure" "negated atom is not ground"))])]]))

(define capcov.none-unify?
  _ [] _ -> true
  Terms [Row | Rows] Env -> (if (= (capcov.unify Terms Row Env) capcov.none) (capcov.none-unify? Terms Rows Env) false))

(define capcov.premise-alt
  \\ the nested explanation is computed (and its alternatives counted) before this one is recorded
  Rule Rel Terms Env Sat Depth -> (let Row (capcov.ground-row Terms Env)
                                       Nested (capcov.wn-nested Rel Row Depth)
                                    [(capcov.rule-name Rule) (capcov.rule-digest Rule) Env Sat
                                     [(capcov.obj [(@p "kind" "premise") (@p "relation" Rel) (@p "row" (capcov.arr (capcov.partial-row Terms Env)))
                                                   (@p "alternatives" Nested)])]]))

(defprolog capcov.attempt
  Rel Row _ [capcov.null capcov.null [] [] [Missing]] <--
    (when (capcov.primitive-relation? Rel)) ! (is Missing (capcov.missing-fact Rel Row));
  Rel Row _ [capcov.null capcov.null [] [] [Missing]] <--
    (when (empty? (capcov.rules-for Rel))) ! (is Missing (capcov.missing-rule Rel Row));
  Rel Row Depth Alt <-- (capcov.rule-for Rel Rule) (capcov.rule-attempt Rule Row Depth Alt);)

(defprolog capcov.rule-attempt
  Rule Row Depth Alt <-- (is Env (capcov.unify (capcov.rule-head-terms (1 Rule)) (1 Row) []))
                         (capcov.attempt-from Env Rule Row Depth Alt);)

(defprolog capcov.attempt-from
  capcov.none Rule Row _ Alt <-- ! (is Alt (capcov.head-alt Rule Row));
  Env Rule _ Depth Alt <-- (is Body (capcov.rule-body (1 Rule))) (capcov.blocked Rule Body Env [] Depth Alt);)

(defprolog capcov.blocked
  \\ Alt is where an attempt at the rest of Rule's body under Env stops
  Rule [[capcov.cmp L Op R] | Body] Env Sat Depth Alt <--
    (when (capcov.holds? (1 L) (1 Op) (1 R) (1 Env))) ! (capcov.blocked Rule Body Env Sat Depth Alt);
  Rule [[capcov.cmp L Op R] | _] Env Sat _ Alt <--
    (is Alt (capcov.comparison-alt Rule L Op R Env Sat));
  Rule [[capcov.neg Rel Terms] | Body] Env Sat Depth Alt <--
    (when (capcov.absent? (1 Rel) (1 Terms) (1 Env))) ! (capcov.blocked Rule Body Env Sat Depth Alt);
  Rule [[capcov.neg Rel Terms] | _] Env Sat _ Alt <--
    (is Alt (capcov.absence-alt Rule Rel Terms Env Sat));
  Rule [[capcov.pos Rel Terms] | Body] Env Sat Depth Alt <--
    (is Rows (capcov.candidates (1 Rel) (1 Terms) (1 Env)))
    (capcov.blocked-at Rows Rule Rel Terms Body Env Sat Depth Alt);)

(defprolog capcov.blocked-at
  \\ every matching candidate is walked on; with none, the premise itself is missing
  Rows Rule Rel Terms Body Env Sat Depth Alt <--
    (capcov.member Row Rows)
    (when (capcov.ticked? (cn "why-not " (1 Rel))))
    (is Env2 (capcov.unify (1 Terms) (1 Row) (1 Env)))
    (when (not (= (1 Env2) capcov.none)))
    (capcov.blocked Rule Body Env2 [[Rel Row] | Sat] Depth Alt);
  Rows Rule Rel Terms _ Env Sat Depth Alt <--
    (when (capcov.none-unify? (1 Terms) (1 Rows) (1 Env)))
    (is Alt (capcov.premise-alt Rule Rel Terms Env Sat Depth));)

(define capcov.partial-row
  Terms Env -> (map (/. T (let V (capcov.ground T Env)
                            (if (= V capcov.unbound) (capcov.obj [(@p "variable" (nth 2 T))]) V)))
                    Terms))

(define capcov.record-alt
  Name Digest Env Sat Missing ->
    (do (set capcov.*alt-count* (+ 1 (value capcov.*alt-count*)))
        (set capcov.*alts* [(capcov.obj [(@p "rule" Name) (@p "rule_digest" Digest)
                                         (@p "bindings" (capcov.obj (capcov.env-pairs Env [])))
                                         (@p "satisfied" (capcov.arr (map (/. S (capcov.obj [(@p "relation" (nth 1 S)) (@p "row" (capcov.arr (nth 2 S)))])) (reverse Sat))))
                                         (@p "missing" (capcov.arr Missing))])
                            | (value capcov.*alts*)])
        (if (>= (value capcov.*alt-count*) (value capcov.*max-alternatives*))
            (error "capcov-truncated: why-not alternatives exceed max_alternatives=~A" (value capcov.*max-alternatives*))
            ok)))

(define capcov.env-pairs
  [] Seen -> []
  [(@p K V) | Rest] Seen -> (if (element? K Seen) (capcov.env-pairs Rest Seen) [(@p K V) | (capcov.env-pairs Rest [K | Seen])]))

(define capcov.wn-nested
  \\ explain a fully ground missing derived premise one level deeper (bounded)
  Rel Row Depth -> (let Decl (capcov.decl Rel)
                     (if (and (capcov.fully-ground? Row)
                              (and (not (= Decl capcov.none))
                                   (and (not (capcov.decl-primitive? Decl))
                                        (< Depth (value capcov.*max-why-not-depth*)))))
                         (let Saved (value capcov.*alts*)
                           (do (set capcov.*alts* [])
                               (capcov.wn-alternatives Rel Row (+ Depth 1))
                               (let Nested (reverse (value capcov.*alts*))
                                 (do (set capcov.*alts* Saved)
                                     (capcov.arr Nested)))))
                         capcov.null)))

(define capcov.wn-term
  T Env -> (let V (capcov.ground T Env) (if (= V capcov.unbound) (capcov.obj [(@p "variable" (nth 2 T))]) V)))

\\ ---------------------------------------------------------------- entry point

(define capcov.load-bundle
  -> (do (capcov.reset-state)
         (capcov.load-decls (value capcov.*in-decls*))
         (capcov.elaborate-rules (value capcov.*in-rules*))
         (capcov.freeze-pack)
         ok))

(define capcov.check-request-row
  Rel Row -> (let Decl (capcov.decl Rel)
               (cond ((= Decl capcov.none) (error "capcov-invalid-input: unknown relation ~A" Rel))
                     ((not (cons? Row)) (error "capcov-invalid-input: requested row must be a non-empty list"))
                     ((not (= (length Row) (capcov.decl-arity Decl)))
                      (error "capcov-invalid-input: requested row has arity ~A, ~A declares ~A" (length Row) Rel (capcov.decl-arity Decl)))
                     (true ok))))

(define capcov.run
  [capcov.compile-spec] -> (capcov.spec-elaborate)
  [capcov.authority] -> (do (capcov.load-bundle) (capcov.authority-json))
  [capcov.derive Rel Row] -> (do (capcov.load-bundle)
                                 (capcov.check-request-row Rel Row)
                                 (capcov.load-facts (value capcov.*in-facts*))
                                 (capcov.closure)
                                 (set capcov.*phase* capcov.derive)
                                 (capcov.derive-json Rel Row))
  [capcov.why-not Rel Row] -> (do (capcov.load-bundle)
                                  (capcov.check-request-row Rel Row)
                                  (capcov.load-facts (value capcov.*in-facts*))
                                  (capcov.closure)
                                  (set capcov.*phase* capcov.why-not)
                                  (capcov.why-not-json Rel Row))
  Other -> (error "capcov-invalid-input: unknown request ~S" Other))

(define capcov.error-json
  Message -> (capcov.json-chunks (capcov.obj [(@p "kind" "error") (@p "error" Message)])))

(define capcov.emit
  \\ results are printed chunk by chunk: pr of one large string is quadratic here
  Chunks -> (let Out (stoutput)
              (do (pr (value capcov.*nl*) Out)
                  (pr (value capcov.*begin*) Out)
                  (pr (value capcov.*nl*) Out)
                  (capcov.each (/. C (pr C Out)) Chunks)
                  (pr (value capcov.*nl*) Out)
                  (pr (value capcov.*end*) Out)
                  (pr (value capcov.*nl*) Out)
                  ok)))

(define capcov.main
  -> (let Out (trap-error (capcov.run (value capcov.*in-request*)) (/. E (capcov.error-json (error-to-string E))))
       (capcov.emit Out)))
