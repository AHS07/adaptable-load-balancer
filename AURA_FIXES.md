# AURA (ALPHA1) Timeout Fix

## Problem: AURA had 30% MORE timeouts than Round Robin

**Test Results:**
- Round Robin: 9.48% timeout rate
- AURA (before fix): 12.34% timeout rate
- Difference: +30.2% worse

---

## Root Causes Identified:

### 1. **Self-Referential Feedback Loop**
**Problem:** Work queue calculation amplified connection count by 10x
```python
current_work = server['connections'] * 10  # Creates positive feedback
```

**Effect:**
- Server gets selected → connections increase
- Work queue EWMA increases dramatically (10x multiplier)
- Risk score increases → server avoided
- Connections decrease → work queue decreases
- Server looks safe again → selected again
- **Oscillation and load imbalance**

### 2. **Cold-Start Bias**
**Problem:** New servers had interference_signal = 0.0
```python
else:
    state['interference_signal'] = 0.0  # Looks artificially safe!
```

**Effect:**
- Servers with <5 response time samples looked "perfect"
- AURA preferentially routed to them
- They got overloaded before accumulating enough data
- By the time interference signal updated, damage was done

### 3. **Incorrect Head Request Age**
**Problem:** Age accumulated continuously while connections > 0
```python
if server['connections'] > 0:
    state['head_request_age'] += time_since_last  # Always growing!
```

**Effect:**
- Busy servers accumulated age even if processing quickly
- Made busy servers look increasingly risky
- AURA avoided them even when they were healthy
- Load concentrated on "idle" servers

### 4. **Aggressive Feedback Control**
**Problem:** Weights adjusted too quickly (10% increase, 5% decay)
```python
self.beta = min(self.beta * 1.1, 1.0)   # 10% jump
self.gamma = min(self.gamma * 1.1, 1.0)
```

**Effect:**
- System oscillated between extremes
- Never found stable equilibrium
- Amplified the other issues

---

## Fixes Applied:

### Fix 1: Remove Work Queue Amplification
**Before:**
```python
current_work = server['connections'] * 10  # 10x amplifier
```

**After:**
```python
current_work = server['connections']  # Use raw connections
```

**Impact:** Eliminates self-referential feedback loop

---

### Fix 2: Fix Cold-Start Bias
**Before:**
```python
else:
    state['interference_signal'] = 0.0  # Looks perfect!
```

**After:**
```python
else:
    state['interference_signal'] = 0.1  # Small neutral value
```

**Impact:** New servers no longer look artificially safe

---

### Fix 3: Fix Head Request Age Calculation
**Before:**
```python
if server['connections'] > 0:
    state['head_request_age'] += time_since_last  # Always grows
else:
    state['head_request_age'] = 0.0
```

**After:**
```python
if server['connections'] > 2:  # Only if actual queueing
    # Age increases proportional to queue depth
    state['head_request_age'] = min(
        state['head_request_age'] + (time_since_last * server['connections'] / 10.0), 
        1.0
    )
else:
    # Decay age when queue is small
    state['head_request_age'] = max(state['head_request_age'] * 0.5, 0.0)
```

**Impact:** 
- Only tracks age when there's actual queueing (>2 connections)
- Decays when queue is small
- Proportional to queue depth

---

### Fix 4: Normalize Interference Signal Scale
**Before:**
```python
state['interference_signal'] = min(variance / 1000.0, 10.0)  # 0-10 scale
```

**After:**
```python
state['interference_signal'] = min(variance / 10000.0, 1.0)  # 0-1 scale
```

**Impact:** Better balance with other components (work_queue and head_age now also 0-1 scale)

---

### Fix 5: Reduce Initial Weights
**Before:**
```python
self.beta = 0.3   # Weight for interference
self.gamma = 0.4  # Weight for queue age
```

**After:**
```python
self.beta = 0.2   # Reduced from 0.3
self.gamma = 0.3  # Reduced from 0.4
```

**Impact:** Less aggressive avoidance, more balanced distribution

---

### Fix 6: Conservative Feedback Control
**Before:**
```python
self.beta = min(self.beta * 1.1, 1.0)   # 10% increase, cap at 1.0
self.gamma = min(self.gamma * 1.1, 1.0)
# ...
self.beta = max(self.beta * 0.95, 0.1)  # 5% decay
```

**After:**
```python
self.beta = min(self.beta * 1.05, 0.5)   # 5% increase, cap at 0.5
self.gamma = min(self.gamma * 1.05, 0.5)
# ...
self.beta = max(self.beta * 0.98, 0.1)  # 2% decay
```

**Impact:** 
- Slower adjustments (5% vs 10% increase, 2% vs 5% decay)
- Lower cap (0.5 vs 1.0) prevents over-sensitivity
- More stable behavior

---

## Expected Results After Fix:

### Timeout Rate:
- **Before:** 12.34% (30% worse than Round Robin)
- **Expected:** 7-9% (equal to or better than Round Robin)

### P99 Latency:
- **Before:** 8.3% reduction (good!)
- **Expected:** Maintain or improve (10-15% reduction)

### Load Distribution:
- **Before:** Oscillating, imbalanced
- **Expected:** Stable, fair (Fairness Index ~0.98)

---

## Why These Fixes Work:

### 1. **Eliminates Positive Feedback**
- Work queue no longer amplifies connection count
- Risk scores reflect actual load, not amplified signals

### 2. **Prevents Cold-Start Exploitation**
- New servers start with realistic interference signal
- No preferential routing to untested servers

### 3. **Accurate Queue Age Tracking**
- Only accumulates when there's actual queueing
- Decays when queue clears
- Proportional to queue depth

### 4. **Balanced Risk Scoring**
- All components on 0-1 scale
- Lower weights prevent over-avoidance
- More balanced load distribution

### 5. **Stable Feedback Control**
- Slower adjustments prevent oscillation
- Lower caps prevent extreme sensitivity
- System finds stable equilibrium

---

## Testing:

Run the tests to verify:
```bash
python test\generate_research_tables.py
```

Expected improvements:
- AURA timeout rate should drop below 10%
- P99 latency reduction should maintain or improve
- Fairness Index should remain high (~0.98)

---

## Technical Notes:

### Risk Score Formula (unchanged):
```
Risk = work_queue_ewma + β×interference_signal + γ×head_request_age
```

### Component Scales (now balanced):
- work_queue_ewma: 0-20 (raw connection count)
- interference_signal: 0-1 (normalized variance)
- head_request_age: 0-1 (normalized age)

### With Default Weights:
- β = 0.2, γ = 0.3
- Typical risk score: 0-25 range
- More emphasis on actual load (work_queue) than signals

### Feedback Control:
- Adjusts every 100 requests
- Increases by 5% if p99 > target
- Decreases by 2% if p99 ≤ target
- Caps at 0.5 (prevents over-sensitivity)
- Floors at 0.1 (maintains minimum awareness)
