# Mitigation design: checkpointing, re-signing of history, and historical proofs

Pinned tree: postfiatd main commit
`0085a1ff885d6a446369cf73a4430f75af22be55`. Measured inputs are from
`results/summary.json` (500 consecutive validated ledgers, 8020940 to
8021439, fetched 2026-11-13T19:34:17Z). ML-DSA sizes are NIST FIPS 204,
Table 2 (see `sources.md`). Cost figures that scale the sample to the
full history are **illustrative extrapolations**, labelled as such;
per-unit costs are exact arithmetic from measured or standard sizes.

## 0. What is actually at risk (from `record_inventory.md`)

- **Harvestable:** every transaction signature ever validated, with its
  public key. Sample: 142 signatures from 31 accounts in 497 ledgers,
  all Ed25519, 64 bytes each, 9,088 classical signature bytes total.
- **Not harvestable from the ledger:** validations, proposals,
  manifests, payment-channel claims. They are never recorded in a
  ledger; an adversary would have had to capture live traffic.
- **Not forgeable at all:** ledger headers and ledger entries. Their
  integrity is the SHA-512Half hash chain, which Grover's algorithm
  only weakens from 256-bit to ~128-bit preimage resistance.
- **The damage model is forward-looking.** Forging a key lets an
  adversary submit *new* transactions as the account. It does not let
  them alter validated history, replay consumed sequence numbers, or
  rewrite a ledger header.

## 1. The re-signing problem, stated honestly

Re-signing history in the literal sense — producing a post-quantum
signature over every historical transaction — is **not achievable**,
for two independent reasons:

1. **The private keys are gone.** A historical transaction can only be
   re-signed by the key that signed it, and those keys are held by
   users, many of whom have lost them, rotated them, or are no longer
   reachable. No operator, validator set or protocol upgrade can
   re-sign another account's transaction. Any plan that assumes
   otherwise is not a plan.
2. **The cost is large for no gain.** At the measured sample rate of
   0.2857 transactions per ledger, the full history of ~8,021,439
   ledgers holds on the order of 2.29 million transactions
   (illustrative extrapolation — see §6). Re-signing all of them with
   ML-DSA-65 would produce ~7.58 GB of signatures (2.29M × 3,309 B),
   against ~147 MB of classical signatures today (2.29M × 64 B), and
   would still not make the old signatures unforgeable: the classical
   signatures would remain in the history alongside the new ones, and
   a verifier that accepts either scheme accepts the broken one.

The honest substitute for re-signing is **checkpointing**: post-quantum
signatures over *hashes* of history, not over the transactions
themselves. A checkpoint says "this ledger hash, at this sequence, is
part of the canonical history, attested by these post-quantum keys".
It does not re-sign any transaction, and it does not need any user's
private key. What it does is give future verifiers a post-quantum
anchor: history before the checkpoint is authenticated by the checkpoint
signature plus the hash chain, rather than by the classical signatures
inside it.

## 2. Options compared

| Option | What it protects | Needs whose keys | Cost (from measured numbers) | Verdict |
|---|---|---|---|---|
| A. Full re-signing of historical transactions | Nothing extra: old classical signatures stay valid alongside | Every historical account's private key — unavailable | ~7.58 GB of ML-DSA-65 signatures for the extrapolated full history; 469,878 B for the 500-ledger sample alone (51.7× the measured 9,088 B) | **Not feasible.** Reject. |
| B. Validator-signed PQ checkpoints over ledger hashes | The integrity of history as a whole: a future verifier can trust that ledger N is canonical without trusting any classical signature | The checkpoint signers' post-quantum keys only (a small, known set) | One ML-DSA-65 signature (3,309 B) per checkpoint. Every 1,000 ledgers over full history: 8,021 checkpoints ≈ 26.5 MB total. Every 100 ledgers: ≈ 265 MB. Per checkpoint, trivial. | **Recommended.** Cheap, achievable, additive. |
| C. Hash-anchored external timestamping | Same as B, but the anchor lives outside the network (public timestamp log) | The timestamping service's keys | One hash (32 B) per checkpoint plus the service's fee/signature; storage negligible | **Recommended as a complement** to B. Independent of validator keys. |
| D. Key rotation + live PQ migration | Future transactions: stops the harvest from growing and retires exposed keys | Each account's and each validator's cooperation | Per account: one SetRegularKey-style transaction (one classical signature today, one PQ signature after migration). Per validator: one manifest. Live-signing cost per the companion consensus work: ML-DSA-65 adds ~50× signature bytes per ledger per node, verification faster than secp256k1. | **Required.** This is the only option that shrinks the live exposure. |
| E. Historical inclusion proofs on demand | Lets a third party prove a transaction is in a validated ledger without trusting a classical signature | The prover's access to an archival ledger copy | Per proof: one Merkle path, ~log2(entries) × 32 B plus one checkpoint signature (3,309 B). No bulk cost. | **Recommended** as a service, not as a migration. |
| F. Do nothing to history; migrate live signing only | Future transactions only; history keeps its classical signatures forever | As D | As D | **Minimum viable.** Acceptable only if B is judged unnecessary — but B is cheap enough that skipping it needs a reason. |

## 3. Phased plan

### Phase 0 — Inventory and monitoring (immediate, no protocol change)

- Publish this inventory and re-run the harness monthly to track the
  harvest surface: transactions per ledger, distinct accounts with
  exposed keys, scheme split (Ed25519 vs secp256k1), multi-signed
  share. The harness already supports this (`--live` re-fetch).
- Watch for the first accounts that rotate keys and for any
  multi-signed adoption; both reduce the exposed-key count per
  transaction.
- Exit criterion: a standing monthly measurement exists; no code
  change required.

### Phase 1 — Key hygiene (immediate, off-chain + user-facing)

- Tell holders plainly: any key that has ever signed a transaction is
  permanently public. Rotate it before a quantum adversary exists,
  not after. Rotation means issuing a new key and moving funds and
  authorisations to it; the old key's historical signatures remain
  valid history, but the old key authorises nothing new.
- Validators rotate ephemeral keys on their normal schedule (already
  supported by manifests) and treat master-key exposure as the
  critical event: a master key that has ever been published in a
  manifest must be assumed breakable, and its revocation path
  (sequence `0xFFFFFFFF`, `Manifest.cpp:236-240`) must be exercised
  promptly if compromise is suspected.
- Payment-channel operators: shorten settle delays and close channels
  promptly, since the channel key is public from creation
  (R-05).
- Exit criterion: documented rotation guidance exists; high-value
  accounts and validators confirm rotation.

### Phase 2 — Post-quantum checkpoints (the core of this design)

- **What:** at a fixed cadence (recommendation: every 1,000 ledgers),
  a quorum of designated checkpoint signers publishes a
  post-quantum-signed attestation over the ledger hash and sequence:
  `{ledger_index, ledger_hash, parent_hash, close_time}` signed with
  ML-DSA-65. Checkpoints are stored alongside the ledger (as a
  standalone record, not inside ledger state — ledger state has no
  signature field to hold one, R-10) and mirrored to at least one
  independent store.
- **Why 1,000 ledgers:** at the measured mean close interval of
  3.04 s, 1,000 ledgers is ~51 minutes of history per checkpoint.
  Cost over the full 8.02M-ledger history is 8,021 × 3,309 B ≈
  26.5 MB — negligible against any archival store. Tightening to
  every 100 ledgers costs ≈ 265 MB and buys a ~5-minute granularity
  that no verifier needs. Loosening to every 10,000 ledgers costs
  ≈ 2.65 MB but leaves ~8.4 hours of history per checkpoint, which
  is still fine; the choice is a policy knob, not a technical
  constraint.
- **Backfill:** checkpoints can be issued retroactively for any past
  ledger whose hash is known from an archival copy. The public node
  used for this audit retains only 71,386 ledgers (7950054–8021439,
  ≈ 2.5 days at the measured 3.04 s close interval), so backfill
  beyond that range needs an archival node or an explorer archive.
  Backfill is what makes Phase 2 cover history rather than only the
  future: issue checkpoints for every 1,000th ledger from genesis to
  the present, then keep issuing them live.
- **Verification rule:** a ledger version is trusted if either (a) it
  is covered by a valid PQ checkpoint and its hash chain links to a
  checkpointed ledger, or (b) it is validated by the live quorum
  under PQ signatures (after Phase 3). Classical signatures inside a
  checkpointed range are treated as historical evidence only, never
  as live authorisation.
- **Rollback:** none needed. Checkpoints are additive and monotonic:
  a new checkpoint never invalidates an old one, and a bad checkpoint
  (wrong hash) is simply ignored — it cannot rewrite the hash chain.
  If a checkpoint signer's key is compromised, revoke that signer and
  re-issue affected checkpoints under a new key; the ledger hashes
  themselves do not change.
- **Exit criterion:** checkpoints exist for every 1,000th ledger from
  the earliest available archival ledger to the present, and new ones
  are issued live.

### Phase 3 — Live post-quantum migration (protocol change)

- Follow the companion consensus migration design: dual signatures
  (classical + ML-DSA-65) during transition, then ML-DSA-only after
  the activation amendment enables. That design's numbers apply
  directly: ML-DSA-65 public key 1,952 B, signature 3,309 B (FIPS
  204, Table 2); per-ledger per-node verification is faster than
  secp256k1 in published benchmarks, and the cost is bandwidth (~50×
  signature bytes per ledger). Validation quorum arithmetic is
  unchanged (45 of 66 under the 67% rule).
- Account transactions migrate on the same pattern: dual-signed
  transactions during transition, so old clients keep working, then
  classical signatures are rejected for new transactions after the
  activation amendment. Historical transactions keep their classical
  signatures — they are covered by Phase 2 checkpoints instead.
- **No rollback after activation.** The amendment mechanism has no
  disable path for an enabled amendment; recovery from a bad
  activation is forward-only (a new amendment). This must be stated
  in the activation proposal, with a canary period on the testnet
  first.
- Exit criterion: new transactions and validations are ML-DSA-signed;
  classical signatures are rejected for new records.

### Phase 4 — Historical-proof service

- An archival node plus a proof endpoint: given a transaction hash,
  return the Merkle inclusion path to the transaction hash of its
  ledger, the ledger header, and the covering PQ checkpoint. Cost per
  proof is one path (~log2 of entries × 32 B) plus one checkpoint
  signature reference. This lets auditors, exchanges and courts verify
  a historical transaction without trusting any classical signature.
- Exit criterion: the endpoint answers inclusion proofs for any
  transaction in the retained or archived range.

### Phase 5 — Classical decommission

- Once Phases 2–4 are live and the activation amendment has enabled,
  classical verification code can be removed from the live path — but
  **not** from historical verification: old transactions still need
  classical verification for audit tooling that inspects pre-migration
  history without a checkpoint. Keep a clearly-labelled
  historical-only verification path.
- Exit criterion: no live path accepts a classical signature; the
  historical path is fenced and documented.

## 4. Cost summary (grounded in the measured sample)

Measured (sample, 497 ledgers, 142 transactions, 31 accounts):

| Quantity | Measured value | Source |
|---|---|---|
| Transactions per ledger | 0.2857 | `results/summary.json`, `transactions.mean_tx_per_ledger` |
| Classical signature bytes in sample | 9,088 B (142 × 64 B) | `results/summary.json`, `signatures.classical_signature_bytes_total` |
| Mean ledger close interval | 3.04 s | `results/ledger_sample.csv`, close_time span 1,508 s over 497 ledgers |
| Distinct accounts with exposed keys | 31 | `results/summary.json`, `transactions.distinct_accounts` |
| Chain links checked / breaks | 493 / 0 | `results/summary.json`, `chain_linkage` |
| Retained history on the public node | 71,386 ledgers (7950054–8021439) | `results/summary.json`, `server_info.complete_ledgers` |

Derived (exact arithmetic from the measured rate and FIPS 204 sizes):

| Quantity | Value | Method |
|---|---|---|
| Re-signing the sample with ML-DSA-65 | 469,878 B (142 × 3,309 B), 51.7× the measured classical bytes | Exact multiplication |
| Re-signing the sample with ML-DSA-44 | 343,640 B (142 × 2,420 B), 37.8× | Exact multiplication |
| Re-signing the sample with ML-DSA-87 | 657,034 B (142 × 4,627 B), 72.3× | Exact multiplication |
| Checkpoints every 1,000 ledgers, full history | ≈ 26.5 MB (8,021 × 3,309 B) | Exact multiplication |
| Checkpoints every 100 ledgers, full history | ≈ 265 MB (80,214 × 3,309 B) | Exact multiplication |

Illustrative extrapolation (labelled, not measured): at the sample rate
of 0.2857 transactions per ledger, the full ~8.02M-ledger history holds
on the order of 2.29M transactions; re-signing all of them with
ML-DSA-65 would be ~7.58 GB of signatures. This assumes the recent
activity rate holds across all of history, which is unlikely — early
history may be denser or sparser, and the testnet's activity is
bursty (the sample itself has 414 empty ledgers out of 497). Treat
2.29M and 7.58 GB as order-of-magnitude guides for sizing, not as
measurements. The per-unit costs in the table above are the solid
numbers; the extrapolation only exists to show that full re-signing is
expensive *and* impossible (§1), while checkpointing is cheap at any
plausible scale.

## 5. Rollback notes

- **Checkpoints (Phase 2):** no rollback. Additive, monotonic,
  verifiable independently of any other checkpoint. A compromised
  checkpoint signer is removed and affected checkpoints re-issued.
- **Key rotation (Phase 1):** rollback means re-authorising the old
  key, which re-opens the exposure — do not roll back rotation. If a
  rotation was done wrong (funds sent to the wrong key), the fix is a
  new transaction under the new key, not a return to the old one.
- **Live migration (Phase 3):** no protocol rollback after the
  activation amendment enables. The dual-signature transition phase
  is the rollback: while it lasts, classical signatures are still
  accepted, so disabling the new path is possible by not activating.
  Once activated, recovery is forward-only.
- **Historical-proof service (Phase 4):** stateless; no rollback.
  A wrong proof is detected by hash mismatch and rejected.

## 6. Open questions

1. **Archival history.** The public node retains only ~71,386 ledgers
   (~2.5 days). Is there an archival node or explorer archive holding
   the full history back to ledger 1, and who operates it? Without
   one, Phase 2 backfill cannot cover early history, and the
   extrapolation in §4 cannot be checked.
2. **Checkpoint signers.** Who holds the post-quantum checkpoint keys,
   how many signers, and what quorum? If the checkpoint signers are
   the validators themselves, a validator-key compromise affects both
   live consensus and checkpoints.
3. **Checkpoint storage.** Where do checkpoints live — a new ledger
   entry type, a sidecar store, or an external log? Ledger state has
   no signature field (R-10), so a new entry type or an external store
   is needed; that choice is a protocol decision.
4. **Historical rate.** What was the transaction rate in early history?
   The 2.29M-transaction extrapolation is untested. A full-history
   count from an archival node would settle it.
5. **Credential signing.** The `credential` hash prefix exists in the
   tree (`HashPrefix.h:90`) but no signing use was found in the
   non-test sources. If credentials are signed somewhere, they need
   the same treatment as R-01.
6. **Account key rotation uptake.** How many of the 31 sampled
   accounts (and, at scale, of all historical accounts) are still
   active under the same key? Rotation only helps accounts that
   actually rotate; dormant accounts with exposed keys stay exposed
   until they move.
7. **Validator master-key inventory.** How many validator master keys
   have ever been published in manifests, and are any of them still
   in use? Each one is a long-lived forgery target (R-08).
