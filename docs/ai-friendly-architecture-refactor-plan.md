# AI-Friendly Architecture Refactor Plan

**Date:** 2026-05-13  
**Status:** Proposed  
**Intent:** reshape the trading bot into an AI-friendly modular monolith with vertical slices and light DDD boundaries.

---

## 1. Recommendation

Do **not** convert the whole repository into textbook DDD in one pass.

Use this target instead:

- **Modular monolith**: single deployable app, clear internal module contracts
- **Vertical slices by feature**: entry / exit / auto_trade / portfolio / execution / market_data
- **DDD-lite boundaries**: domain rules live close to the slice, but avoid excessive repositories/factories/indirection
- **Hexagonal edges only where valuable**: Upbit, persistence, external APIs, runtime adapters
- **Explicit repo rules**: AGENTS.md + ADR + dependency rules

This target is more AI-friendly because changes stay inside one slice, file recall is easier, and agents do not need to load the whole codebase to make a safe edit.

---

## 2. Current pain points

### 2.1 Sell logic is split across multiple places

Current sell/exit decision paths:

1. `src/investment_bot/strategies/trend_following.py`
   - stop loss
   - take profit
   - trend reversal
   - bearish sell branch

2. `src/investment_bot/services/paper_broker.py`
   - partial take profit
   - trailing stop
   - atr stop
   - timeout exit

3. `src/investment_bot/services/auto_trade_service.py`
   - `_exit_override()`
   - sell candidate filtering / prioritization

4. `src/investment_bot/services/trading_cycle.py`
   - force-exit rewriting

### 2.2 Service layer is overloaded

`services/` is acting as:

- orchestration
- domain policy
- infrastructure gateway
- state manager
- selector/debug layer

This makes the code harder for both humans and AI to navigate.

### 2.3 Feature logic is scattered by layer

One trading behavior change often touches:

- strategy
- trading_cycle
- auto_trade_service
- paper_broker
- container wiring
- tests in multiple directories

That is exactly the pattern that causes high context cost for coding agents.

---

## 3. Target architecture

```text
src/investment_bot/
  features/
    auto_trade/
      application/
      domain/
      infrastructure/
      api/
    entry/
      application/
      domain/
      infrastructure/
    exit/
      application/
      domain/
      infrastructure/
    portfolio/
      application/
      domain/
      infrastructure/
    execution/
      application/
      domain/
      infrastructure/
    market_data/
      application/
      domain/
      infrastructure/

  shared/
    kernel/
    types/
    money.py
    time.py

  interfaces/
    api/
```

### Design intent by slice

- **entry**: decide whether a symbol is worth entering
- **exit**: decide whether an open position should be reduced or closed
- **portfolio**: exposure, position state, managed/dust classification
- **execution**: preview/submit order through exchange adapter
- **auto_trade**: orchestration only; chooses between exit and entry actions
- **market_data**: candles and market state access

---

## 4. Sell-side design target

## 4.1 Principle

**Exit logic should have a single owner.**

Recommended owner:

- `features/exit/domain/exit_policy.py`
- called through `features/exit/application/evaluate_exit.py`

## 4.2 What moves out

### Move out of strategy
From `trend_following.py`, remove direct ownership of:
- stop loss
- take profit
- trend reversal exit decision as final execution decision

The strategy may still emit **entry signal quality metadata** and optional **exit hints**, but it should not be the final sell authority.

### Move out of auto_trade_service
From `auto_trade_service.py`, remove:
- `_exit_override()` as a policy owner
- sell rule ownership
- mixed buy/sell rule computation

`auto_trade_service` should only:
- request exit candidates
- request entry candidates
- compare priorities
- execute chosen action

### Keep but repurpose in paper_broker
`paper_broker.evaluate_exit_rules()` should stop being the primary policy brain.
It can become either:

- position state helper, or
- simulation/runtime support for exit execution bookkeeping

Not the canonical place for business exit policy.

## 4.3 Target sell flow

```text
open position
  -> exit application service evaluates position + market + portfolio
  -> exit policy returns ExitDecision
  -> auto_trade orchestrator prioritizes exit vs entry
  -> execution service submits order
  -> portfolio/bookkeeping updated
```

## 4.4 Exit domain responsibilities

Exit policy should own:
- stop loss
- trailing stop
- partial take profit
- timeout exit
- trend reversal exit
- dust/managed/executable classification inputs from portfolio
- exit priority (`hard_stop > protective_exit > profit_take > soft_exit`)

---

## 5. DDD-lite rules for this repo

These are the rules I recommend instead of full textbook DDD.

### 5.1 Allowed
- feature-level domain modules
- explicit decision objects (`EntryDecision`, `ExitDecision`, `ExposureDecision`)
- application services for orchestration
- adapter interfaces only at external boundaries
- thin API/controller layer

### 5.2 Avoid
- generic `services/` dumping ground
- deep inheritance hierarchies
- one repository abstraction per model just because DDD says so
- factories/builders everywhere
- abstraction layers that only forward calls

### 5.3 Rule of thumb
If a new abstraction does not reduce either:
- context needed to make a change, or
- blast radius of a change,

then it is probably not AI-friendly.

---

## 6. Estimated change size

## Phase 1: Sell refactor only

Expected scope:
- source files touched: **8-15**
- test files touched: **8-18**
- net-new files: **4-8**
- risk: **medium**

## Phase 2: Auto-trade slice cleanup

Expected scope:
- source files touched: **12-25**
- test files touched: **10-20**
- net-new files: **6-12**
- risk: **medium-high**

## Phase 3: Wider repo reshape into feature-first structure

Expected scope:
- source files touched: **30-60+**
- test files touched: **20-40+**
- risk: **high if done in one pass**

So this should be done as a staged strangler refactor, not a big-bang rewrite.

---

## 7. mkflow-style breakdown

Below is the recommended task queue.

### TASK-001 — Architecture snapshot
**Goal:** map current module ownership and dependency hotspots  
**Done when:** document exists with current flow for entry/exit/portfolio/execution  
**Evidence:** dependency map + current owner table

### TASK-002 — Target slice contract
**Goal:** define public contracts for `entry`, `exit`, `portfolio`, `execution`, `auto_trade`  
**Done when:** each slice has input/output contract draft  
**Evidence:** architecture doc section + example decision objects

### TASK-003 — Exit policy spec
**Goal:** define canonical sell/exit rules and precedence  
**Done when:** stop/trailing/tp/timeout/reversal precedence is written and approved  
**Evidence:** exit decision table + truth cases

### TASK-004 — Exit decision model
**Goal:** introduce `ExitDecision` and related domain objects  
**Done when:** code compiles and tests cover decision shapes  
**Evidence:** new domain module + tests

### TASK-005 — Exit evaluator application service
**Goal:** create single entry point for sell decision calculation  
**Done when:** orchestrator can call one exit evaluation API  
**Evidence:** tests proving old scattered logic is reproduced

### TASK-006 — Move strategy-owned exits out of `trend_following`
**Goal:** keep strategy focused on entry semantics  
**Done when:** strategy no longer owns final stop/tp/reversal sell execution decisions  
**Evidence:** updated tests + reduced logic in strategy file

### TASK-007 — Remove auto-trade `_exit_override()` ownership
**Goal:** sell override logic delegated to exit slice  
**Done when:** `_exit_override()` removed or reduced to compatibility wrapper  
**Evidence:** auto_trade tests pass

### TASK-008 — Rework `paper_broker.evaluate_exit_rules()` role
**Goal:** convert from policy owner to state/bookkeeping helper  
**Done when:** exit domain is canonical owner  
**Evidence:** broker tests updated, no duplicated policy source of truth

### TASK-009 — Auto-trade orchestration split
**Goal:** separate entry selection, exit selection, and action arbitration  
**Done when:** orchestration file only coordinates slice outputs  
**Evidence:** slimmer orchestrator + focused tests

### TASK-010 — Portfolio slice extraction
**Goal:** centralize exposure, dust, managed position, executable size logic  
**Done when:** buy and sell both use same portfolio policy surface  
**Evidence:** exposure tests + shared portfolio decision objects

### TASK-011 — Feature-first directory migration (strangler step 1)
**Goal:** create `features/exit`, `features/entry`, `features/auto_trade` and move first-class modules  
**Done when:** imports work and legacy paths are minimized  
**Evidence:** tree diff + test pass

### TASK-012 — Feature-first directory migration (strangler step 2)
**Goal:** move `portfolio` and `execution` concerns under slices  
**Done when:** runtime wiring uses new module locations  
**Evidence:** smoke test + route test

### TASK-013 — API/container rewiring
**Goal:** interfaces call application services, not mixed service/domain internals  
**Done when:** container wiring reflects slices cleanly  
**Evidence:** container diff + API smoke tests

### TASK-014 — Repo-level AI guardrails
**Goal:** make architecture explicit for future agents  
**Done when:** AGENTS.md/ADR/dependency rules/scaffold guidance added  
**Evidence:** docs + CI rules or lint config

### TASK-015 — Final stabilization
**Goal:** regression pass and cleanup of compatibility shims  
**Done when:** targeted tests pass and old duplicated logic removed  
**Evidence:** test report + remaining debt list

---

## 8. Recommended implementation order

### Wave 1 — Safe and high leverage
- TASK-001
- TASK-002
- TASK-003
- TASK-004
- TASK-005

### Wave 2 — Sell-side consolidation
- TASK-006
- TASK-007
- TASK-008

### Wave 3 — Orchestration cleanup
- TASK-009
- TASK-010

### Wave 4 — Structural migration
- TASK-011
- TASK-012
- TASK-013

### Wave 5 — Long-term guardrails
- TASK-014
- TASK-015

---

## 9. What I recommend doing first

Start here:

1. approve this architecture direction
2. execute **sell-side only** first
3. stop after Wave 2 and verify live behavior
4. only then continue into wider repo migration

This keeps risk controlled while still moving toward the AI-friendly architecture target.

---

## 10. Definition of success

We should consider the refactor successful when:

- buy and sell ownership are explicit
- one file change no longer requires scanning half the repo
- `auto_trade_service` becomes orchestration-focused
- exit logic has a single source of truth
- portfolio/exposure rules are reused by both entry and exit
- future AI edits can be made slice-by-slice with smaller context windows
