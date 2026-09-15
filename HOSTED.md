# Hosted pubskill service

The hosted surface at `https://pubskill.interdependentway.org/` preserves two product questions:

- **Audit:** Which repository claims hold up, and which fail against the evidence?
- **Examiner:** What is actually in this codebase, how is it structured and documented, what can be measured safely, and where are the unresolved boundaries?

## Audit purchases

The hosted audit supports two purchase sizes:

- one complete repository audit: **$5 USD**
- five complete repository audits: **$20 USD**

A single repository may first receive a three-finding free preview. Paid checkout is created only after the repository URL or five repository URLs have been supplied. The exact URLs and purchase tier are bound into Stripe Checkout Session metadata before payment; the return handler verifies live payment state, amount, tier, count, and repository URLs before running the complete audits.

Supported public HTTPS Git hosts are GitHub, GitLab, Bitbucket, Codeberg, and SourceHut. Target repository code is not executed.

## Operator access

`PUBSKILL_OPERATOR_CODE` configures a private server-side access code for demonstration and operator use. The value must be supplied as deployment secret/environment state; it must not be committed to this repository. The service compares the submitted code server-side and never stores it in repository state or browser storage.

Operator access runs the same complete one- or five-repository audit paths without creating a Stripe checkout.

## Deployment configuration

Required for paid checkout:

```text
STRIPE_SECRET_KEY
```

Required for private operator bypass:

```text
PUBSKILL_OPERATOR_CODE
```

Optional hosted URL overrides:

```text
PUBSKILL_SUCCESS_URL
PUBSKILL_CANCEL_URL
```

The defaults return successful checkout to `https://pubskill.interdependentway.org/?session_id={CHECKOUT_SESSION_ID}` and cancellation to the site root.

## Examiner boundary

Structural examination does not require AI. AI is optional for narration. Hosted Examiner execution, metering, and pricing remain `hmmm` until measured against real repository runs; the hosted site must not imply those capabilities are already available.
