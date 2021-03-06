import torch
import torch.nn.functional as F
from torch import nn


class AttentionRNN(nn.Module):
    """Class containing the architecture of the model and the corresponding weights
    Contains a classical implementation of attention model"""

    def __init__(self, input_size, num_alphabet, Ty, project_size=256, encoder_hidden_size=128,
                 encoder_num_layers=2, decoder_hidden_size=128, decoder_num_layers=1, dropout=0.1,
                 save_attention=False):
        super().__init__()
        self.num_alphabet = num_alphabet
        self.input_size = input_size
        self.Ty = Ty
        self.Tx = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

        self.fc1 = nn.Linear(input_size, project_size)
        self.fc2 = nn.Linear(input_size - 1, project_size)
        self.encoder = nn.LSTM(project_size, hidden_size=encoder_hidden_size, num_layers=encoder_num_layers,
                               bidirectional=True, batch_first=True, dropout=dropout)
        self.post_attention_lstm = nn.LSTM(self.encoder.hidden_size * 2, hidden_size=decoder_hidden_size,
                                           num_layers=decoder_num_layers, batch_first=True, dropout=dropout)
        self.attention = nn.Sequential(
            nn.Linear(
                self.encoder.hidden_size * 2 + self.post_attention_lstm.hidden_size *
                self.post_attention_lstm.num_layers,
                80
            ),
            nn.ReLU(), nn.Linear(80, 1))
        self.fc = nn.Linear(self.post_attention_lstm.hidden_size, self.num_alphabet)
        self.infos = {"attention": []}
        self.save_attention = save_attention

    def calc_context(self, x, s_prev):
        repeat = s_prev.unsqueeze(1).expand(s_prev.shape[0], self.Tx, s_prev.shape[1])
        attention = torch.cat((x, repeat), dim=2)
        attention = self.attention(attention)
        attention = attention.squeeze(dim=-1)
        attention = F.softmax(attention, dim=1)
        context = (x * attention.unsqueeze(dim=-1)).sum(dim=1)
        if self.save_attention:
            self.infos["attention"].append(attention)
        return context

    def forward(self, x, x2):
        if self.save_attention:
            self.infos["attention"] = []

        result = []
        x = F.relu(self.fc1(x))
        x2 = F.relu(self.fc2(x2))
        x = torch.cat([x, x2], dim=-2)
        x, _ = self.encoder(x)
        x = self.dropout1(x)
        self.Tx = x.shape[1]
        s_prev, c_prev = self.init_hidden(self.post_attention_lstm, x.shape[0])
        for _ in range(self.Ty):
            s_prev_t = s_prev.transpose(0, 1)
            s_prev_t = s_prev_t.reshape(s_prev_t.shape[0], -1)
            context = self.calc_context(x, s_prev_t)
            context = context.unsqueeze(dim=1)
            y, (s_prev, c_prev) = self.post_attention_lstm(context, (s_prev, c_prev))
            y = self.dropout2(y)
            y = y.squeeze(dim=1)
            y = self.fc(y)
            result.append(y)
        result = torch.stack(result, dim=1)
        return result

    def init_hidden(self, layer, batch_size):
        h0 = torch.zeros((layer.num_layers, batch_size, layer.hidden_size)).to(self.device)
        c0 = torch.zeros((layer.num_layers, batch_size, layer.hidden_size)).to(self.device)
        return h0, c0

    def predict(self, x, eos, max_iter=100):
        if self.save_attention:
            self.infos["attention"] = []
        # (Tx, )
        result = []
        x = x.unsqueeze(0)
        x = self.fc1(x)
        x, _ = self.encoder(x)
        self.Tx = x.shape[1]
        s_prev, c_prev = self.init_hidden(self.post_attention_lstm, x.shape[0])
        for _ in range(max_iter):
            y, s_prev, c_prev = self.step_predict(x, s_prev, c_prev)
            result.append(int(torch.argmax(y, -1)[0]))
            if result[-1] == eos:
                break
        result = torch.tensor(result)
        return result

    def step_predict(self, encoder_out, s_prev, c_prev):
        context = self.calc_context(encoder_out, s_prev.squeeze(0))
        context = context.unsqueeze(dim=1)
        y, (s_prev, c_prev) = self.post_attention_lstm(context, (s_prev, c_prev))
        y = y.squeeze(dim=1)
        y = self.fc(y)
        return y, s_prev, c_prev


if __name__ == "__main__":
    arch = AttentionRNN(num_alphabet=50, Ty=100, save_attention=True)
    x = torch.rand((5, 30, 50))
    y = arch(x)
    attention = arch.infos["attention"]
    print(attention[0].shape)
    attention = torch.stack(attention, dim=2)
    print(attention.shape)
