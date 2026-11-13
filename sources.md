# Primary sources

Consulted while writing this pack (2026-11-13/14). The harness itself
makes network calls only to the public read-only ledger endpoint listed
under "Live network snapshot"; every other source below was consulted
at authoring time, and the facts taken from each are listed so a
reviewer can re-check them.

## Standards

- NIST FIPS 204, *Module-Lattice-Based Digital Signature Standard*
  (ML-DSA), final, 13 Aug 2024. ML-DSA derived from
  CRYSTALS-Dilithium; parameter sets ML-DSA-44/65/87 (categories
  2/3/5); public keys 1,312/1,952/2,592 bytes; private keys
  2,560/4,032/4,896 bytes; signatures 2,420/3,309/4,627 bytes
  (Tables 1–2); key generation from a 32-byte seed
  (`ML-DSA.KeyGen_internal`, §6). Used for: all ML-DSA sizes in
  `record_inventory.md`, `mitigation_design.md` and the results page.
  Verified against the NIST-published tables via secondary summaries
  consulted 2026-11-13, which quote Tables 1–2 verbatim.
- NIST FIPS 205, *Stateless Hash-Based Digital Signature Standard*
  (SLH-DSA), final, 13 Aug 2024. SLH-DSA derived from SPHINCS+;
  signatures 7,856–49,856 bytes. Used for: background only; no
  finding in this pack depends on SLH-DSA sizes.
- RFC 8032 (IRTF, Jan 2017), *Edwards-Curve Digital Signature Algorithm
  (EdDSA)*: Ed25519 public keys 32 bytes, signatures 64 bytes,
  ~128-bit security level. Used for: the Ed25519 size claims, which
  the sample also measures directly (142 signatures, all 64 bytes).
- NIST IR 8547, *Transition to Post-Quantum Cryptography Standards*,
  final, Oct 2026: quantum-vulnerable public-key algorithms deprecated
  after 2030 and disallowed after 2035. Used for: background only;
  no finding rests on the exact dates.

## Quantum threat model

- P. W. Shor, "Polynomial-Time Algorithms for Prime Factorization and
  Discrete Logarithms on a Quantum Computer", *SIAM Journal on
  Computing* 26(5), 1997 (arXiv:quant-ph/9508027): factoring and
  discrete logarithms in polynomial time — breaks RSA, DH, ECDH, ECDSA
  and EdDSA. Used for: every "forgeable" rating in the inventory.
- L. K. Grover, "A fast quantum mechanical algorithm for database
  search", 1996 (arXiv:quant-ph/9605043): unstructured search in ~√N
  steps — halves effective symmetric/hash strength. Used for: the
  hash-chain safety claims (SHA-512Half 256-bit → ~128-bit preimage
  resistance) and the never-exposed-account claim (160-bit address
  hash → ~80-bit quantum preimage work).
- Brassard, Høyer, Tapp (quantum collision finding): quantum collision
  search in ~N^(1/3) steps — used for the ~85-bit figure for
  SHA-256-class collision resistance in the inventory.

## Upstream ledger documentation (xrpl.org)

- "Configure Full History": in its default configuration an `xrpld`
  server automatically deletes outdated history as new ledger versions
  become available; full history needs `online_delete` removed and
  `[ledger_history] full`. Used for: the retention finding (the public
  node keeps ~71,386 ledgers).
- "Configure Online Deletion": by default a server deletes history
  older than the most recent 2,000 ledger versions (~15 minutes at
  3–4 s per ledger); new ledgers are usually validated 3–4 s apart.
  Used for: the close-interval context for the measured 3.04 s mean.
- "Ledger History": `server_info` reports available history in
  `complete_ledgers`; full-history servers collect all history and do
  not use online deletion. Used for: the archival-history open
  question.
- "Validation" stream reference (js.xrpl.org, ValidationStream): the
  validations stream sends a message whenever the server receives a
  validation, whether or not it is from a trusted validator; flags
  `0x80000000` (fully-canonical signature) and `0x00000001` (full
  validation). Used for: the claim that validations are live-streamed
  messages, corroborating the code finding that they are not stored
  in ledgers.
- "Run xrpld as a Validator" and `validation_create` method reference:
  validator keys, tokens and rotation. Used for: background on the
  manifest lifecycle (see also the companion validator-key-lifecycle
  pack).

## Codebase facts (primary source: the pinned tree itself)

- postfiatd, commit `0085a1ff885d6a446369cf73a4430f75af22be55`
  ("Merge pull request #50 from postfiatorg/hotfix/upstream-hardening-1.0.9").
  All file:line citations in this pack come from this tree. The
  harness records the tree's `HEAD` commit in
  `results/summary.json` (`tree_check`), so a wrong tree is
  detectable.
- Upstream comparison: postfiatd `doVoting` is byte-identical to
  upstream rippled 2.5.0 (commit
  `1e01cd34f7a216092ed779f291b43324c167167a`); the only divergence is
  the amendment-majority threshold, 67/100 in postfiatd
  (`include/xrpl/protocol/SystemParameters.h:85`) vs 80/100 upstream.
  Source: the amendment-vote regression-test research notes
  (Nov 2026). Cited where quorum arithmetic matters; not re-derived.
- Companion packs on the same pinned tree (cited, not re-derived):
  the crypto inventory (production signatures are Ed25519 +
  secp256k1/ECDSA; 0 post-quantum mentions in the tree); the validator
  key-lifecycle pack (N=66 validators live, quorum 45/66 under the
  67% rule, two-tier keys, manifest sequence and revocation); the
  consensus-signature migration pack (37 consensus-path call sites,
  ML-DSA-65 sizes, 5-phase migration, no rollback after activation);
  the peer-overlay transport pack. Their published repository URLs
  are listed in `README.md` where a reviewer can find them.

## Live network snapshot

- Public JSON-RPC endpoint, https://rpc.testnet.postfiat.org/ (no
  credentials, no auth): `server_info` and `ledger` / `ledger_data`
  methods, fetched 2026-11-13T19:34:17Z. At fetch time: build 1.0.9,
  network_id 2025, validated ledger 8021439, complete_ledgers
  7950054–8021439. Used for: every measured number in `results/`.
  The raw fetch is vendored as `results/sample_ledger_data.json` and
  the per-request outcomes (including 3 failed ledger fetches) as
  `results/fetch_log.json`.
- PostFiat testnet explorer, https://explorer.testnet.postfiat.org/
  (fetched 2026-11-13): 66 validators listed, ledger ~8,016,789 at
  the time of the companion packs' fetch. Used for: background only;
  the validator count is not re-measured here.
