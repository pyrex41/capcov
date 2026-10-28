#!/bin/sh
# Offline source compiler. Inputs are verified by Nix or scripts/bootstrap.
# Run inside the pinned upstream source tree; BOOTSTRAP, KERNEL, OUTPUT absolute.
set -eu
bootstrap=$1
kernel=$2
output=$3
unset SHEN_SCHEME_HOME SHEN_SCHEME_RUNTIME
# The v0.52 C launcher is byte-identical in source to 8d26151. Only reuse it
# while this remains true; the Scheme runtime is rebuilt, never copied.
sh scripts/verify-sha256.sh e14255e360bf5f8b1c3ead79b195afb66a3b06dd988b66c78be3cd3219efae34 main.c
sh scripts/verify-sha256.sh 060066a8f84d9a2f7d41cb3b37b986a8d4653279752b739b5063cd648d9baacd "$kernel"
tar --no-same-owner -xzf "$kernel"
cp ShenOSKernel-43.1-ec16a9f/klambda/*.kl kl/
"$bootstrap/bin/shen-scheme" script scripts/do-build.shen > /dev/null
mkdir -p _build/obj/shen-scheme _build/lib/shen-scheme/shen-scheme
"$bootstrap/bin/shen-scheme" eval -q -e '(eval-kl [scm. "(parameterize ([command-line (list c#34;buildc#34; c#34;shen-scheme.scmc#34; c#34;_build/obj/main.soc#34; c#34;shen-scheme-runtime.ssc#34; c#34;_build/obj/shen-scheme/runtime.soc#34; c#34;_build/lib/shen-scheme/shen-scheme/runtime.soc#34; c#34;3c#34; c#34;0c#34; c#34;falsec#34; c#34;falsec#34;)]) (load c#34;scripts/build-runtime.ssc#34;))"])'
mkdir -p "$output/bin" "$output/lib/shen-scheme/shen-scheme"
cp "$bootstrap/bin/shen-scheme" "$output/bin/"
cp "$bootstrap/lib/shen-scheme/petite.boot" "$bootstrap/lib/shen-scheme/scheme.boot" "$output/lib/shen-scheme/"
cp _build/lib/shen-scheme/shen-scheme/runtime.so "$output/lib/shen-scheme/shen-scheme/"
test "$("$output/bin/shen-scheme" eval -e '(+ 20 22)')" = 42
test "$("$output/bin/shen-scheme" eval -e '(eval-kl [scm. "(procedure-arity-mask kl:shen.search-user-datatypes-h)"])')" = 128
printf '\316\273\351\233\252 caf\303\251' > _build/expected
printf '(pr "%s" (stoutput))\n' "$(cat _build/expected)" > _build/text.shen
"$output/bin/shen-scheme" script _build/text.shen > _build/actual
cmp _build/expected _build/actual
