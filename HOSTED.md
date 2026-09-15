# Hosted pubskill service

The hosted surface at `https://pubskill.interdependentway.org/` preserves two product questions:

- **Audit:** Which repository claims hold up, and which fail against the evidence?
- **Examiner:** What is actually in this codebase, how is it structured and documented, what can be measured safely, and where are the unresolved boundaries?

## Audit purchases

A complete repository audit costs **$5 USD**. Customers may purchase any positive number of audits in one checkout. For every group of five audits, the fifth is free:

- 1 audit: $5
- 4 audits: $20
- 5 audits: $20
- 6 audits: $25
- 10 audits: $40

The pricing rule is `paid_count = repository_count - floor(repository_count / 5)`.

A single repository may first receive a three-finding free preview. For paid audits, repository URLs are supplied before checkout. The service stores the repository count and a SHA-256 digest of the ordered URL list in Stripe Checkout Session metadata, rather than storing an arbitrary number of repository URLs in Stripe metadata. The Checkout line-item quantity equals the number of paid audits after applying the every-fifth-free rule.

On return from Stripe, the browser resubmits the repository list. The service verifies live payment state, amount, paid/free counts, repository count, and the URL-list digest before running the complete audits. The browser keeps the pending list only in session storage during checkout. If that state is lost, the service exposes the paid repository count so the customer can re-enter the same URLs and recover the purchase.

Supported public HTTPS Git hosts are GitHub, GitLab, Bitbucket, Codeberg, and SourceHut. Target repository code is not executed.

## Operator access

`PUBSKILL_OPERATOR_CODE` configures a private server-side access code for demonstration and operator use. The value must be supplied as deployment secret/environment state; it must not be committed to this repository. The service compares the submitted code server-side and never stores it in repository state or browser storage.

Operator access runs the same complete audit path for any positive number of repository URLs without creating a Stripe checkout.

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
