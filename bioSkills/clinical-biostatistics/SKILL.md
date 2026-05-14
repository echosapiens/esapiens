# Clinical Biostatistics

Apply statistical methods to clinical trial and observational study data.

## Recommended Tools

- **scipy.stats**: hypothesis testing, distributions
- **statsmodels**: regression, survival analysis, mixed models
- **lifelines** (Python): Kaplan-Meier, Cox regression
- **Pingouin**: power analysis, effect sizes
- **R**: gold standard for biostatistics via rpy2

## Common Workflows

### Hypothesis Testing

```python
from scipy import stats
import pingouin as pg

# Two-sample t-test (Welch's)
t_stat, p_val = stats.ttest_ind(group_a, group_b, equal_var=False)

# Mann-Whitney U (non-parametric)
u_stat, p_val = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")

# Effect size (Cohen's d)
d = pg.compute_effsize(group_a, group_b, eftype="cohen")

# Multiple testing correction
from statsmodels.stats.multitest import multipletests
reject, padj, _, _ = multipletests(p_values, method="fdr_bh")
```

### Power Analysis

```python
import pingouin as pg

# Sample size for two-sample t-test
power = pg.power_ttest(d=0.5, alpha=0.05, power=0.8, alternative="two-sided")
print(f"Required sample size per group: {power:.0f}")
```

### Survival Analysis (lifelines)

```python
from lifelines import KaplanMeierFitter, CoxPHFitter

# Kaplan-Meier
kmf = KaplanMeierFitter()
kmf.fit(durations=df["time"], event_observed=df["event"])
kmf.plot_survival_function()

# Log-rank test
from lifelines.statistics import logrank_test
result = logrank_test(
    df_A["time"], df_B["time"],
    df_A["event"], df_B["event"]
)
print(f"Log-rank p-value: {result.p_value:.4f}")

# Cox proportional hazards
cph = CoxPHFitter()
cph.fit(df, duration_col="time", event_col="event")
cph.print_summary()
```

### Regression with Confounders

```python
import statsmodels.api as sm
import statsmodels.formula.api as smf

# Multiple linear regression with confounders
model = smf.ols("outcome ~ treatment + age + sex + bmi", data=df).fit()
print(model.summary())

# Mixed-effects model (random intercept for site)
model = smf.mixedlm("outcome ~ treatment + age", data=df,
                     groups=df["site"]).fit()
print(model.summary())
```

## Key Parameters

- Significance threshold: alpha = 0.05 (two-sided)
- Power: 0.80 minimum for study design
- FDR (Benjamini-Hochberg) for multiple comparisons
- Reporting: include effect sizes (Cohen's d, odds ratio, hazard ratio) with 95% CI

## Gotchas

- Always check distributional assumptions before parametric tests
- For small samples (n < 30), prefer non-parametric methods
- Multiple comparisons must be corrected; FDR is standard in genomics
- Cox PH requires proportional hazards assumption; check with Schoenfeld residuals
- Confounders must be included in the model; unadjusted comparisons are often meaningless