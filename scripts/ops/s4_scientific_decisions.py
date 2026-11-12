"""Explicit, complete scientific dispositions for the D2L S4 extraction."""

from __future__ import annotations

# Every extracted row has an explicit disposition. Summaries are corrected in
# place so existing concept IDs remain stable in the isolated graph.
CONCEPT_DECISIONS: dict[str, tuple[str, str, str | None]] = {
    "Regression": (
        "MODIFY",
        "The chapter defines regression as numerical prediction.",
        "A prediction task that estimates a numerical target from input features.",
    ),
    "Linear Regression": (
        "MODIFY",
        "Replace the section recap with the model definition and fitting objective.",
        "A regression model that predicts a numerical target from an affine weighted sum of features; its parameters can be fit by minimizing squared loss.",
    ),
    "Linear Transformation": (
        "MODIFY",
        "The bias makes the chapter's feature map affine, not strictly linear.",
        "A weighted-sum map of input features; adding a bias yields the affine transformation used for linear-regression predictions.",
    ),
    "Model": (
        "REJECT",
        "The extracted sentence concerns observation noise, not a supported generic model definition.",
        None,
    ),
    "Loss Function": (
        "MODIFY",
        "Loss is a function; nonnegative loss is typical rather than universal.",
        "A function that measures prediction error; this chapter uses squared error to fit linear regression.",
    ),
    "Stochastic Gradient Descent": (
        "MODIFY",
        "Distinguish the chapter's single-example extreme from minibatch SGD.",
        "A gradient-based optimizer that updates parameters using one randomly selected training example at a time in the chapter's comparison.",
    ),
    "Minibatch Stochastic Gradient Descent": (
        "MODIFY",
        "Use the chapter's random minibatch gradient update; remove the false UNLOCKS claim.",
        "An optimizer that repeatedly samples a random minibatch and updates parameters using the average loss gradient over that minibatch.",
    ),
    "Prediction": (
        "KEEP",
        "The Predictions section directly defines this use of the fitted model.",
        None,
    ),
    "Vectorization": (
        "KEEP",
        "The Vectorization for Speed section explicitly processes minibatches together.",
        None,
    ),
    "Normal Distribution": (
        "MODIFY",
        "Tie the Gaussian definition to the chapter's noise assumption and squared loss.",
        "A Gaussian distribution described by mean and variance; a Gaussian noise assumption motivates squared loss in this chapter.",
    ),
    "Maximum Likelihood Estimation": (
        "MODIFY",
        "Replace the tautology with the likelihood objective and Gaussian example.",
        "Parameter estimation by maximizing the probability of observed data; under Gaussian observation noise this yields a squared-error objective.",
    ),
    "Mathematics": (
        "REJECT",
        "A passing Biology analogy does not define a relevant linear-regression concept.",
        None,
    ),
}

# Keys are the 21 new typed relationships in the uncorrected staging graph.
# A RELATED edge is kept only with a defensible semantic label and exact chapter support.
EDGE_DECISIONS: dict[tuple[str, str, str], tuple[str, str, str | None]] = {
    ("regression", "linear_regression", "RELATED"): (
        "MODIFY",
        "Linear regression is a specific regression method.",
        "has_specialization",
    ),
    ("regression", "prediction", "RELATED"): (
        "MODIFY",
        "Regression predicts numerical values.",
        "predicts_numeric_target",
    ),
    ("regression", "linear_transformation", "RELATED"): (
        "REJECT",
        "Regression in general need not use an affine map.",
        None,
    ),
    ("regression", "model", "RELATED"): ("REJECT", "Generic Model row is removed.", None),
    ("regression", "normal_distribution", "RELATED"): (
        "REJECT",
        "Regression in general need not assume Gaussian noise.",
        None,
    ),
    ("regression", "stochastic_gradient_descent", "RELATED"): (
        "REJECT",
        "Regression in general need not use SGD.",
        None,
    ),
    ("linear_regression", "linear_transformation", "RELATED"): (
        "MODIFY",
        "The chapter's regression prediction uses an affine weighted sum.",
        "uses_affine_map",
    ),
    ("linear_regression", "loss_function", "RELATED"): (
        "MODIFY",
        "The chapter fits linear regression with squared loss.",
        "uses_squared_loss",
    ),
    ("linear_regression", "model", "RELATED"): ("REJECT", "Generic Model row is removed.", None),
    ("linear_regression", "prediction", "RELATED"): (
        "MODIFY",
        "The fitted regression model produces predictions.",
        "produces_prediction",
    ),
    ("linear_regression", "stochastic_gradient_descent", "RELATED"): (
        "REJECT",
        "The chapter uses minibatch SGD; this single-example association is too loose.",
        None,
    ),
    ("linear_transformation", "model", "RELATED"): (
        "REJECT",
        "Generic Model row is removed.",
        None,
    ),
    ("linear_transformation", "normal_distribution", "RELATED"): (
        "REJECT",
        "An affine map does not imply Gaussian noise.",
        None,
    ),
    ("linear_transformation", "prediction", "RELATED"): (
        "MODIFY",
        "The weighted feature map yields a target estimate.",
        "maps_features_to_prediction",
    ),
    ("loss_function", "stochastic_gradient_descent", "RELATED"): (
        "MODIFY",
        "SGD updates parameters in a direction that lowers loss.",
        "optimized_by",
    ),
    ("minibatch_stochastic_gradient_descent", "stochastic_gradient_descent", "UNLOCKS"): (
        "REJECT",
        "These are batch-size strategies, not a progression unlocked in either direction.",
        None,
    ),
    ("model", "normal_distribution", "RELATED"): (
        "REJECT",
        "Generic Model row is removed; Gaussian noise is optional.",
        None,
    ),
    ("model", "prediction", "RELATED"): ("REJECT", "Generic Model row is removed.", None),
    ("normal_distribution", "linear_regression", "RELATED"): (
        "MODIFY",
        "Gaussian observation noise motivates squared loss for this model.",
        "motivates_squared_loss",
    ),
    ("prediction", "normal_distribution", "RELATED"): (
        "REJECT",
        "Prediction itself does not imply a normal distribution.",
        None,
    ),
    ("stochastic_gradient_descent", "normal_distribution", "RELATED"): (
        "REJECT",
        "SGD does not require Gaussian noise.",
        None,
    ),
}
