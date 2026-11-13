# Assumptions and limits

Read before citing any number in this pack.

## A1. Sample, not census

The harness measures a **sample**: 500 consecutive validated ledgers
(8020940–8021439), of which 497 were fetched and 3 failed
(8020957, 8021042, 8021222 — server closed the connection or returned
a truncated response, 4 attempts each; see `results/fetch_log.json`).
All transaction, signature and account counts describe that sample
only. Nothing in this pack counts the full history: the public node
retains only 71,386 ledgers, and no full-history source was available.

## A2. Consecutive window, recent history

The window ends at the latest validated ledger at fetch time
(2026-11-13T19:34:17Z) and runs backwards 500 ledgers. It is a plain
slice of recent history, not cherry-picked for activity. Recent
testnet activity is sparse (414 of 497 ledgers empty) and bursty
(NFToken mint/burn clusters). Any extrapolation to the full history
(§4 of `mitigation_design.md`) assumes the sample rate holds across
all of history, which is unlikely; it is labelled illustrative.

## A3. Zero counts for ephemeral classes are structural, not measured

Validations, proposals, manifests and payment-channel claims score 0
in `record_class_counts.csv` because they are **not recorded in
ledgers** — the code keeps them in memory or gossips them live
(see `record_inventory.md` for the file:line evidence). The 0 means
"not countable from ledger data", not "none exist". Likewise the 0
multi-signed, 0 batch and 0 XChain-attestation counts mean "none in
this 500-ledger sample", not "none on the network".

## A4. Key-type split is a sample property

All 142 sampled signatures are Ed25519. Both Ed25519 and secp256k1 are
fully supported by the verification code (`PublicKey.cpp:224-236`),
and secp256k1 is mandatory for validations. A different window, or a
busier network, would show secp256k1 transactions. Do not cite "0
secp256k1" as a protocol fact.

## A5. Entry census is one page, not the state

The entry census is the first page of `ledger_data` on ledger
8021439. The request asked for a limit of 400; the server returned
256 entries and a continuation marker, so more pages exist and were
not fetched. The page is ordered by entry key (hash order), which is
effectively arbitrary with respect to entry type — but it is still
one page, not a random sample, and the type mix on later pages may
differ. In particular, the 0 key-carrying entries in this page does
not mean no payment channel or attestation entry exists in state;
it means none fell on this page.

## A6. No build, no run of the ledger

A full build of the ledger is not feasible on the audit machine (no
Conan, ~1 GB RAM available; the build needs Conan-managed
dependencies and a multi-GB toolchain). Nothing in this pack claims
the ledger was compiled or executed. The inventory is static analysis
of the pinned tree plus read-only RPC sampling.

## A7. No live peer connections

The harness talks only to the public JSON-RPC endpoint
(`server_info`, `ledger`, `ledger_data`). No peer connection, no
validation subscription, no manifest fetch, no write of any kind.
Anything about live validations, proposals or manifests comes from
reading the code and the upstream documentation, not from observing
the live peer network.

## A8. Signature sizes

Ed25519 signature size (64 bytes) is both specified (RFC 8032) and
measured (142/142 at 64 bytes). secp256k1 DER size (70–72 bytes) is
stated from the encoding; no secp256k1 transaction signature was
measured. The 72-byte bound is the tree's own, enforced on the
proposal path (`RCLCxPeerPos.cpp:37-40`).

## A9. Quantum figures are asymptotic, not engineering estimates

"Shor breaks Ed25519/secp256k1" and "Grover halves hash strength" are
asymptotic statements about the algorithms. This pack makes no claim
about when a cryptographically relevant quantum computer will exist,
how many qubits it needs, or how long a given key takes to break.
The exposure ratings are about *what becomes possible in principle*
once such a machine exists, not about a date.

## A10. The `credential` prefix

The `credential` hash prefix is defined (`HashPrefix.h:90`) but no
signing use of it was found in the non-test sources. If credential
signing exists elsewhere in the tree or in a later version, the
inventory needs a new record class. This is open question 5 in
`mitigation_design.md`.

## A11. Extrapolation method

The full-history figures in `mitigation_design.md` §4 are computed as
`sample rate × 8,021,439 ledgers`. The rate (0.2857 tx/ledger) comes
from this one 500-ledger window on a quiet testnet. The method and
its weakness are stated next to the figures; do not quote 2.29M
transactions or 7.58 GB as measured.
