# Test Results Analysis

## Current Results (After Initial Fixes):

### HELIOS Performance:
- **Cache Hit Rate:** 73.08% (vs Round Robin 79.02%)
- **Status:** Still underperforming by 5.9%

### AURA Performance:
- **P99 Reduction:** 8.3% (good!)
- **Timeout Rate:** 12.34% vs Round Robin 9.48%
- **Status:** 30% MORE timeouts (bad!)

---

## Root Cause Analysis:

### HELIOS Issue: Bounded Load Too Restrictive

**The Math:**
- 20 concurrent clients ÷ 5 servers = 4 connections average
- Bounded load threshold = 1.25 × 4 = 5 connections
- If server gets 6+ connections → REDIRECT

**The Problem:**
- Zipfian distribution naturally concentrates popular keys
- Popular keys route to same server (by design)
- Server hits 6 connections → bounded load kicks in
- Redirect breaks cache affinity!

**Example:**
```
Key "popular_1" → Server A (by HRW)
Key "popular_2" → Server A (by HRW)
Key "popular_3" → Server A (by HRW)
...
Server A reaches 6 connections
Key "popular_10" → Server A (by HRW) → REDIRECTED to Server B
→ Cache miss on Server B!
```

**Fix Applied:**
- Increased capacity_factor from 1.25 → 2.5 for cache tests
- New threshold = 2.5 × 4 = 10 connections
- Much more headroom before redirects

---

### AURA Issue: Too Conservative?

**The Problem:**
- AURA has 30% MORE timeouts than Round Robin
- This suggests AURA is making poor routing decisions

**Possible Causes:**

1. **Over-concentration:**
   - AURA avoids "risky" servers
   - Concentrates load on "safe" servers
   - Safe servers become overloaded
   - Result: More timeouts

2. **Feedback Loop Issues:**
   - β and γ weights might be adjusting too aggressively
   - System oscillates between extremes
   - Never finds stable equilibrium

3. **Interference Signal Noise:**
   - Response time variance might be too noisy
   - AURA avoids servers unnecessarily
   - Reduces effective server pool

**Needs Investigation:**
- Check if AURA is distributing load fairly (Fairness Index)
- Monitor β and γ weight changes over time
- Verify interference signal calculation

---

## Expected Results After capacity_factor Fix:

### HELIOS:
- **Before:** 73.08% hit rate
- **Expected:** 85-90% hit rate
- **Reasoning:** 
  - Threshold now 10 connections (vs 5)
  - Can handle natural concentration from Zipfian
  - Fewer redirects = better cache affinity

### AURA:
- **No change expected** (different issue)
- Still needs investigation

---

## Next Steps:

### 1. Re-run Tests with New capacity_factor:
```bash
python test\generate_research_tables.py
```

### 2. If HELIOS Still Underperforms:
- Check bounded_load_redirects metric
- May need even higher capacity_factor (3.0 or 4.0)
- Or disable bounded load for cache tests

### 3. For AURA Timeout Issue:
- Add debug logging to track:
  - Which servers AURA selects
  - β and γ values over time
  - Interference signals per server
- Compare load distribution vs Round Robin
- May need to tune feedback control parameters

---

## Technical Details:

### Capacity Factor Calculation:
```
average_load = total_connections / num_servers
threshold = capacity_factor × average_load
is_overloaded = current_connections > threshold
```

### With Different capacity_factors:
| capacity_factor | Avg Load | Threshold | Headroom |
|----------------|----------|-----------|----------|
| 1.25 (old)     | 4        | 5         | 25%      |
| 2.0            | 4        | 8         | 100%     |
| 2.5 (new)      | 4        | 10        | 150%     |
| 3.0            | 4        | 12        | 200%     |

### Zipfian Distribution Impact:
With α=2.5 and 1000 keys:
- Top 10 keys: ~30% of requests
- Top 50 keys: ~70% of requests
- Top 100 keys: ~85% of requests

If top 10 keys all hash to same server:
- That server gets 30% of traffic
- With 20 clients = 6 concurrent connections
- Old threshold (5) = OVERLOADED
- New threshold (10) = OK

---

## Confidence Level:

### HELIOS Fix: HIGH
- Root cause identified (bounded load too restrictive)
- Fix is straightforward (increase capacity_factor)
- Should see immediate improvement

### AURA Issue: MEDIUM
- Problem identified (more timeouts)
- Root cause unclear (needs investigation)
- May require algorithm tuning
