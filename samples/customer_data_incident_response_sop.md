# Customer Data Incident Response SOP

## Document Control

- Document Owner: Security Operations Manager
- Version: 3.4
- Effective Date: 2026-01-15
- Review Cycle: Quarterly
- Classification: Internal Confidential
- Related Policies:
  - Information Security Policy
  - Privacy Incident Notification Policy
  - Access Control Standard
  - Backup and Recovery Standard

---

## 1. Purpose

This SOP defines the standard process for identifying, triaging, containing, investigating, remediating, communicating, and closing incidents involving suspected or confirmed exposure of customer data. The objective is to reduce harm, preserve evidence, meet legal and contractual obligations, and restore normal operations safely.

---

## 2. Scope

This SOP applies to all production systems, cloud services, endpoints, integrations, databases, file stores, logging platforms, and third-party processors that handle any of the following:

- Customer names
- Email addresses
- Phone numbers
- Billing addresses
- Payment-related metadata
- Authentication identifiers
- Support case content
- Exported operational reports that contain customer records

This SOP must be used when the incident involves one or more of the following conditions:

- Unauthorized access to a system containing customer data
- Accidental sharing or misdelivery of customer records
- Malicious exfiltration or suspected data theft
- Misconfigured storage bucket or public asset exposing customer data
- Lost endpoint containing unencrypted customer exports
- Third-party vendor notification of a security event affecting shared customer data

---

## 3. Roles and Responsibilities

### 3.1 Incident Commander

The Incident Commander owns the end-to-end coordination of the response, declares severity, approves major containment actions, and ensures the timeline is maintained.

### 3.2 Security Analyst

The Security Analyst performs initial triage, validates indicators, preserves evidence, performs log analysis, and recommends containment and eradication steps.

### 3.3 Engineering Lead

The Engineering Lead executes approved technical actions in production, validates service health after containment, and coordinates remediation changes.

### 3.4 Privacy Counsel

Privacy Counsel determines regulatory notification obligations, reviews customer-facing statements, and approves wording for legal or privacy disclosures.

### 3.5 Customer Support Lead

The Customer Support Lead prepares macros, internal FAQs, escalation paths, and staffing plans if customer communication is required.

### 3.6 Executive Stakeholder

The designated executive stakeholder must be informed for Severity 1 incidents and must approve any public statement or broad customer communication.

---

## 4. Severity Classification

### Severity 1

Use Severity 1 if any of the following is true:

- Confirmed exposure of highly sensitive customer data
- Evidence of active exfiltration still in progress
- Incident affects more than 10,000 customer records
- Media, regulator, or law enforcement involvement is already present
- Business-critical services are unavailable due to containment or compromise

### Severity 2

Use Severity 2 if any of the following is true:

- Likely exposure of customer data with incomplete scope
- Confirmed unauthorized access with no proof of exfiltration yet
- Incident affects between 500 and 10,000 customer records
- Third-party processor reports a credible event affecting shared data

### Severity 3

Use Severity 3 if any of the following is true:

- Suspicious behavior requires investigation but exposure is unconfirmed
- Limited internal misconfiguration with no evidence of external access
- Incident affects fewer than 500 customer records and is quickly contained

---

## 5. Trigger Conditions

Start this SOP immediately when any of the following inputs are received:

- SIEM alert indicating abnormal export, download, or access pattern
- Cloud security tool alert for public storage or permissive IAM policy
- Ticket from support, compliance, or engineering reporting exposed customer information
- Vendor or partner security notice referencing shared customer data
- External report from a customer, researcher, or law firm

If the event is later shown to be a false positive, the Incident Commander may downgrade or close the incident with a documented rationale.

---

## 6. Required Systems and Evidence Sources

The following systems should be checked as early as possible, depending on relevance:

- Identity provider sign-in logs
- Cloud audit logs
- Production application logs
- Database audit trails
- Endpoint detection alerts
- Reverse proxy and CDN request logs
- Ticketing and change management history
- Object storage access logs
- Data warehouse query logs
- Backup job history

Evidence must be collected in a way that preserves timestamps, actor identifiers, and original event detail.

---

## 7. Response Timeline Targets

- Acknowledge alert or report within 15 minutes
- Severity assigned within 30 minutes
- Incident bridge opened within 30 minutes for Severity 1 and Severity 2
- Initial containment recommendation within 60 minutes
- Executive notification within 60 minutes for Severity 1
- Legal/privacy review started within 90 minutes if customer data exposure is plausible
- First written status update within 2 hours
- Customer notification decision within the regulatory or contractual deadline

---

## 8. Initial Triage Procedure

1. Open an incident record in the incident tracker.
2. Assign an Incident Commander and Security Analyst.
3. Record the source of detection, time of detection, and reporting party.
4. Confirm whether production customer data may be involved.
5. Capture the affected systems, accounts, integrations, and environments.
6. Determine whether the event appears active, historical, or unresolved.
7. Classify the incident severity using the criteria in Section 4.
8. Create a working timeline and begin logging all decisions.
9. Preserve screenshots, alert payloads, raw logs, and ticket references.
10. Notify the Engineering Lead if technical containment may be required.

---

## 9. Evidence Preservation Procedure

1. Export relevant logs before making containment changes where feasible.
2. Capture object identifiers, user IDs, IP addresses, request IDs, and timestamps.
3. Preserve database audit entries related to queried or exported records.
4. Save copies of IAM policy changes, deployment changes, and configuration diffs.
5. Hash exported evidence bundles when possible and record the hash in the incident record.
6. Do not delete malicious artifacts until the Security Analyst confirms evidence is sufficient.
7. If an endpoint is involved, isolate the host before powering it down unless memory capture is explicitly required.

---

## 10. Containment Decision Tree

### 10.1 Active Unauthorized Session

If an active unauthorized session is confirmed:

1. Revoke the session immediately.
2. Reset credentials or tokens for the affected identity.
3. Block suspicious IP addresses or network ranges if justified.
4. Require MFA re-authentication where supported.
5. Document the exact time and owner of each containment action.

### 10.2 Public Storage Exposure

If a bucket, blob container, file share, or report endpoint is publicly exposed:

1. Remove public access immediately.
2. Snapshot the configuration before and after the change.
3. Review access logs to estimate exposure duration and scope.
4. Identify any downstream caches, mirrors, or indexing engines that may have accessed the data.

### 10.3 Malicious Export or Query Activity

If malicious export or bulk query activity is suspected:

1. Disable or restrict the offending account.
2. Pause scheduled exports, integrations, or report jobs that may propagate data.
3. Evaluate whether database read replicas, caches, or analytics copies are also impacted.
4. Seek Incident Commander approval before taking any action that could disrupt billing, authentication, or customer-facing production workflows.

---

## 11. Mandatory Approval Gates

The following actions require Incident Commander approval before execution:

- Disable production integrations used by customers
- Block a privileged internal service account
- Shut down a production workload handling customer traffic
- Invalidate all active user sessions platform-wide
- Notify customers or regulators
- Approve any public, media, or investor-facing statement

The following actions require Privacy Counsel approval before execution:

- Send a data breach notification to customers
- Notify a regulator or supervisory authority
- Share detailed incident scope with an external third party

The following actions require Executive Stakeholder approval before execution:

- Publish a public disclosure
- Authorize a broad service suspension impacting customer operations
- Approve financial remediation offers or credits at scale

---

## 12. Investigation Procedure

1. Determine the earliest known suspicious activity.
2. Determine the last known clean state, if possible.
3. Identify the initial access vector.
4. Identify affected identities, systems, and data sets.
5. Estimate the number of potentially affected customer records.
6. Determine whether the actor viewed, exported, altered, or deleted data.
7. Review whether backups or replicas contain the same exposed data.
8. Correlate the incident with recent deployments, config changes, or vendor updates.
9. Identify control failures that allowed the exposure.
10. Record confidence level and any unresolved assumptions.

---

## 13. Customer Impact Assessment

The Incident Commander and Privacy Counsel must assess:

- What specific data elements were exposed
- Whether the data was encrypted at rest and in transit
- Whether encryption keys or credentials may also be compromised
- Whether the data was likely accessed versus merely exposed
- Whether the impacted customers are concentrated in a regulated geography or segment
- Whether identity theft, fraud, phishing, or service misuse risk is elevated

If scope remains uncertain, the report must explicitly say so rather than implying certainty.

---

## 14. Communication Procedure

### Internal Updates

- Post the first internal status update within 2 hours
- Include severity, scope known/unknown, actions taken, blockers, and next update time
- Update the incident record after every major decision

### Customer Communication

If customer communication is approved:

1. Use approved legal language only.
2. State what happened, what data may be involved, what the company has done, and what the customer should do next.
3. Do not speculate about attribution without evidence.
4. Do not promise a date for final scope confirmation unless the team is confident.
5. Route support escalations to the prepared support playbook.

### Regulatory Communication

Any regulator communication must be reviewed by Privacy Counsel and recorded in the incident timeline with timestamp, recipient, and summary.

---

## 15. Eradication and Recovery

1. Remove malicious persistence, unauthorized accounts, exposed secrets, or vulnerable configurations.
2. Patch or harden the root-cause control gap.
3. Rotate affected credentials, tokens, keys, and service account secrets.
4. Validate that logging, alerting, and access controls are functioning after changes.
5. Restore any paused services in a staged manner.
6. Monitor closely for reoccurrence for at least 72 hours.
7. Do not declare recovery complete until the Incident Commander and Engineering Lead both confirm production health.

---

## 16. Closure Criteria

An incident may be closed only when all of the following are true:

- Containment is complete
- Root cause is documented or an explicit limitation statement is recorded
- Customer and regulatory notification decisions are documented
- Required remediations have owners and due dates
- Executive summary is completed
- Post-incident review is scheduled

---

## 17. Post-Incident Review Procedure

Within 5 business days of closure:

1. Conduct a retrospective with security, engineering, privacy, support, and incident leadership.
2. Review detection quality, escalation speed, evidence quality, approval delays, and communication effectiveness.
3. Identify at least one preventive action, one detective improvement, and one process improvement.
4. Assign owners and due dates to every action item.
5. Publish a concise internal summary for operational learning.

---

## 18. Common Failure Modes

- Evidence was overwritten because logs were not exported early enough
- Containment was delayed while the team debated severity
- Customers were notified before scope was adequately reviewed
- Production changes were made without documenting exact timestamps
- Public statements were issued without legal approval

---

## 19. Example Escalation Scenarios

### Scenario A: Public Storage Exposure

A report export container is discovered to be publicly accessible. The team must immediately remove public access, preserve configuration evidence, assess exposure duration, estimate the number of downloaded files, and seek approval before sending any external notification.

### Scenario B: Credential Compromise

A privileged support account authenticates from an unusual geography and accesses a large number of customer records. The team must revoke sessions, reset credentials, inspect audit logs, and determine whether customer records were merely viewed or exported.

### Scenario C: Vendor Notification

A third-party analytics processor reports unauthorized access to a shared processing environment. The team must validate contractual reporting obligations, map which customer data fields were shared, and determine whether customer communication is legally required.

---

## 20. Minimum Report Contents

The final incident report must include:

- Incident summary
- Severity and rationale
- Systems affected
- Data types potentially impacted
- Containment actions with timestamps
- Evidence sources reviewed
- Customer or regulator communication decisions
- Root cause or current hypothesis
- Remediation actions and owners
- Open risks or uncertainties

---

## 21. Appendix: Initial Response Checklist

- [ ] Incident ticket created
- [ ] Incident Commander assigned
- [ ] Severity assigned
- [ ] Timeline started
- [ ] Evidence export started
- [ ] Affected systems identified
- [ ] Containment strategy proposed
- [ ] Legal/privacy consulted if required
- [ ] Executive notified if required
- [ ] First status update sent

---

## 22. Appendix: Customer Notification Readiness Checklist

- [ ] Scope estimate documented
- [ ] Data elements listed
- [ ] Legal review completed
- [ ] Support macros prepared
- [ ] FAQ drafted
- [ ] Escalation manager assigned
- [ ] Approval recorded from required stakeholders

---

## 23. Appendix: Recovery Validation Checklist

- [ ] Secrets rotated
- [ ] Unauthorized access removed
- [ ] Monitoring enhanced
- [ ] Service health validated
- [ ] Backlog remediation items assigned
- [ ] Post-incident review scheduled
