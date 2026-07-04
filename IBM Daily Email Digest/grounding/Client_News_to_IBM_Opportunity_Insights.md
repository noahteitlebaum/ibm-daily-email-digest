# IBM Horizon Atlantic — Grounding Context for Client-News → Opportunity Insights

> **Purpose of this file.** This is a knowledge base to feed an LLM alongside aggregated client
> news (J.D. Irving, Irving Oil, Government of New Brunswick). The LLM's job is to read incoming
> news items and generate **IBM sales opportunity insights**: connect a news event to a relevant
> IBM offering, the right buyer, the sales stage it implies, and the recommended next move.
> Everything below is drawn from IBM internal account briefs and reference material. Treat it as
> the authoritative background; treat the news feed as the new, time-sensitive input.

> **Confidentiality.** Source briefs are marked *IBM Confidential*. Keep generated insights internal.

---

## 1. How to use this document

When a news item arrives, the LLM should:

1. **Identify the account** it concerns (JDI, Irving Oil, Govt of NB, or a named division/subsidiary).
2. **Match the event to a trigger type** (see §3.7 trigger events) — e.g. capex announcement,
   executive appointment, cyber incident, M&A, contract/renewal signal, AI/data initiative.
3. **Map to the most relevant IBM opportunity** for that account (the opportunity theses in §5 and §6).
4. **Frame it in Client Engagement Model terms** (§4): which sales stage does this move, and what
   is the next-step exit criterion.
5. **Name the buyer / champion** likely to own it (from the org intelligence in §5 and §6).
6. **Flag risks/guardrails** (§7) — e.g. do not position against an entrenched incumbent.

Recommended output shape per insight: *Event → Why it matters to IBM → Relevant offering →
Likely buyer → Sales-stage implication → Recommended next move → Confidence (high/medium/low)*.

**Grounding discipline:** Only assert facts supported below or in the news item itself. Where a
figure or relationship is inferred, say so. Do not invent contacts, dollar values, or contract terms.

---

## 2. Who IBM is here (seller context)

- **Team:** IBM Horizon Atlantic account team. Lead seller / quarterback: **Michael Brooker,
  Technology Sales Leader (TSL)**.
- **Key extended team members (engage by opportunity):**
  - Tony Lodge — Account Technical Leader (architecture credibility).
  - Phil Pelletier — Data Sales Leader (Db2, watsonx, data).
  - Jayne Campbell — Automation Sales Leader (Turbonomic, IWHI, Maximo, WebSphere).
  - Ed Flynn — Systems / Infrastructure (Power, Cloud, Storage).
  - Rene Doucet — TLS Sales Specialist (support/hardware lifecycle).
  - Pascale Leonard — Expert Labs (TEL) services (funded proofs/deployment).
  - Joy Malakar — Software Dealmaker (ELA / multi-year structuring).
  - Sandip Roy — First-Line Manager / sales leadership (ELA strategy escalation).
  - Clemmy Yip — Software Renewals.
- **Primary business partner:** **Pellera Technologies** (formed April 2025 from the
  Converge + Mainline merger under H.I.G. Capital). In IBM systems the partner of record on Irving
  agreements is mapped as **Converge → Pellera**. Pellera is the recommended VAR/SI/MSP for IBM
  Power, Cloud, Maximo sequencing, security, and renewals across the NB Horizon base.
  Partner specialist: Andre Bhugra (TPS, Ontario + Atlantic).

---

## 3. IBM offerings reference (what we sell, and to which signal)

### 3.1 IBM Platform Strategy (the four strategic pillars)
IBM positions its portfolio as four platforms; building/maintaining a platform enables the full
client journey from first sale to cross-sell:

1. **Data** — governance, integration, encryption, orchestration, discovery, ingestion/ETL.
2. **Automation** — FinOps, application performance management, workflow, rules engines, hybrid iPaaS.
   (>40% of all API calls globally are estimated to pass through IBM systems.)
3. **Transaction Processing** — IBM Z, zOS (world's #1 transaction processing platform).
4. **Hybrid Cloud** — Red Hat (RHEL, OpenShift), HashiCorp; unify public, private, on-prem, hyperscalers.

Cross-platform theme: **how to infuse AI**. Platform value levers: product integrations
(e.g. Instana↔Concert, Turbonomic↔Apptio), packaging/pricing simplicity (PAYGO or committed
spend), multi-cloud availability, and flexible routes to market (direct, e-commerce, partner ecosystem).

### 3.2 Product → buying-signal cheat sheet
Use this to match a news event to an offering.

- **webMethods Hybrid Integration (IWHI)** — heterogeneous systems, many integrations, M&A,
  new ERP/system go-lives, "connect everything" pain. (iPaaS / Automation + Data.)
- **Maximo Application Suite (MAS)** — asset-intensive operations, turnarounds, plant/refinery
  capex, predictive maintenance, unplanned-downtime cost. (Automation / Asset Management.)
- **watsonx / watsonx.data / watsonx Orchestrate** — AI on operational data, reliability,
  agentic back-office workflows, "infuse AI" announcements.
- **Security & Resilience portfolio** — Guardium (data activity monitoring), Storage Defender
  (immutable cyber recovery), Verify (identity), Concert (vuln prioritization), API Advanced
  Security, plus **SaRA** (Security & Resilience Assessment, NIST-CSF based, low-friction entry).
- **Turbonomic + Apptio + Instana** — FinOps, observability, compute cost during capex-heavy periods.
- **Red Hat OpenShift** — container/hybrid-cloud standardization; deployment substrate for IWHI/MAS.
- **IBM Power (Power 11) + Storage** — resilient 24×7 compute for OT/control workloads, data-center
  moves, VMware-cost (post-Broadcom) displacement.
- **Db2 / SPSS / WebSphere** — installed-base modernization, version upgrades, multi-year renewals.

### 3.3 Critical portfolio note — IBM exited SIEM
**IBM no longer sells QRadar.** IBM divested QRadar SaaS to Palo Alto Networks (acquisition closed
31 Aug 2024; end-of-sale / end-of-life 14 Apr 2025). Where SIEM is needed, IBM Consulting is a
Palo Alto **Cortex XSIAM** migration partner. IBM security plays are now **data security, cyber
recovery, identity, and assessment** — not SIEM. (Note: some existing JDI references mention QRadar
in production historically; do not pitch net-new QRadar.)

### 3.4 Commercial constructs
- **Multi-year uplift:** 1.2x on 2-year, 1.3x on 3-year SaaS/FSL ACV contracts. Multi-year both
  lowers the client's effective annual uplift and secures IBM annuity.
- **ELA (Enterprise License Agreement):** wraps current + net-new commitments under one framework;
  reduces admin overhead and accelerates procurement velocity.
- **Passport Advantage:** prerequisite enrollment for IBM software purchases; renewals can route
  direct or via business partner (Pellera).

---

## 4. Client Engagement Model (CEM) — how to frame insights

The CEM is IBM's iterative three-part sales methodology. Use it to label what stage a news event implies.

**Sales stages (IBM side):**
1. Prepare (pre-Day 0) — build corporate profile, understand initiatives, recent news, infer pain.
2. Engage (Day 0) — activate account plan, identify opportunities/challenges.
3. Qualify — satisfy **BANT** (Budget, Authority, Need, Timeline); IBM extends to BANTSA+Competition
   (adds Scope, Availability, Competition + Decision Criteria/Process).
4. Design — co-create decision criteria, timeline, business case, KPIs.
5. Propose — validate funding, roadblocks solved, ally commits.
6. Negotiate — commercials, scope, timing, BATNA.
7. Closing/Commit → 8. Closed → 9. Deploy → 10. Adopt → 11. Expand Value ("rehash").

**Client journey stages (customer side):** Plan → Awareness → Explore → Acquire → Implement & Expand.

**Qualification framework — MEDDPICC:** Metrics, Economic buyer, Decision criteria, Decision
process, Paper process, Implicate pain, Champion, Competition. When framing an insight, note which
MEDDPICC field a news event helps fill (e.g. an exec appointment fills *Economic Buyer* or *Champion*).

**How news maps to stages:** A *recent-news scan* is core to the **Prepare** stage. A capex
announcement or exec change is often the **compelling event** that opens **Engage**. A renewal date
is a hard commercial gate that can pull an account into **Negotiate/Closing**.

---

## 5. CLIENT PROFILE — J.D. Irving, Limited (JDI)

### 5.1 Snapshot
- Privately held, family-owned NB conglomerate; founded 1882, Bouctouche NB. HQ: 300 Union Street,
  Saint John, NB. ~20,000 employees globally. Nine divisions.
- **Active capital programs exceeding $1.3B** — the central "compelling reason to act."
- Verticals: Forestry & forest products (pulp, paper, lumber); Consumer products (Irving Tissue —
  Royale, Majesta, Scotties; Irving Personal Care); Food (Cavendish Farms, 4th-largest N.A. frozen
  potato processor); Transport & logistics (Midland, Sunbury, RST, railways); Retail (Kent Building
  Supplies, 48 locations); Shipbuilding (Irving Shipbuilding — **out of scope** for this engagement);
  Agriculture (Cavendish Agri); Hydro energy.
- Leadership: **Jim Irving (James D. Irving)** is sole operational head following the death of
  Robert K. Irving (May 2026) and James K. Irving (June 2024). Investment decisions are co-CEO/family
  authority.

### 5.2 Key contacts (who shapes IBM decisions)
- **Eddie Hacala — CTO** (27+ yrs at JDI). Primary relationship; owns enterprise IT strategy.
  Likely IBM champion (Turbonomic won under his watch). Now reports to Brad Zacharias.
- **Brad Zacharias — General Manager** (former VP IT). Cross-division architecture authority; Kent
  D365 / Microsoft case-study spokesperson — possible blocker on net-new IBM Cloud outside anchors.
- **Georges-Emmanuel Tetegan — VP Corporate Business Transformation.** Owns the **Aera Technology**
  AI/decision-intelligence relationship — competitive AI anchor; do NOT position watsonx as displacement.
- **Nataliya Yevtushenko — Manager, Contracts.** Drove the PA/Cloud Services v6→v12 amendment;
  contract-simplification advocate; ELA paper-process gatekeeper.
- **Carl MacKenzie — Sr Director, Enterprise Architecture.** Technical co-design partner.
- Division VPs: **Mark Mosher** (Pulp & Paper), **Daniel Richard** (Cavendish Farms), Mike Simms
  (Retail/Kent), Andrew Fisher (Transport & Logistics).
- Unconfirmed/to-validate: CFO, CISO/VP Cybersecurity, CDO, VP Procurement.

### 5.3 Installed tech & IBM footprint
- **Confirmed IBM:** Turbonomic (recently won, deploying well); **IWHI in flight** (targeted close);
  PA + Cloud Services agreements amended to v12; some IBM Data and Infrastructure (Power/Storage) present.
- **Non-IBM stack:** Kent Building Supplies on **Microsoft Dynamics 365** (Finance/SCM/Commerce, Azure);
  **Aera Technology** for supply-chain decision intelligence; Apache Hadoop; ServiceNow; Cisco ISE;
  Microsoft Exchange; Autodesk Revit; HashiCorp/Terraform confirmed.

### 5.4 Active capex (the opportunity anchors)
- **Irving Tissue Macon, GA — Phase 3: ~US$600M** (3rd ThruAir Dry machine + automated warehouse;
  completion ~2027).
- **Cavendish Farms Jamestown, ND: ~US$150M** (fryer replacement, packaging, wastewater; broke
  ground spring 2025).
- **Irving Pulp & Paper, Saint John mill rejuvenation: ~CAD$450M+** (Project NextGen; new digester,
  dryer; +CAD$660M CIB loan; up to 145 MW renewable energy; recovery boiler/turbine 2025–2028).
- **IPP woodyard: CAD$110M** (world's largest automated stacker reclaimer; completion ~2025).
- **Brighton Mountain Wind: CAD$550M** Phase 1 (200 MW, 34 turbines).
- **Moncton→Halifax data centre move** — creates a Power 8 → Power 11 vs Dell x86 decision (most
  time-sensitive infrastructure conversation).

### 5.5 IBM opportunity theses (ranked)
1. **IWHI close** (Tier 2 XaaS ACV) — integration substrate across heterogeneous systems during capex.
   In flight; Sandip–Nataliya alignment. References: Komatsu, Hellmann.
2. **Maximo MAS** for Pulp & Paper, Tissue, Cavendish Farms (Tier 1 Period Revenue) — predictive
   maintenance / asset lifecycle across the three asset-intensive capex programs. Ref: IDC Maximo
   study (avg US$13.9M annual benefit, 17% lifespan extension), NYPA ($33.7M).
3. **Strategic ELA construct, target Nov 2026** (Tier 3/4) — extends v12 contract simplification to
   the full portfolio.
4. **Security & Resilience (SaRA-led)** — industrial cyber for OT/IT convergence (Guardium, Storage
   Defender, Verify, Concert, API Advanced Security). NOT SIEM.
5. **watsonx Orchestrate** — agentic workflows adjacent to (not displacing) Aera.
6. **IBM Power 11** — resilient compute for mill/tissue 24×7 workloads; anchors the data-centre move.
7. **Turbonomic expansion + Apptio** — cross-division FinOps during capex.
8. **Red Hat OpenShift** — deployment substrate for IWHI + MAS.

### 5.6 Risks / guardrails (JDI)
- **Aera is the named AI supply-chain platform** — position watsonx as complement, never displacement.
- **Kent is committed to Microsoft D365** — do not pitch a conflicting Data/Automation/Workflow story for Kent.
- Private company, low disclosure — many roles unconfirmed; discovery-dependent.

---

## 6. CLIENT PROFILE — Irving Oil Limited

### 6.1 Snapshot
- Privately held, family-owned international energy company; founded 1924; HQ Saint John, NB.
- Operates **Canada's largest refinery** (Saint John, 320,000+ bpd) and **Ireland's only refinery**
  (Whitegate, Co. Cork). 1,000+ fuelling locations across Eastern Canada, New England, Ireland.
- ~3,400–4,000 employees (estimate). Strategic review (announced 2023) concluded Jan 2025 — decided
  to **remain privately held**; **Jeff Matthews** appointed President & CEO.
- Divisions: Refining & Supply (Saint John + Whitegate; Canaport terminal); Sales & Marketing
  (retail/convenience, commercial, marine, aviation, home heating; "Top" brand in Ireland); Midstream
  & terminals; Lubricants & packaging.

### 6.2 Key contacts
- **Kelley Greer White — SVP, Information Systems & Technology** (since 2016). **Primary technology
  decision-maker**; owns IT, OT, cybersecurity, and the Operational Management System. The central
  champion for renewal cost and OT cyber risk. (Prior: Husky Energy.) SAP in skill profile.
- **Jeff Matthews — President & CEO** (since Jan 2025; ~30 yrs at Irving, ex-CFO/CBDO).
- **Scott Hastings — EVP & CFO** (joined 2025, ex-Emera). Budget/ROI gatekeeper.
- **Peter McNay — SVP Engineering, Procurement & Capital** (ex-Deloitte). Gates technology/capital spend.
- **John Laidlaw — EVP & Chief Legal Officer.** Owns paper process & corporate security review.
- **Kevin Scott — Chief Refining & Supply Officer**; **Dave MacLennan — GM Saint John Refinery**
  (turnaround owners / operational sponsors).
- Unconfirmed: CISO, VP IT Infrastructure, VP Data & Analytics (placeholders to validate).

### 6.3 Installed tech & IBM footprint
- **Confirmed IBM (renews 30 June 2026, via Converge/Pellera):** Db2 Enterprise Server Edition
  (1,440 PVU), Db2 Advanced (non-prod), **Db2 Extended Support** (~30% / ~$13K of the Db2 line —
  an avoidable cost removable by version upgrade), SPSS Statistics, WebSphere App Server ND.
- **2025 IBM software spend:** ~$903K total (SaaS ~$775K, on-prem ~$127K). On-prem renewal modelled
  ~$140K at 10% uplift. (SaaS product mix not itemized — to validate.)
- **Inferred non-IBM:** SAP enterprise core; Microsoft Azure + M365; Deloitte advisory relationship.

### 6.4 Active capex (opportunity anchors)
- **FCCU Revamp: ~$100M** (announced June 2025; fluid catalytic cracking unit upgrade, Saint John).
- **Operation Ram: ~$190M** annual turnaround maintenance.
- **Operation Eastern Screech Owl: ~$40M** (30-day turnaround from Sept 2025).
- ESG: 30% GHG reduction by 2030; hydrogen (200+ t/day, Plug Power electrolyzer — 2022-era, validate);
  Burchill wind RECs (validate recency).

### 6.5 IBM opportunity theses (ranked)
1. **On-premise renewal → multi-year** (Db2, SPSS, WebSphere) — Tier 4 Annuity + Tier 1 Period
   Revenue. **Hard gate: closes 30 June 2026.** A 3-year term (6% then 5%) lowers client cost vs a
   single-year 10% uplift while applying the 1.3x multiplier. Reference: JDI multi-year S&S discipline.
2. **watsonx + AI for refinery reliability** (Tier 2 XaaS ACV) — anchored to the $100M FCCU Revamp and
   $190M Ram turnaround; pairs with Maximo.
3. **Cybersecurity Resilience across IT/OT** (Tier 2/3) — SVP owns OT + cyber; oil & gas ransomware
   up 935% YoY. Data security, recovery, identity, assessment (NOT SIEM).
4. **Maximo MAS** for turnaround & asset performance.
5. **WebSphere → Cloud Pak for Applications** (modernization; renews 30 June 2026).
6. **Db2 upgrade** to remove the Extended Support penalty (~$13K) and enable Db2 AI / watsonx.data.
7. **Instana + Turbonomic** (observability/FinOps across hybrid SAP/MS/IBM estate).
8. **IBM Storage + Power** for OT data growth.

### 6.6 Single most compelling reason to act (Irving Oil)
The **30 June 2026 on-premise renewal** forces a near-term commercial decision. Converting to
multi-year plus a Db2 upgrade removes the Extended Support penalty and reframes a transactional
renewal into a modernization + AI conversation tied to the refinery reliability agenda.

### 6.7 Risks / guardrails (Irving Oil)
- Renewal routes through partner Converge (Pellera) — IBM influence on terms is shared; client
  historically counters a 10% uplift down to ~2%. Engage Pellera early on the Db2 upgrade scope.
- SAP + Microsoft are the probable enterprise core; a Deloitte SI relationship is inferred.
- Post-strategic-review: discretionary tech budgets may be gated behind reliability capital.

---

## 7. Government of New Brunswick (third feed account — context note)

The news aggregator also tracks the **Government of New Brunswick**. There is **no dedicated account
brief** for it in the source material, so the LLM should treat it more cautiously:

- Classify it as a **public-sector account** (different procurement rules: public RFP/RFI processes,
  longer cycles, transparency requirements) — unlike the two privately held Irving entities.
- Relevant IBM angles by analogy: data platforms, AI for citizen services, cybersecurity resilience
  for critical infrastructure, automation/modernization. But **do not fabricate** specific GNB
  contacts, contracts, or initiatives — flag those as "to validate."
- When a GNB news item arrives, the most useful insight is usually: *what initiative/budget does this
  signal, which IBM domain could it map to, and who on the Horizon team should investigate.*
- Note JDI/Irving overlap: GNB policy (energy, forestry, economic development) can indirectly affect
  the Irving accounts — cross-reference where relevant.

---

## 8. Turning a news event into an opportunity insight (playbook)

### 8.1 Trigger events worth flagging immediately
- New capex / project announcement (esp. >$50M, or any refinery/mill/plant investment).
- Executive appointment in IT, security, data, AI, transformation, or finance (fills MEDDPICC
  Economic Buyer / Champion).
- Any public cybersecurity incident (at the account or a close industry peer).
- M&A, divestiture, restructuring, or facility expansion.
- AI / data / cloud initiative announcement (esp. anything that signals "infuse AI").
- Contract/renewal/procurement signals (RFP/RFI — rare for private Irvings; watch for them anyway).
- For Irving Oil specifically: anything touching the 30 June 2026 renewal, Db2, or the FCCU Revamp.
- Competitive signals: Microsoft/SAP/Aera/Deloitte expansion (incumbency to navigate).

### 8.2 Mapping logic (examples)
- *"JDI announces new plant/turnaround"* → Maximo MAS + watsonx reliability; buyer Mark Mosher /
  Eddie Hacala; Engage→Qualify; next move = sequence MAS discovery.
- *"Irving Oil announces refinery reliability/AI project"* → watsonx + Maximo; buyer Kelley Greer
  White + Kevin Scott; tie to FCCU Revamp.
- *"New CISO / cyber incident at either account"* → Security & Resilience (SaRA assessment entry,
  Guardium/Storage Defender/Verify) — NOT QRadar/SIEM; buyer SVP IS&T / CISO.
- *"Executive change in IT/finance"* → updates Economic Buyer/Champion; recommend relationship move.
- *"M&A or new ERP/system"* → IWHI integration story (JDI especially).

### 8.3 Output guardrails (apply to every generated insight)
- Cite the news item; separate **fact** from **inference**; mark confidence.
- Respect competitive guardrails: **complement Aera, don't displace; don't conflict with Kent D365;
  never pitch net-new QRadar/SIEM (IBM exited SIEM).**
- Name a realistic buyer/champion from §5/§6; if unknown, say "to validate."
- Tie to a CEM stage and a concrete next move (a meeting, a discovery question, a proof).
- Keep dollar figures grounded in this file or the news item — do not invent ACV.

---

*Sources: IBM Account Brief — J.D. Irving, Limited; IBM Account Brief — Irving Oil Limited;
IBM Client Engagement Model overview; IBM Platform Strategy brief. All IBM Confidential.*
