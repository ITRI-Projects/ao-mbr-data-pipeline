"""Small deterministic CPU LSTM with validation-only epoch selection."""
import numpy as np
import torch
from torch import nn


class SequenceRegressor(nn.Module):
    def __init__(self, features, hidden=24):
        super().__init__()
        self.lstm = nn.LSTM(features, hidden, batch_first=True)
        self.output = nn.Linear(hidden, 1)

    def forward(self, x):
        sequence, _ = self.lstm(x)
        return self.output(sequence[:, -1]).squeeze(-1)


def train_lstm(X, y, split, folder, epochs=60, seed=42):
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    train, val = split == "train", split == "validation"
    center, scale = float(y[train].mean()), float(y[train].std())
    if scale == 0:
        scale = 1.0
    x = torch.tensor(X, dtype=torch.float32)
    labels = torch.tensor((y - center) / scale, dtype=torch.float32)
    model = SequenceRegressor(X.shape[2])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.003)
    loss_fn = nn.MSELoss()
    best, patience, history = float("inf"), 0, []
    train_positions = np.flatnonzero(train)
    for epoch in range(epochs):
        model.train()
        for positions in np.array_split(train_positions, max(1, int(np.ceil(len(train_positions) / 64)))):
            optimizer.zero_grad()
            loss = loss_fn(model(x[positions]), labels[positions])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            train_loss = float(loss_fn(model(x[train]), labels[train]))
            val_loss = float(loss_fn(model(x[val]), labels[val]))
        history.append({"epoch": epoch + 1, "train_mse_scaled": train_loss, "validation_mse_scaled": val_loss})
        if val_loss < best - 1e-8:
            best, patience = val_loss, 0
            state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch + 1
        else:
            patience += 1
        if patience >= 12:
            break
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        predicted = model(x).numpy() * scale + center
    path = folder / "lstm.pt"
    torch.save({"state_dict": state, "input_features": X.shape[2], "hidden": 24,
                "target_center": center, "target_scale": scale, "best_epoch": best_epoch}, path)
    saved = torch.load(path, map_location="cpu", weights_only=True)
    restored = SequenceRegressor(saved["input_features"], saved["hidden"])
    restored.load_state_dict(saved["state_dict"])
    restored.eval()
    with torch.no_grad():
        np.testing.assert_allclose(predicted, restored(x).numpy() * saved["target_scale"] + saved["target_center"])
    return predicted, history
