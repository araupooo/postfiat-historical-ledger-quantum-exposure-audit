# Record-class inventory: what the ledger's history actually records

Pinned tree: postfiatd main commit
`0085a1ff885d6a446369cf73a4430f75af22be55`. Machine-readable form:
`record_inventory.csv`. Sampled counts come from the harness run in
`results/summary.json` (500 consecutive validated ledgers, 8020940 to
8021439, fetched 2026-11-13T19:34:17Z; 497 fetched, 3 failed).

## The headline correction

The ledger's permanently recorded history contains **one** signature-bearing
record class in meaningful quantity: **transactions**. Validations,
proposals, manifests and payment-channel claims are **not** recorded in
ledgers at all — they are ephemeral messages that exist only while they
are being gossiped or held in memory. A future quantum adversary cannot
harvest them from ledger history, because there is nothing to harvest:
they would have had to record the live traffic themselves. What the
ledger does record, permanently and publicly, is every transaction
signature ever validated — and with each one, the public key it was made
with. That is the harvest surface.

## R-01 — Single-signed transaction (the harvest surface)

- **Where recorded:** validated ledger, transaction plus metadata.
  The transaction ID itself is the hash of transaction plus signature
  (`STTx.cpp:94`, `HashPrefix::transactionID`, `HashPrefix.h:57`).
- **Scheme:** Ed25519 or secp256k1/ECDSA, dispatched by key type
  (`PublicKey.cpp:224-236`: a 33-byte key starting `0xED` is Ed25519,
  `0x02`/`0x03` is secp256k1). Single-signature verification is
  `STTx::checkSingleSign` (`STTx.cpp:452`) via `singleSignHelper`
  (`STTx.cpp:415`); the signed data is the transaction without signing
  fields prefixed by `txSign` (`STTx.cpp:188-199`,
  `HashPrefix.h:72`).
- **Sizes (measured in the sample):** public key 33 bytes; signature
  64 bytes for every one of the 142 sampled signatures, all Ed25519
  (`results/summary.json`, `signatures.ed25519_signature_bytes`).
  secp256k1 signatures are DER-encoded, 70–72 bytes in practice (two
  32-byte integers plus DER framing); the tree's proposal path enforces
  a 72-byte maximum (`RCLCxPeerPos.cpp:37-40`), and transaction
  verification uses the same `verifyDigest` path
  (`PublicKey.cpp:239`).
- **Sampled:** 142 signatures from 31 distinct accounts; 119 Payment,
  14 NFTokenMint, 9 NFTokenBurn; all `tesSUCCESS`
  (`results/summary.json`, `transactions.by_type`).
- **What forging enables:** a quantum adversary that recovers a private
  key from an exposed public key can submit arbitrary new transactions
  as that account — spend funds, set a new regular key, change account
  settings, mint or burn tokens — until the key is rotated out of use.
  Forging does **not** rewrite history: already-validated transactions
  are committed under the ledger's transaction hash, and replaying an
  old transaction is blocked by the consumed sequence number. The
  damage is entirely forward-looking, against accounts that still use
  a key that history has exposed.
- **What stays safe:** accounts that have never transacted and never
  published a key. An account address is `RIPEMD-160(SHA-256(public
  key))` (`AccountID.cpp:168`, comment at lines 145–146), so the public
  key of a never-transacting account is hidden behind a 160-bit hash.
  Recovering it needs a hash preimage (Grover: ~2^80 work), not a
  discrete logarithm. Once an account transacts even once, its public
  key is permanently public.

## R-02 — Multi-signed transaction

- **Where recorded:** validated ledger, `Signers` array. Each signer
  entry carries `Account`, `SigningPubKey` and `TxnSignature`, all
  required (`InnerObjectFormats.cpp:39-45`). Verification is
  `STTx::checkMultiSign` (`STTx.cpp:581`) over per-signer data prefixed
  by `txMultiSign` (`Sign.cpp:96-107`, `HashPrefix.h:75`). A
  transaction cannot be both single- and multi-signed
  (`STTx.cpp:420-425`).
- **Sampled:** 0. No multi-signed transaction occurred in the 500-ledger
  sample. This is a sample property, not a protocol property:
  multi-signing is fully supported by the code above.
- **What forging enables:** forging one signer's key yields one share.
  A multi-signed transaction still needs its signer quorum, so a
  single broken key does not authorise the transaction. The defence
  holds only while the quorum exceeds the number of broken signer keys;
  if the adversary breaks keys for a quorum of signers, the protection
  collapses exactly as in R-01. Multi-signing therefore buys time and
  key diversity, not immunity.

## R-03 — Batch transaction signature

- **Where recorded:** validated ledger, `BatchSigners` array
  (`STTx.cpp:314`). Verification is `STTx::checkBatchSign`
  (`STTx.cpp:300`), dispatching per signer to `checkBatchSingleSign`
  (`STTx.cpp:463`) or `checkBatchMultiSign` (`STTx.cpp:555`), over
  data prefixed by `batch` (`HashPrefix.h:93`).
- **Sampled:** 0. No batch transaction occurred in the sample.
- **What forging enables:** same as R-01/R-02 per batch signer. A
  batch transaction authorises a set of inner transactions, so one
  forged batch signature can authorise several transactions at once —
  the blast radius per forged key is wider than a single transaction.

## R-04 — Cross-chain attestation signature

- **Where recorded:** validated ledger, inside XChain transactions.
  Each attestation element carries `AttestationSignerAccount`,
  `PublicKey` and `Signature`, all required
  (`InnerObjectFormats.cpp:84-110`; `XChainAttestations.cpp:111`).
- **Sampled:** 0. No XChain transaction occurred in the sample.
- **What forging enables:** forging an attestation lets an adversary
  manufacture apparent cross-chain agreement for a claim or an account
  creation. Because attestations ride inside transactions, they are
  permanently recorded exactly like R-01 — the same harvest applies,
  with the same remedy (rotate attestation keys, and treat old
  attestations as suspect once the scheme is broken).

## R-05 — Payment-channel claim

- **Where recorded:** nowhere in the ledger, until redeemed. A claim
  is an off-ledger signed message: `CLM\0` followed by the channel and
  the amount (`PayChan.cpp:103-108`), verified at redemption
  (`PayChan.cpp:469-486`) against the channel's public key, which is
  the one public key stored directly in a ledger entry
  (`ltPAYCHAN sfPublicKey`, `ledger_entries.macro:375`).
- **Sampled:** 0 observable. Claims cannot be counted from ledger data
  by construction.
- **What forging enables:** redeeming the channel balance to the
  adversary. The exposure window is the channel's lifetime: the key is
  public from the moment the channel is created, and a claim signed
  under it is valid until the channel closes or the key changes. The
  ledger cannot help here — it never sees the claim — so the defence
  must be at the channel: short settle delays, prompt closure, and
  key rotation on channel renewal.

## R-06 — Validation

- **Where recorded:** nowhere permanent. A validation carries
  `SigningPubKey` and `Signature`, both required
  (`STValidation.cpp:72-73`), signed over the `VAL`-prefixed hash
  (`STValidation.cpp:93-95`, `HashPrefix.h:78`) and verified by
  `isValid()` via `verifyDigest` (`STValidation.cpp:123-146`).
  Validations are **secp256k1-only by construction**: the signing
  constructor refuses any other key type
  (`STValidation.h:249-250`) and deserialization throws on a
  non-secp256k1 signing key (`STValidation.h:201-209`). They are kept
  only in memory (`Validations.h:306`, `315-323`: `current_` and aged
  maps; no persistence layer) and are relayed over the peer protocol.
- **Sampled:** 0, by construction. No RPC method returns historical
  validations, and no ledger contains them.
- **What forging enables:** impersonating a validator in live
  consensus. With a quorum of forged validations an adversary could
  validate a false ledger. But the historical angle is narrow: the
  adversary cannot harvest past validations from the ledger, and a
  forged validation is only useful while it is current (it votes for a
  specific ledger hash at a specific close time). The durable exposure
  is the validator's public key, published via its manifest (R-08) —
  breaking that key is what makes forged validations possible at all.
  Quorum arithmetic from the companion work: 45 of 66 validators under
  the 67% rule (53 under the 80% rule); a single broken validator key
  buys nothing.

## R-07 — Consensus proposal

- **Where recorded:** nowhere permanent. A proposal carries a signature
  verified by `RCLCxPeerPos::checkSign()` via `verifyDigest`
  (`RCLCxPeerPos.cpp:48-51`) over the `PRP`-prefixed signing hash
  (`HashPrefix.h:81`). The tree caps proposal signatures at 72 bytes
  (`RCLCxPeerPos.cpp:37-44`).
- **Sampled:** 0, by construction.
- **What forging enables:** influencing a live consensus round by
  forging a validator's position. Like validations, proposals are
  useful only while current, and they are not archived in the ledger.
  The same validator-key exposure as R-06 applies.

## R-08 — Validator manifest

- **Where recorded:** nowhere in the ledger. A manifest binds a master
  public key to an ephemeral signing key, with a sequence number
  (`Manifest.cpp:62-81`). Verification checks two signatures — the
  ephemeral signature and the master signature — under the `MAN`
  prefix (`Manifest.cpp:196-213`, `HashPrefix.h:84`). Sequence
  `0xFFFFFFFF` is a permanent revocation of the master key
  (`Manifest.cpp:236-240`). Manifests accept either key type
  (`Manifest.cpp:97-142`).
- **Sampled:** 0, by construction. Manifests are distributed via the
  validator site and the peer protocol, not via ledgers.
- **What forging enables:** breaking a validator's master key lets an
  adversary publish a forged manifest binding a new ephemeral key to
  that validator's identity, and then forge validations (R-06) under
  it — until the master key is revoked by a higher-sequence manifest.
  The master key is the long-lived secret: ephemeral keys rotate, and
  breaking an old ephemeral key buys nothing once its manifest is
  superseded, but the master key's exposure never expires while the
  manifest is current. Rotation of the ephemeral key bounds ephemeral
  exposure; only master-key rotation (a new validator identity)
  bounds master exposure.

## R-09 — Ledger header

- **Where recorded:** every validated ledger. The ledger hash is
  `SHA-512Half` over the `ledgerMaster` prefix plus sequence, drops,
  parent hash, transaction hash, account hash, close times, resolution
  and flags (`Ledger.cpp:54-71`, `HashPrefix.h:69`); the header fields
  are serialised by `addRaw` (`LedgerHeader.cpp:28-41`). There is no
  signature field anywhere in the header.
- **Sampled:** 497 headers; 493 consecutive parent-hash links checked,
  0 breaks (`results/summary.json`, `chain_linkage`).
- **What forging enables:** nothing. Rewriting a validated header
  requires a hash preimage or collision, not a broken signature key.
  SHA-512Half is a 256-bit hash: Grover's algorithm halves preimage
  resistance to ~128 bits and quantum collision search to ~85 bits —
  both far beyond any foreseeable adversary. The hash chain is the
  part of history that a quantum adversary cannot rewrite, and it is
  what anchors every signature-bearing record above it.

## R-10 — Ledger entries (state)

- **Where recorded:** validated ledger state. The tree defines 30
  entry types (`ledger_entries.macro:45-559`), all sharing only
  `LedgerEntryType` and `Flags` as common fields
  (`LedgerFormats.cpp:32-36`). No entry type carries a signature
  field. Exactly one field in the whole macro is a public key:
  `ltPAYCHAN sfPublicKey` (line 375). Two near-misses that are not
  signatures: `sfSignatureReward` is an amount, not a signature
  (`sfields.macro:284`, type `AMOUNT` — it is the reward paid to
  attestation signers); `ltSIGNER_LIST` entries name signer accounts
  with weights, not keys (`InnerObjectFormats.cpp:31-37` — Account,
  SignerWeight, WalletLocator).
- **Sampled:** first page of ledger 8021439 (server returned 256
  entries for a requested limit of 400; more pages exist): 240
  AccountRoot, 7 LedgerHashes, 4 NFTokenPage, 3 NFTokenOffer,
  2 DirectoryNode; 0 entries carrying a public key
  (`results/entry_type_census.csv`).
- **What forging enables:** nothing against the entry itself — entries
  are authenticated by the ledger hash chain (R-09) and the validation
  quorum at close time, not by a per-entry signature. The exposure
  flows through what entries point at: a payment channel's key (R-05),
  a signer list's accounts (R-02), an account's regular key. Forging a
  signature does not change stored state; it lets the adversary issue
  new transactions that change state through the normal path.

## What stays safe (summary)

1. **Validated history itself.** Transactions already in validated
   ledgers cannot be altered by forging a signature: they sit under
   the transaction hash, the account hash, and the SHA-512Half header
   chain, all of which are hash-based and quantum-resistant at
   ~128-bit preimage security. Sequence numbers also block replay of
   old transactions.
2. **Never-exposed keys.** An account that has never transacted, never
   set a regular key, never validated and never opened a payment
   channel has its public key hidden behind the 160-bit address hash.
   Its key cannot be recovered from the ledger at all.
3. **Quorum structures.** Multi-signed transactions and the validator
   quorum both require more than one broken key. A single broken key
   buys nothing against either — until the adversary holds a quorum.
4. **Hash-based records.** Ledger hashes, skip lists (`ltLEDGER_HASHES`),
   transaction IDs and entry indexes are all hashes; Grover's algorithm
   only halves their strength, leaving them far out of reach.

## Notes and caveats

- The `credential` hash prefix (`HashPrefix.h:90`, `CRD`) is defined
  in the tree but no signing use of it was found in the non-test
  sources; credentials are not listed as a separate record class
  here. If credential signing exists in a later tree, it belongs in
  this inventory as a new class.
- secp256k1 signature sizes (70–72 bytes DER) are stated from the
  encoding, not measured: the sample contained no secp256k1
  transaction signature. The 72-byte bound is the tree's own
  (`RCLCxPeerPos.cpp:37-40`); the 70-byte lower bound is the DER
  minimum for two 32-byte integers with full-length framing.
- The sample's scheme split (142 Ed25519, 0 secp256k1) describes the
  accounts active on this testnet in this window, not the protocol:
  both schemes are fully supported by the verification code.
