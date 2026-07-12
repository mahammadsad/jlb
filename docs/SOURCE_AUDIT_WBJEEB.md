# WBJEEB Current Events source audit

Reviewed on 12 July 2026 for the West Bengal Joint Entrance Examinations Board.

## Approved discovery surface

- Listing: `https://wbjeeb.nic.in/current-events/`
- Owner: West Bengal Joint Entrance Examinations Board
- Hosting: National Informatics Centre S3WaaS
- Documents: direct HTTPS PDFs on the exact host `cdnbbsr.s3waas.gov.in`
- Categories: admissions, results, examinations and education notices
- Interval: six hours
- Initial cap: newest three listing rows

## Safety and access checks

- `https://wbjeeb.nic.in/robots.txt` disallows `/wp-admin/` and does not disallow
  `/current-events/`.
- Strict TLS verification succeeded for the listing and linked documents.
- The page identifies WBJEEB as the content owner and NIC as developer/host.
- The S3WaaS document host did not return a robots file within 30 seconds. It is not
  used for discovery: only exact PDF links published by the allowed WBJEEB listing
  are fetched. The verifier keeps strict host, HTTPS, redirect and size controls.
- The integration publishes short factual summaries with prominent official-document
  links; it does not republish complete PDFs or third-party material.

## Verified selectors

```text
item:  .doc-table tbody > tr
title: td:first-child > a[href]
link:  td:first-child > a[href]
```

The first three live documents were inspected. Two yielded extractable official text;
one was an image scan and correctly remained manual-review-only. If the listing host,
NIC document host, selectors, robots rules or ownership changes, disable the source
until this audit is repeated.
