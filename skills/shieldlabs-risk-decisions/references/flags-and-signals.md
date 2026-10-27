# Detection flags, risk signals and connection types

Branch on detection flags and on the band of the Risk Score. Use risk signals to explain a score
in logs and internal tools. The current list and weights are at
https://docs.shieldlabs.ai/features/risk-signals.

## Detection flags

The table below is the legacy 19-flag normalized model of the published Node 1.0.1 contract.
It is not the complete current wire model. Read [the SDK contract preflight](../../shieldlabs-server/references/sdk-contract.md)
before interpreting absent fields. Old SDKs default missing flags to false; that default is not
evidence that a newer detection was checked and absent.

| Flag | Set when | Notes |
|---|---|---|
| `vpn` | A VPN was detected | Common with privacy-minded and corporate users |
| `privacy_relay` | A privacy relay service was detected | Mostly legitimate users |
| `browser_vpn_proxy` | A VPN or proxy browser extension was detected | |
| `tor` | The request came from a Tor exit node | |
| `proxy` | A proxy was detected | |
| `datacenter_ip` | The IP belongs to a hosting or datacenter network | Unusual for a real visitor's browser |
| `abuser` | The IP has a history of abuse | |
| `os_mismatch` | The operating system the browser reports differs from the one seen on the network | A sign of a spoofed environment |
| `os_not_detected` | The operating system could not be determined | |
| `timezone_mismatch` | The browser time zone differs from the IP's time zone | Travellers and VPN users can trigger it |
| `anti_detect_browser` | A browser that masks its real configuration | Strong on its own |
| `browser_automation` | Automated or scripted browsing | Blocked by the SDK policy default |
| `ip_mismatch` | The public IP differs from the local network IP | Informational |
| `incognito` | A private browsing window | Weak on its own |
| `search_bot` | A known search engine crawler | Its Risk Score is forced to 0 |
| `suspicious_paid_click` | A paid-ad click (Google Ads, Meta, TikTok, Microsoft Ads, LinkedIn, Pinterest, X) with a Risk Score of 60 or more | For ad traffic quality |
| `javascript_disabled` | The page ran without JavaScript features | Blocked by the SDK policy default |
| `stun_not_checked` | The STUN network check did not complete | Check the Content Security Policy |
| `check_incomplete` | A browser check timed out | Informational |

## Risk signals

`signals` lists the weighted reasons behind the Risk Score as `{ name, weight }` (History rows
also carry a `description`). Legacy known names (not an exhaustive current server catalog):

| Name | Meaning |
|---|---|
| `tor` | Tor exit node |
| `javascript_disabled` | JavaScript features were unavailable |
| `os_mismatch` | Reported and observed operating systems differ |
| `antidetect_browser` | Anti-detect browser detected (at most one per identification) |
| `proxy_routed_antidetect` | A network check was routed through a proxy in an anti-detect pattern |
| `port_scan_routed_via_proxy` | The same pattern carried forward from a recent verdict on the same device and IP |
| `browser_automation` | Automated browsing, or many fresh cookie IDs from one device in a short time |
| `stun_not_checked` | The STUN network check did not complete |
| `stun_late_correction` | A late STUN result corrects `stun_not_checked` (negative weight) |
| `os_not_detected` | The operating system could not be determined |
| `browser_vpn_proxy` | VPN or proxy browser extension |
| `vpn` | VPN |
| `privacy_relay` | Privacy relay service |
| `proxy` | Proxy |
| `datacenter_ip` | Hosting or datacenter IP |
| `abuser` | IP with a history of abuse |
| `timezone_mismatch` | Browser and IP time zones differ |
| `rate_limited` | The rate-limit marker: the only signal of a `999` identification |

Rules:

- The set is open: new names appear without an SDK release. Keep unknown names, never fail on
  them, and never model them as a closed enum.
- Weights can be negative and a name can appear more than once (for example `stun_not_checked`
  and its `stun_late_correction`). Never add weights up to rebuild or check the score.
- Descriptions on History rows are free text: never branch on them.

## Connection types

`connection_type` is one of `direct`, `mobile`, `vpn`, `proxy`, `tor`, `privacy_relay`,
`browser_vpn_proxy` or `unknown`; keep unknown values. It describes the network for display. For
decisions use the flags: `connection_type` can say `vpn` while `detection_flags.vpn` is `false`,
when IP intelligence suggests a VPN that the scored check did not confirm.

## Countries and IPs

`public_ip.country` and `local_ip.country` are English country names (`"Germany"`,
`"United States"`) or `""`. IPs are IPv4 strings, or `""` when unknown (for example for visitors on
IPv6). Compare countries for account checks (shieldlabs-account-abuse skill) rather than
branching on `ip_mismatch`.
