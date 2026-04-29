import torch
import torch.nn as nn


class LogTransformer(nn.Module):
    def __init__(
        self,
        vocab_size,
        max_len=128,
        embed_dim=32,
        num_heads=2,
        num_layers=1,
        dropout=0.1,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size + 1, embed_dim, padding_idx=0)
        self.positional = nn.Parameter(torch.randn(1, max_len, embed_dim) * 0.02)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=embed_dim * 4,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.classifier = nn.Linear(embed_dim, 2)

    def forward(self, x):
        mask = x.eq(0)
        embedded = self.embedding(x) + self.positional[:, : x.size(1), :]
        encoded = self.encoder(embedded, src_key_padding_mask=mask)

        valid = (~mask).unsqueeze(-1).float()
        pooled = (encoded * valid).sum(dim=1) / valid.sum(dim=1).clamp_min(1.0)
        return self.classifier(pooled)


def encode_sequence(events, event_to_idx, max_len):
    encoded = [event_to_idx.get(event_id, 0) for event_id in events[:max_len]]
    encoded += [0] * (max_len - len(encoded))
    return encoded
