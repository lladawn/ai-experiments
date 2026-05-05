# OPENEYE
## AI Activity Monitor for Power Users
### Project Specification & Build Guide
**v1.0 — May 2026**
**GitHub:** https://github.com/lladawn/openeye

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [The Solution](#2-the-solution-openeye)
3. [Technical Architecture](#3-technical-architecture)
4. [Default Alert Rules](#4-default-alert-rules)
5. [UI Design & UX Principles](#5-ui-design--ux-principles)
6. [Build Phases](#6-build-phases)
7. [Monetization Strategy](#7-monetization-strategy)
8. [Launch Strategy](#8-launch-strategy)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Success Metrics](#10-success-metrics)

---

## 1. The Problem

The threat model for developers and power users has fundamentally changed. It used to be: don't click phishing links. Now it's: every new AI tool you install is a potential attack surface — and the people most at risk are exactly those who aggressively adopt AI tools.

### 1.1 How the New Attacks Work

Traditional security tools (antivirus, firewalls) are blind to this class of threat because the software is legitimate. The attack happens inside the application layer, by software you chose to install and trust.

**MCP Server Poisoning**
- You install an MCP server to give Claude access to your filesystem or browser
- The MCP server has undocumented tools that read `~/.ssh` keys, browser cookies, or crypto wallet files
- It exfiltrates these silently via outbound HTTP — looks like normal API traffic

**Agentic Code Execution**
- A coding agent (Codex, Cursor, Devin) is given a task
- It reads environment variables, `.env` files, or keychain entries as "context"
- It logs or transmits these as part of its reasoning trace

**Browser Extension Compromise**
- An AI browser extension has full DOM access — it sees everything
- MetaMask prompts, banking sessions, auth tokens, clipboard contents
- One compromised extension = full wallet drain with no on-chain warning

**Supply Chain Attacks via AI Tools**
- AI dev tools ship with npm/pip packages that have hidden malicious payloads
- The AI tool is legitimate; the dependency is the vector
- Standard lockfile hygiene doesn't catch post-install runtime behavior

> **The Core Insight:** The people most at risk are exactly the people most excited about AI — developers, founders, web3 power users. They install everything. They run agents locally. They have crypto wallets and SSH keys on the same machine. Nobody has built a visibility layer for this new threat class.

### 1.2 Why Existing Tools Don't Help

| Tool | Why It Fails |
|---|---|
| Antivirus / EDR | Looks for known malware signatures. AI tools are legitimate software doing illegitimate things. |
| Little Snitch / Firewall | Shows network connections but no context — "python3 connected to api.openai.com" tells you nothing. |
| Activity Monitor / htop | Shows processes but not what files they're reading, what they copied, what keys they touched. |
| Permission prompts (macOS) | Only covers camera/mic/location. File system access, clipboard, and network are invisible. |
| Audit logs (macOS BSM) | Expert-only, no UI, no real-time alerts, designed for forensics not prevention. |

---

## 2. The Solution: OpenEye

Openeye is a local agent activity monitor — a lightweight macOS (and later Linux) desktop app that gives you real-time visibility into what every AI tool on your machine is doing. Think of it as Little Snitch, but built for the AI-agent era.

> **One-line pitch:** Openeye watches every AI tool running on your machine and tells you when something looks wrong — before your wallet gets drained.

### 2.1 Core Capabilities

**File Access Monitor**
- Real-time display of every file read/write by AI processes
- Instant alerts when any process touches: `~/.ssh/`, wallet files (`*.json`, keystore dirs), `.env` files, browser profile directories, macOS Keychain
- Diff view: shows exactly what was read, not just which file

**Network Activity Tracker**
- All outbound requests from AI processes with full URL, headers, and payload preview
- Automatic flagging of unexpected destinations: data being sent to IPs not in the tool's documented API list
- Payload inspection: base64 decode, JSON pretty-print, detect if sensitive strings appear in outbound data

**Clipboard Watch**
- Detects when any process reads from clipboard without user action
- Especially dangerous: clipboard often contains wallet addresses, API keys, passwords
- Shows which process accessed clipboard, when, and what was in it

**Process Lineage Map**
- Visual tree of all running AI-related processes and their children
- Shows which process spawned which — catches agents that spawn hidden subprocesses
- Highlights anomalies: process running as unexpected user, unusual parent-child relationships

**MCP Server Auditor**
- On connect, scans every registered MCP server's tool manifest
- Flags undocumented tools, tools with filesystem or network access beyond stated scope
- Live diff: shows if a tool manifest changed between sessions (supply chain attack detection)

**Alert Engine**
- Rule-based alerts with severity levels: Info, Warning, Critical
- Sensible defaults out of the box, fully customizable
- Notification channels: macOS native notification, menu bar badge, optional webhook (Slack/Discord/Telegram)
- "Explain this alert" button: uses local LLM to explain what the alert means in plain English

---

## 3. Technical Architecture

Openeye is designed to be entirely local — no cloud dependency, no data leaves your machine. This is non-negotiable for a security tool.

### 3.1 Component Overview

| Component | Responsibility |
|---|---|
| **Openeye Agent (Rust)** | Core monitoring daemon. Uses OS APIs to hook file I/O, network calls, process events. Runs as a privileged background process. Exposes a local Unix socket for the UI to consume. |
| **Event Processor (Rust)** | Receives raw OS events from the agent. Applies classification rules, enriches with process metadata, evaluates alert conditions. Emits structured events. |
| **Local DB (SQLite)** | Stores event history, alert rules, process registry, MCP manifests. Enables timeline queries and session replay. |
| **UI App (Tauri + React)** | Desktop app shell. Consumes events via local WebSocket. Renders dashboards, alert inbox, process map. Tauri chosen for small binary size and native OS integration. |
| **MCP Auditor (Node.js)** | Connects to each registered MCP server on startup, fetches tool manifests, diffs against stored baseline, flags changes. |
| **Alert Engine (Rust)** | Evaluates incoming events against rule set. Supports CEL (Common Expression Language) for custom rules. Fires notifications via OS and webhooks. |
| **Local LLM Bridge** | Optional. Connects to Ollama (local) or user-provided API key for "explain this alert" feature. Never sends event data to cloud by default. |

### 3.2 OS-Level Monitoring Strategy

**macOS**
- File I/O: Use Apple's Endpoint Security Framework (ESF) — the same API used by enterprise EDR tools. Requires System Extension entitlement.
- Network: Use Network Extension framework for traffic inspection. Alternatively, use the existing macOS packet filter (PF) with process tagging.
- Process events: ESF also provides process fork/exec events with full argument list.
- Clipboard: Use `NSPasteboard` change count polling — there is no push API on macOS for clipboard access by other apps.

**Linux (Phase 2)**
- File I/O: `inotify` for watches, eBPF (via `libbpf`) for syscall-level tracing without kernel module
- Network: eBPF socket filter attached to cgroup, or netfilter hooks
- Process events: netlink connector for process events (`PROC_EVENT_EXEC`, `PROC_EVENT_FORK`)

> **Implementation note:** macOS ESF requires an Apple Developer account with the `com.apple.developer.endpoint-security.client` entitlement. This is approved for security tools. Apply early — approval takes 1–3 business days.

### 3.3 Data Flow

| Stage | What Happens | Latency |
|---|---|---|
| 1. OS Event | ESF/eBPF fires on syscall (`open`, `connect`, `exec`, etc.) | < 1ms |
| 2. Agent Capture | Rust agent receives event, extracts PID, path, metadata | < 2ms |
| 3. Process Enrichment | Lookup process name, parent, cmdline, code signature | < 5ms |
| 4. Classification | Rule engine tags event: `SENSITIVE_FILE`, `WALLET_ACCESS`, etc. | < 1ms |
| 5. Alert Evaluation | Check against user-defined and default alert rules | < 1ms |
| 6. UI Dispatch | Emit to WebSocket. SQLite write. Notification if alert. | < 5ms |
| **Total** | End-to-end from syscall to UI update | **< 15ms** |

### 3.4 Tech Stack Summary

| Layer | Choice |
|---|---|
| Core Daemon | Rust (tokio async runtime) |
| Desktop UI Shell | Tauri v2 (Rust backend + WebView) |
| UI Framework | React + TypeScript |
| Local Database | SQLite via sqlx |
| MCP Auditor | Node.js (uses `@anthropic-ai/sdk` for MCP client) |
| macOS Monitoring API | Apple Endpoint Security Framework (ESF) |
| Linux Monitoring API | eBPF via `libbpf-rs` |
| Alert Rules Language | CEL (Common Expression Language) |
| IPC (daemon ↔ UI) | Unix domain socket + WebSocket bridge |
| Package / Distribution | Homebrew tap (macOS), AppImage (Linux) |

---

## 4. Default Alert Rules

Openeye ships with a curated set of default rules targeting the most common AI-tool attack patterns. All rules are expressed in CEL and can be modified or extended by the user.

### 4.1 Critical Alerts (Immediate Notification)

| Rule Name | Trigger Condition | Why It Matters |
|---|---|---|
| `WALLET_FILE_READ` | Any process reads `*.json` in `~/Library/Ethereum`, `~/.bitcoin`, keystore dirs | Direct wallet file access is almost never legitimate from an AI tool |
| `SSH_KEY_EXFIL` | Process reads `~/.ssh/id_*` AND makes outbound network call within 5s | Classic pattern: read key, immediately ship it |
| `ENV_PLUS_NET` | Process reads `.env` file AND sends HTTP POST within 10s | API key harvest pattern |
| `BLIND_CLIPBOARD` | Process reads `NSPasteboard` without a user-initiated paste event | Silent clipboard sniffing |
| `MCP_MANIFEST_CHANGE` | MCP tool manifest differs from last-seen baseline | Supply chain tampering |
| `KEYCHAIN_TOUCH` | Process calls `SecKeychainFindGenericPassword` or equivalent | Direct keychain access outside of expected apps |

### 4.2 Warning Alerts (Badge + Log)

| Rule Name | Trigger Condition | Why It Matters |
|---|---|---|
| `BROWSER_PROFILE_READ` | Process reads `~/Library/Application Support/Google/Chrome` or Firefox profile dir | Session cookie theft vector |
| `UNEXPECTED_OUTBOUND` | Process sends data to IP not in its known-good domain list | Possible C2 communication |
| `CHILD_PROCESS_SPAWN` | AI process spawns shell (`bash`, `sh`, `zsh`) with unusual arguments | Agent escape or command injection |
| `LARGE_FILE_EXFIL` | Process sends HTTP body > 100KB to external endpoint | Bulk data exfiltration |
| `ENV_FILE_READ` | Any AI process reads a `.env` file | Less critical alone, but worth logging |

### 4.3 Custom Rule Example

Users can write custom rules in the Openeye UI using CEL. Example: alert if any MCP server touches files outside a designated workspace folder:

```cel
// Alert if MCP process reads outside ~/workspace
process.name.startsWith("mcp-") &&
event.type == "FILE_READ" &&
!event.path.startsWith(user.home + "/workspace")
```

---

## 5. UI Design & UX Principles

Openeye's UI should feel like a calm, always-available dashboard — not an anxiety machine. Most of the time it sits quietly in the menu bar. It only interrupts you when something genuinely needs attention.

### 5.1 Menu Bar App

- Default: small shield icon in menu bar. Green = all clear. Yellow = warnings present. Red = critical alert.
- Click: opens popover with last 5 events and active alert count
- `Cmd+Shift+S`: open full dashboard

### 5.2 Main Dashboard Views

| View | Description |
|---|---|
| **Live Feed** | Real-time stream of all monitored events. Filterable by process, event type, severity. Each row expandable for full details. |
| **Alert Inbox** | All fired alerts, grouped by session. Each alert has: timestamp, process, description, recommended action, "explain this" button. |
| **Process Map** | Visual tree of running AI-related processes. Color-coded by trust level. Click any node to see its full activity history. |
| **MCP Auditor** | List of all connected MCP servers with their tool manifests. Diff view for any changes since last session. Trust score per server. |
| **Rules Editor** | View, edit, enable/disable all alert rules. Write new rules in CEL with live syntax checking. Test rules against historical events. |
| **Timeline** | Chronological replay of any past session. Useful for post-incident investigation. |

### 5.3 The "Explain This" Feature

Every alert has an "Explain this alert" button. When clicked, it sends the alert context (process name, event type, file paths — **never file contents**) to either a local Ollama model or the user's own API key, and returns a plain-English explanation:

> **Example output:** "The process `cursor-agent` read your SSH private key at `~/.ssh/id_ed25519`, then made an outbound HTTPS request to `34.102.x.x` (not a known Cursor endpoint) 3 seconds later. This matches a pattern commonly used to exfiltrate credentials. Recommended action: revoke this key immediately and check your Git provider for unauthorized access."

---

## 6. Build Phases

### Phase 0 — Proof of Concept (Week 1–2)

**Goal:** prove the monitoring works and something visually useful exists.

- macOS only, no installer — just a Rust binary you run in terminal
- Use ESF to capture file events from a list of known AI process names (`cursor`, `claude`, `python`, `node`)
- Log to stdout with color coding: green = normal, yellow = `.env` file, red = SSH/wallet
- Hardcode 3 rules: SSH key read, `.env` read, wallet file read
- Share on Twitter/X as a demo video — gauge interest before building the full UI

### Phase 1 — MVP (Week 3–6)

**Goal:** something real people can install and use daily.

- Tauri desktop app with menu bar integration
- Live feed view with filtering
- Alert inbox with notifications
- Full default rule set (see Section 4)
- MCP server manifest auditor
- Homebrew tap for easy install: `brew install openeye-ai`
- Basic "explain this alert" via user's own API key

### Phase 2 — Polish (Week 7–10)

**Goal:** make it something you'd recommend to every developer you know.

- Process map visualization (D3.js tree in WebView)
- Timeline / session replay
- Rules editor with CEL support
- Linux support (eBPF backend)
- Webhook alerts (Slack, Discord, Telegram)
- Local Ollama integration for fully offline "explain" feature

### Phase 3 — Distribution (Week 11+)

**Goal:** grow the user base and explore monetization.

- Public launch: Product Hunt, Hacker News Show HN, developer Twitter
- Open source the core monitoring engine, keep UI as paid or freemium
- Team plan: monitor all developer machines in an org from a central dashboard
- API/SDK: let other tools integrate Openeye as a trust layer

---

## 7. Monetization Strategy

| Tier | What's Included |
|---|---|
| **Free (OSS core)** | Basic file + network monitoring. Default alert rules. CLI only. Perfect for technical users who want to self-host. |
| **Personal — $9/mo** | Full desktop UI. All default + custom rules. MCP auditor. "Explain this alert" with own API key. 30-day event history. |
| **Pro — $19/mo** | Everything in Personal. Ollama integration (fully offline). Webhook alerts. Unlimited history. Priority support. |
| **Team — $15/seat/mo** | Centralized dashboard for all developer machines. Org-wide rule policies. Security audit exports. SSO. |

> **Distribution insight:** Open sourcing the Rust monitoring core builds trust (this is a security tool — people need to audit it) and creates community adoption. The UI and team features are where the monetization lives.

---

## 8. Launch Strategy

### 8.1 Target Audiences (in order)

1. Web3 developers and founders — highest immediate need, most vocal on social media
2. AI power users who run agents and MCP servers locally
3. Security-conscious developers (Hacker News demographic)
4. Enterprise dev teams as adoption grows

### 8.2 Launch Sequence

| Week | Action | Goal |
|---|---|---|
| 1–2 | Build PoC. Record terminal demo video showing SSH key detection in real-time. | Validate the concept publicly |
| 3–4 | Post PoC on Twitter/X with demo. "I built a thing that catches AI tools stealing your SSH keys." | Build waitlist and gauge demand |
| 5–6 | Ship MVP via Homebrew. Post on Hacker News Show HN. | First real users + feedback |
| 7–8 | Write deep-dive blog post: "The new attack surface nobody is talking about." | SEO + thought leadership |
| 9–10 | Product Hunt launch with full desktop app. | Broad awareness |
| 11+ | Outreach to web3 security communities, dev tool newsletters. | Targeted growth |

### 8.3 The Viral Hook

The strongest distribution mechanism: people sharing their own Openeye alerts. "Look what my MCP server was trying to do" is inherently shareable — especially in the web3 and developer communities where trust is currency and everyone is paranoid (rightfully).

- Build a one-click "share this alert" feature that redacts sensitive info and generates a shareable image
- Create a public "threat feed" — anonymized, aggregated alerts that show what attack patterns are being detected across all Openeye users

---
## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Apple rejects ESF entitlement | High — can't ship macOS app | Apply early. In the interim, use DTrace/FSEvents as a fallback (less powerful but available without entitlement). |
| False positive rate too high | Users disable alerts, tool becomes useless | Generous allowlisting for known-good behaviors. User feedback loop to improve rules. "Mark as trusted" for any process. |
| Performance overhead | Developers notice slowdown, uninstall | ESF events are async. Benchmark: target < 1% CPU overhead at idle. Implement event sampling if needed. |
| Privacy concerns about what Openeye itself collects | Trust crisis — a security tool that spies on you | 100% local. No telemetry by default. Open source the core. Reproducible builds. Public security audit. |
| Competitors (enterprise EDR vendors) | Feature parity reduces differentiation | Focus on the AI-tool-specific use case and developer UX. Enterprise EDR is too heavy and too expensive for individual devs. |

---

## 10. Success Metrics

| Milestone | Target |
|---|---|
| Week 2 (PoC) | Twitter demo post gets 500+ engagements. Waitlist of 200+. |
| Week 6 (MVP launch) | 500 Homebrew installs. 50 GitHub stars. At least 3 real attack detections reported by users. |
| Month 3 | 2,000 active installs. 100 paid Personal subscribers. Featured in at least one major developer newsletter. |
| Month 6 | 5,000 active installs. First team/org customers. Community-contributed alert rules in a public registry. |
| Month 12 | Recognized as the go-to tool for AI tool security monitoring. Potential acqui-hire interest from security vendors or developer tool companies. |

---

*End of document.*
