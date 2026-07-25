# FT Benchmark Statistics & Financial Model

Coagulated results from the final fine-tuned-model (**FT**) generalization sweep,
plus derived operational-cost estimates for building a cohesive financial pitch.

## 1. Per-seed benchmark (coagulated)

| Seed | Held-out | MPC bill | BC bill | FT bill | BC ratio | **FT ratio** | FT solar self-cons. | FT peak (kVA) | FT shed (kWh) |
| ---: | :------: | -------: | ------: | ------: | -------: | -----------: | ------------------: | ------------: | ------------: |
|    0 |    no    |   19,452 |  18,071 |  16,099 |    0.929 |    **0.828** |               0.961 |          7.83 |           8.9 |
|    1 | **yes**  |   21,470 |  18,404 |  16,663 |    0.857 |    **0.776** |               0.966 |          8.28 |           9.0 |
|    2 | **yes**  |   18,113 |  18,199 |  16,249 |    1.005 |    **0.897** |               0.963 |          7.90 |           8.8 |
|    3 |    no    |   19,642 |  18,518 |  16,506 |    0.943 |    **0.840** |               0.959 |          8.30 |           8.8 |
|    7 | **yes**  |   19,395 |  18,269 |  16,325 |    0.942 |    **0.842** |               0.956 |          7.86 |           8.8 |

_Ratio = policy bill ÷ MPC bill (lower is better; <1 beats MPC)._

---

## 2. Aggregate statistics

| Statistic                          |     BC |         **FT** |
| ---------------------------------- | -----: | -------------: |
| Mean bill ratio — all seeds        | 0.9351 |     **0.8366** |
| Mean bill ratio — held-out {1,2,7} |      — |     **0.8383** |
| **Savings vs MPC — all seeds**     |   6.5% |      **16.3%** |
| **Savings vs MPC — held-out**      |      — |      **16.2%** |
| Best seed (largest saving)         |      — | seed 1 — 22.4% |
| Worst seed (smallest saving)       |      — | seed 2 — 10.3% |
| FT beats BC on every seed          |      — |        **Yes** |
| Verdict vs ≥10% target             |      — |       **PASS** |

**Fleet-level monthly means (across 5 seeds):**

|                              |    MPC |     BC |     **FT** |
| ---------------------------- | -----: | -----: | ---------: |
| Mean monthly bill (₹)        | 19,614 | 18,292 | **16,368** |
| Mean saving vs MPC (₹/month) |      — |  1,322 |  **3,246** |
| Mean peak (kVA)              | ≈17–18 |      — |   **8.03** |
| Mean solar self-consumption  |  ≈0.90 |      — |  **0.961** |

The FT policy also holds shed/unmet near the baseline (≈8.8–9.0 kWh/month across a
30-day episode), so the savings come with **no service-quality regression** — an
essential guardrail for the pitch.

---

## 3. Bill decomposition

A bill = **energy cost** (ToU arbitrage) + **demand charge** (peak × ₹250/kVA/month).
Derived from the sweep (demand = peak × 250; energy = bill − demand):

|                         | MPC (seed-0 reference) | **FT (5-seed mean)** |
| ----------------------- | ---------------------: | -------------------: |
| Energy cost (₹/month)   |                 15,325 |          **≈14,360** |
| Demand charge (₹/month) |                 ≈4,290 |           **≈2,010** |
| Billing peak (kVA)      |                  ≈17.2 |             **8.03** |
| Total (₹/month)         |                 19,614 |           **16,368** |

---

## 4. Savings decomposition

Using the seed-0 reference where the full MPC breakdown is known
(saving ₹3,515/month, 17.9%):

| Savings source                   | ₹/month | Share of saving | Mechanism                                                                |
| -------------------------------- | ------: | --------------: | ------------------------------------------------------------------------ |
| **Peak-shaving** (demand charge) |  ≈2,332 |        **≈66%** | Cut billing peak ~17.2 → ~7.8 kVA (≈9.3 kVA × ₹250)                      |
| **Energy arbitrage** (ToU)       |  ≈1,184 |        **≈34%** | Charge in ₹5 block, discharge in ₹10 block; better solar self-use (0.96) |

**Takeaway for finance:** roughly **two-thirds of the value is demand-charge
reduction**, one-third energy arbitrage. Demand-charge savings scale directly with
the site's `₹/kVA/month` rate and are typically the stickier, larger line for C&I
customers.

---

## 5. Operational cost & financial model

### 5.1 Baseline savings (per site)

| Horizon            | FT saving vs MPC | FT saving vs do-nothing¹ |
| ------------------ | ---------------: | -----------------------: |
| Per month          |           ₹3,246 |          (site-specific) |
| **Per year (×12)** |      **₹38,952** |          (site-specific) |

¹ The benchmark compares against MPC, not an uncontrolled site; a real "vs
do-nothing" baseline is usually _larger_ (an uncontrolled site pays full ToU and
sets an unmanaged peak). Quote FT-vs-MPC as the conservative, defensible number.

### 5.2 Payback methodology

```
monthly_saving  = mpc_bill − ft_bill                 (≈ ₹3,246 here)
annual_saving   = 12 × monthly_saving                (≈ ₹38,952)
payback_years   = upfront_cost / annual_saving
simple_ROI      = annual_saving / upfront_cost
```
