# Risk Register

## R1: Prompt injection through files

Rule: file content is untrusted data, never instruction.

## R2: Unsafe shell command

Rule: no shell runner in Phase 0.

## R3: Scope creep

Rule: no future-phase features.

## R4: Approval fatigue

Rule: risk tiers must be meaningful.

## R5: Rollback overclaim

Rule: rollback is reliable for file edits only, not arbitrary shell effects.

## R6: Secret leakage

Rule: never index or send secrets.
