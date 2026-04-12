import shap
import pandas as pd
import numpy as np
import torch
import matplotlib.pyplot as plt

from client.inference_engine import _get_cached_assets

def _predict_proba_for_shap(X, scaler, model, columns):
    # This is a wrapper function for shap to calculate predictions
    if isinstance(X, np.ndarray):
        df = pd.DataFrame(X, columns=columns)
    elif isinstance(X, pd.DataFrame):
        df = X
    else:
        raise ValueError("Unsupported input format for SHAP")

    scaled = scaler.transform(df).astype(np.float32)
    tensor = torch.from_numpy(scaled).float().to(model.device)
    
    model.model.eval()
    with torch.no_grad():
        output = model.model(tensor)
        
    return output.cpu().numpy().flatten()


def get_global_explainer(X_background, max_display=10):
    columns, model, scaler, _ = _get_cached_assets()
    if model is None or model.model is None:
         raise ValueError("Model is not loaded.")
         
    def model_predict(X):
        return _predict_proba_for_shap(X, scaler, model, columns)
        
    explainer = shap.DeepExplainer(
        model.model,
        torch.from_numpy(scaler.transform(pd.DataFrame(X_background, columns=columns)).astype(np.float32)).to(model.device)
    )

    # Calculate shap values on background to show summary
    shap_values = explainer.shap_values(
        torch.from_numpy(scaler.transform(pd.DataFrame(X_background, columns=columns)).astype(np.float32)).to(model.device)
    )

    # Plot
    fig = plt.figure()
    shap.summary_plot(shap_values, X_background, feature_names=columns, max_display=max_display, show=False)
    
    return fig


def get_local_explainer(X_background, instance_data):
    columns, model, scaler, _ = _get_cached_assets()
    if model is None or model.model is None:
         raise ValueError("Model is not loaded.")

    explainer = shap.DeepExplainer(
        model.model,
        torch.from_numpy(scaler.transform(pd.DataFrame(X_background, columns=columns)).astype(np.float32)).to(model.device)
    )

    if isinstance(instance_data, dict):
        # Convert dictionary to ordered list based on columns
        instance_data = [instance_data.get(col, 0.0) for col in columns]

    instance_df = pd.DataFrame([instance_data], columns=columns)
    scaled_instance = scaler.transform(instance_df).astype(np.float32)
    
    shap_values = explainer.shap_values(
        torch.from_numpy(scaled_instance).to(model.device)
    )
    
    expected_value = explainer.expected_value
    if isinstance(expected_value, np.ndarray):
        expected_value = expected_value[0]
        
    # Plot waterfall
    # create shap explanation object
    explanation = shap.Explanation(
        values=shap_values[0] if isinstance(shap_values, list) else shap_values,
        base_values=expected_value,
        data=instance_df.iloc[0].values,
        feature_names=columns
    )
    
    fig = plt.figure()
    shap.waterfall_plot(explanation[0], show=False)
    
    return fig
