# Hosted pubskill service

The hosted surface at `https://pubskill.interdependentway.org/` preserves two product questions:

- **Audit:** Which repository claims hold up, and which fail against the evidence?
- **Examiner:** What is actually in this codebase, how is it structured and documented, what can be measured safely, and where are the unresolved boundaries?

## Audit purchases

A complete single-repository audit costs **$5 USD**. Customers may purchase any positive number of audits in one checkout. The applicable total is calculated automatically from the selected quantity.

A single repository may first receive a three-finding free preview. For paid audits, repository URLs are supplied before checkout. The service stores the repository count and a SHA-256 digest of the ordered URL list in Stripe Checkout Session metadata, rather than storing an arbitrary number of repository URLs in Stripe metadata. The checkout amount is derived server-side from the selected repository count.

On return from Stripe, the browser resubmits the repository list. The service verifies live payment state, amount, repository count, and the URL-list digest before running the complete audits. The browser keeps the pending list only in session storage during checkout. If that state is lost, the service exposes the paid repository count so the customer can re-enter the same URLs and recover the purchase.

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
