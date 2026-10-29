# Detection flags, risk signals and connection types

Branch on detection flags and on the band of the Risk Score. Use risk signals to explain a score
in logs and internal tools. The current list and weights are at
https://docs.shieldlabs.ai/features/risk-signals.

## Detection flags

Use these **20 detection flags**. A missing value is unknown.

| Flag | Meaning / handling |
|---|---|
| `vpn` | VPN evidence, including browser VPN/proxy evidence in History |
| `proxy` | Proxy evidence |
| `private_relay` | Privacy relay evidence; connection type is `private_relay` |
| `tor` | Tor evidence |
| `check_incomplete` | Browser check incomplete |
| `network_check_incomplete` | Network check incomplete; History column `is_stun_not_checked` |
| `os_not_detected` | OS not determined |
| `timezone_mismatch` | Time-zone mismatch |
| `javascript_disabled` | JavaScript features unavailable |
| `os_mismatch` | Reported and observed OS mismatch |
| `ip_mismatch` | IP mismatch context; do not treat it alone as fraud |
| `latency_test` | Latency-test flag; preserve it without inventing thresholds |
| `anti_detect_browser` | Anti-detect browser evidence |
| `device_spoofing` | Device-spoofing evidence |
| `banned_ip` | Banned IP; check the `999` marker separately |
| `incognito` | Private browsing |
| `search_bot` | Search crawler |
| `ai_bot` | AI-bot classification |
| `browser_automation` | Browser automation |
| `ai_browser` | AI-browser classification |

The AI flags are booleans; this SDK model does not expose a `bot_info` identity object. Do not invent bot names,
providers, categories, confidence or verified identity from these flags. Scope any blocking to
the requested protected action; preserve legitimate crawler access to public pages.

## Risk signals

`signals` lists the weighted reasons behind the Risk Score as `{ name, weight }`.
Use the names and weights returned with that identification for display and logging.

Rules:

- The set is open: new names appear without an SDK release. Keep unknown names, never fail on
  them, and never model them as a closed enum.
- Weights can be negative and a name can appear more than once (for example `network_check_incomplete`
  and its `stun_late_correction`). Never add weights up to rebuild or check the score.
- Descriptions on History rows are free text: never branch on them.

## Connection types

`connection_type` is one of `direct`, `mobile`, `vpn`, `proxy`, `tor`, `private_relay`,
`browser_vpn_proxy` or `unknown`; keep unknown values. It describes the network for display. For
decisions use the flags: `connection_type` can say `vpn` while `detection_flags.vpn` is `false`,
when IP intelligence suggests a VPN that the scored check did not confirm.

## Countries and IPs

`public_ip.country` and `local_ip.country` are English country names (`"Germany"`,
`"United States"`) or `""`. IPs are IPv4 strings, or `""` when unknown (for example for visitors on
IPv6). Compare countries for account checks (shieldlabs-account-abuse skill) rather than
branching on `ip_mismatch`.
