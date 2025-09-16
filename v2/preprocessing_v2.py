#!/usr/bin/env python3
"""
MetaHuman Steering Data Preprocessing V2
Separates baseline and turn movements, trains separate GRU models for each movement type.
"""

import pandas as pd
import numpy as np
import re
import json
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from pathlib import Path
import matplotlib.pyplot as plt

# Constants
DATA_DIR = Path("/Users/martinjaramillo/Documents/Unreal+Rokoko/data")
OUT_DIR = DATA_DIR / "processed_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Movement types
MOVEMENT_TYPES = {
    'baseline': 0,
    'left_turn': 1, 
    'right_turn': 2
}

def normalize_headers(df):
    """Normalize column headers"""
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.replace(r"\s+", "_", regex=True)
        .str.replace(r"[()\[\]/\\\-]", "_", regex=True)
    )
    return df

def load_and_clean_data(file_path):
    """Load and clean data from CSV file"""
    df = pd.read_csv(file_path)
    df = normalize_headers(df)
    # Clean data - replace #SPILL! and other non-numeric values
    df = df.replace(['#SPILL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!'], np.nan)
    df = df.replace([np.inf, -np.inf], np.nan).interpolate(limit_direction="both").fillna(0.0)
    return df

def select_steering_features(df):
    """Select features relevant to steering movements (upper body + hands)"""
    common_cols = [c for c in df.columns if c != "Timestamp"]
    
    # Patterns for steering-relevant body parts
    patterns = [
        r"Shoulder", r"Arm", r"Forearm", r"Wrist", r"Hand", r"Digit",  # arms & hands
        r"Clavicle", r"Scapula", r"Thorax", r"Chest", r"Spine", r"Neck", r"Head",  # upper-body
        r"Pelvis",  # core for steering
    ]
    
    def keep_by_patterns(cols, pats):
        rx = re.compile("|".join(pats), re.IGNORECASE)
        return [c for c in cols if rx.search(c)]
    
    steering_cols = keep_by_patterns(common_cols, patterns)
    return steering_cols

def segment_turn_data(df, n_segments=10):
    """Segment turn data into individual trials"""
    total_frames = len(df)
    segment_length = total_frames // n_segments
    
    segments = []
    for i in range(n_segments):
        start_idx = i * segment_length
        end_idx = start_idx + segment_length
        segment = df.iloc[start_idx:end_idx].copy()
        segments.append(segment)
    
    return segments

def time_normalize_sequence(sequence, target_frames=60):
    """Normalize sequence to target number of frames"""
    T, D = sequence.shape
    if T == target_frames:
        return sequence
    
    # Create time vectors
    t_original = np.linspace(0, 1, T)
    t_target = np.linspace(0, 1, target_frames)
    
    # Interpolate each dimension
    normalized = np.zeros((target_frames, D))
    for i in range(D):
        normalized[:, i] = np.interp(t_target, t_original, sequence[:, i])
    
    return normalized

def create_baseline_dataset(baseline_df, feature_cols, target_frames=60):
    """Create baseline dataset with multiple samples"""
    baseline_data = baseline_df[feature_cols].values.astype(np.float32)
    
    # Create multiple baseline samples by taking different windows
    n_samples = 20  # Number of baseline samples to create
    window_size = target_frames * 2  # Use larger windows for baseline
    
    baseline_samples = []
    for i in range(n_samples):
        start_idx = i * (len(baseline_data) // n_samples)
        end_idx = start_idx + window_size
        if end_idx > len(baseline_data):
            end_idx = len(baseline_data)
            start_idx = end_idx - window_size
        
        sample = baseline_data[start_idx:end_idx]
        normalized_sample = time_normalize_sequence(sample, target_frames)
        baseline_samples.append(normalized_sample)
    
    return np.array(baseline_samples)

def create_turn_datasets(left_df, right_df, feature_cols, target_frames=60):
    """Create turn datasets from segmented data"""
    # Segment turn data
    left_segments = segment_turn_data(left_df, 10)
    right_segments = segment_turn_data(right_df, 10)
    
    left_samples = []
    right_samples = []
    
    # Process left turn segments
    for segment in left_segments:
        segment_data = segment[feature_cols].values.astype(np.float32)
        normalized = time_normalize_sequence(segment_data, target_frames)
        left_samples.append(normalized)
    
    # Process right turn segments  
    for segment in right_segments:
        segment_data = segment[feature_cols].values.astype(np.float32)
        normalized = time_normalize_sequence(segment_data, target_frames)
        right_samples.append(normalized)
    
    return np.array(left_samples), np.array(right_samples)

def compute_normalization_stats(baseline_data):
    """Compute normalization statistics from baseline data"""
    # Use median for robust normalization
    mean_vals = np.median(baseline_data, axis=(0, 1))  # Across all samples and time
    std_vals = np.std(baseline_data, axis=(0, 1))
    std_vals = np.where(std_vals == 0, 1e-6, std_vals)  # Avoid division by zero
    
    return mean_vals.astype(np.float32), std_vals.astype(np.float32)

def normalize_data(data, mean_vals, std_vals):
    """Normalize data using computed statistics"""
    return (data - mean_vals) / std_vals

class MovementGRU(nn.Module):
    """GRU model for movement generation"""
    def __init__(self, input_dim, hidden_dim=128, output_dim=None):
        super().__init__()
        if output_dim is None:
            output_dim = input_dim
        
        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True, num_layers=2)
        self.output_layer = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        gru_out, _ = self.gru(x)
        gru_out = self.dropout(gru_out)
        output = self.output_layer(gru_out)
        return output

def train_movement_model(model, train_data, epochs=100, lr=0.001):
    """Train a movement model"""
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    
    # Convert to tensors
    X = torch.tensor(train_data, dtype=torch.float32)
    
    # Create dataset and dataloader
    dataset = TensorDataset(X, X)  # Autoencoder setup
    dataloader = DataLoader(dataset, batch_size=4, shuffle=True)
    
    losses = []
    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_x, batch_y in dataloader:
            optimizer.zero_grad()
            
            # Forward pass
            output = model(batch_x)
            loss = criterion(output, batch_y)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
        
        avg_loss = epoch_loss / len(dataloader)
        losses.append(avg_loss)
        
        if (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}")
    
    return losses

def main():
    print("Loading data...")
    
    # Load datasets
    baseline_df = load_and_clean_data(DATA_DIR / "BaseLine(SittingPosition).csv")
    left_df = load_and_clean_data(DATA_DIR / "LeftTurn_10times.csv")
    right_df = load_and_clean_data(DATA_DIR / "RightTurn_10times.csv")
    
    print(f"Baseline shape: {baseline_df.shape}")
    print(f"Left turn shape: {left_df.shape}")
    print(f"Right turn shape: {right_df.shape}")
    
    # Select steering-relevant features
    feature_cols = select_steering_features(baseline_df)
    print(f"Selected {len(feature_cols)} steering features")
    
    # Create datasets
    print("Creating movement datasets...")
    baseline_data = create_baseline_dataset(baseline_df, feature_cols)
    left_data, right_data = create_turn_datasets(left_df, right_df, feature_cols)
    
    print(f"Baseline samples: {baseline_data.shape}")
    print(f"Left turn samples: {left_data.shape}")
    print(f"Right turn samples: {right_data.shape}")
    
    # Compute normalization statistics from baseline
    print("Computing normalization statistics...")
    mean_vals, std_vals = compute_normalization_stats(baseline_data)
    
    # Normalize all data
    baseline_norm = normalize_data(baseline_data, mean_vals, std_vals)
    left_norm = normalize_data(left_data, mean_vals, std_vals)
    right_norm = normalize_data(right_data, mean_vals, std_vals)
    
    # Train separate models for each movement type
    input_dim = len(feature_cols)
    target_frames = 60
    
    print("Training baseline model...")
    baseline_model = MovementGRU(input_dim)
    baseline_losses = train_movement_model(baseline_model, baseline_norm, epochs=100)
    
    print("Training left turn model...")
    left_model = MovementGRU(input_dim)
    left_losses = train_movement_model(left_model, left_norm, epochs=100)
    
    print("Training right turn model...")
    right_model = MovementGRU(input_dim)
    right_losses = train_movement_model(right_model, right_norm, epochs=100)
    
    # Save models
    print("Saving models...")
    torch.save(baseline_model.state_dict(), OUT_DIR / "baseline_gru.pth")
    torch.save(left_model.state_dict(), OUT_DIR / "left_turn_gru.pth")
    torch.save(right_model.state_dict(), OUT_DIR / "right_turn_gru.pth")
    
    # Save normalization parameters
    norm_params = {
        "mean": mean_vals.tolist(),
        "std": std_vals.tolist(),
        "feature_columns": feature_cols,
        "target_frames": target_frames
    }
    
    with open(OUT_DIR / "normalization_params.json", "w") as f:
        json.dump(norm_params, f, indent=2)
    
    # Save training data for reference
    np.save(OUT_DIR / "baseline_data.npy", baseline_norm)
    np.save(OUT_DIR / "left_turn_data.npy", left_norm)
    np.save(OUT_DIR / "right_turn_data.npy", right_norm)
    
    # Save baseline vector (mean baseline pose)
    baseline_vector = np.mean(baseline_norm, axis=(0, 1))  # Average across all samples and time
    np.save(OUT_DIR / "baseline_vector.npy", baseline_vector)
    
    # Plot training losses
    plt.figure(figsize=(12, 4))
    
    plt.subplot(1, 3, 1)
    plt.plot(baseline_losses)
    plt.title("Baseline Model Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    
    plt.subplot(1, 3, 2)
    plt.plot(left_losses)
    plt.title("Left Turn Model Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    
    plt.subplot(1, 3, 3)
    plt.plot(right_losses)
    plt.title("Right Turn Model Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    
    plt.tight_layout()
    plt.savefig(OUT_DIR / "training_losses.png", dpi=150, bbox_inches='tight')
    plt.show()
    
    print(f"Preprocessing complete! Results saved to {OUT_DIR}")
    print(f"Models trained for baseline, left turn, and right turn movements")
    print(f"Each model can generate 60-frame sequences of {len(feature_cols)} features")

if __name__ == "__main__":
    main()
