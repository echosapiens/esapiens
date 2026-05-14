# Machine Learning for Bioinformatics

Apply ML methods to biological data for classification, regression, clustering, and feature selection.

## Recommended Tools

- **scikit-learn**: general ML (classification, regression, clustering)
- **xgboost / lightgbm**: gradient boosting for tabular data
- **PyTorch / TensorFlow**: deep learning frameworks
- **scvi-tools**: deep generative models for single-cell data
- **DeepChem**: molecular ML and drug discovery
- **Docker/Singularity**: reproducible environments

## Common Workflows

### Classification with scikit-learn

```python
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Pipeline with scaling and model
pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", RandomForestClassifier(n_estimators=500, max_depth=10, random_state=42))
])

# Cross-validate
cv_scores = cross_val_score(pipe, X_train, y_train, cv=5, scoring="roc_auc")
print(f"CV AUC: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")

# Train and evaluate
pipe.fit(X_train, y_train)
y_pred = pipe.predict(X_test)
print(classification_report(y_test, y_pred))
```

### Feature Importance (XGBoost)

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = xgb.XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.05)
model.fit(X_train, y_train)

# Feature importance
importance = pd.DataFrame({
    "feature": X.columns,
    "importance": model.feature_importances_
}).sort_values("importance", ascending=False)

print(importance.head(20))
```

### Dimensionality Reduction for Visualization

```python
from sklearn.decomposition import PCA
from umap import UMAP
import matplotlib.pyplot as plt

# PCA
pca = PCA(n_components=50)
X_pca = pca.fit_transform(X)
print(f"Explained variance: {pca.explained_variance_ratio_[:5].sum():.2%}")

# UMAP
reducer = UMAP(n_neighbors=15, min_dist=0.1, random_state=42)
X_umap = reducer.fit_transform(X_pca)

plt.scatter(X_umap[:, 0], X_umap[:, 1], c=y, s=5, alpha=0.5)
plt.savefig("umap.png", dpi=300)
```

## Key Parameters

- Train/test split: 80/20 or 70/30, stratified by class
- Cross-validation: 5-fold standard; 10-fold for small datasets
- Random Forest: 500+ trees, max_depth tuned via grid search
- XGBoost: learning_rate=0.05, early_stopping_rounds=50
- UMAP: n_neighbors=15, min_dist=0.1 for general use

## Gotchas

- Always stratify splits for imbalanced datasets
- Scale features before distance-based methods (SVM, kNN, PCA)
- Report both training and test metrics; large gap = overfitting
- Use nested cross-validation for hyperparameter tuning to avoid data leakage
- Biological data is often high-dimensional low-sample; prefer regularized models