# Sample course inputs

When creating a course, **Course title** is just a display label; it has no effect on generation. **"What do you want to learn?" (the goal)** is what actually steers the AI: it's fed directly into the planner prompt alongside your source material, and determines which concepts get extracted and how the course is structured. The same source document can produce very different courses depending on the goal.

The examples below all assume the same uploaded source: a machine learning textbook chapter or library documentation (e.g. scikit-learn).

## Beginner conceptual course

- **Course title:** Intro to Machine Learning
- **Goal:** Understand the difference between supervised and unsupervised learning, and how a model actually "learns" from data.

## Practical / hands-on course

- **Course title:** Training my first classifier
- **Goal:** Learn how to train, evaluate, and tune a classification model in scikit-learn, including train/test splits and cross-validation.

## Math-foundations course

- **Course title:** ML math foundations
- **Goal:** Understand the linear algebra and gradient descent math behind how models get trained, not just how to call the library functions.

## Algorithms-from-scratch course

- **Course title:** ML algorithms from scratch
- **Goal:** Implement the core algorithms (k-nearest neighbors, gradient descent, a decision tree split, k-means) from scratch in plain Python/NumPy, with no scikit-learn calls, so I understand the mechanics, not just the API. Each lab should be a single pure function I fill in, checked against exact input/output cases the way LeetCode problems are graded, not against an accuracy threshold on a dataset.

---

Same source material each time, but the second example would generate hands-on coding labs around `fit()`/`predict()`/`cross_val_score`, the third would generate conceptual lessons about gradients and loss functions instead, and the fourth pushes the planner toward small, pure-function labs (e.g. `def knn_predict(X_train, y_train, x_query, k): ...`) graded with deterministic, LeetCode-style test cases: fixed inputs mapped to exact expected outputs, rather than the looser "train it and check the score" style of the second example.
