# West Bengal State Portal source audit

Reviewed on 12 July 2026 for the official Government of West Bengal portal.

## Approved discovery surface

- Listing: `https://wb.gov.in/documents-notification.aspx`
- Owner: Information & Cultural Affairs Department, Government of West Bengal
- Documents: direct HTTPS PDFs below `https://wb.gov.in/upload/`
- Categories: announcements, jobs, schemes, education notices and government services
- Interval: six hours
- Initial cap: newest three listing rows

## Safety and permission checks

- `https://wb.gov.in/robots.txt` returned `User-agent: *` and `Allow: /`.
- `https://wb.gov.in/copyright-policy.aspx` permits accurate reproduction with
  prominent source acknowledgement, except separately identified third-party material.
- `https://wb.gov.in/terms-of-use.aspx` requires users to verify information with
  the relevant department. The pipeline therefore links the official PDF, validates
  extracted claims against that PDF and does not treat the listing title as evidence.
- Strict TLS verification succeeded. No redirects, certificate overrides or access
  controls are bypassed.

## Verified selectors

```text
item:  #ContentPlaceHolder1_gv > tr
title: td:first-child p
link:  td:first-child > a[href]
date:  td:nth-of-type(2)
```

Header and pager rows do not contain all required nodes and are ignored. Links leaving
`wb.gov.in` are rejected before a request is made. If the selectors, policies, robots
rules or TLS behavior change, disable the source until this audit is repeated.
