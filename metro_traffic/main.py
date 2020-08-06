import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn
import numpy as np

from metro_traffic.attention_rnn import AttentionRNN
from metro_traffic.train import torch_train_loop
from metro_traffic.utils import CustomStandardScaler

train = pd.read_csv('train.csv')
train.drop(columns='date_time', inplace=True)

packet_size = 48
x1s = train.values[:-packet_size]
x2s = train.drop(columns='traffic_volume').values[packet_size:]
targets = train['traffic_volume'].values[packet_size:]

x1s_train, x1s_test, x2s_train, x2s_test, target_train, target_test = train_test_split(x1s, x2s, targets,
                                                                                       shuffle=False, test_size=0.1)
ss = CustomStandardScaler(num=2)
x1s_train, x2s_train = ss.fit_transform([x1s_train, x2s_train])
x1s_test, x2s_test = ss.transform([x1s_test, x2s_test])

target_train, target_test = np.expand_dims(target_train, -1), np.expand_dims(target_test, -1)
model = AttentionRNN(x1s_train.shape[-1], 1, Ty=48)

data_train = [x1s_train, x2s_train]
data_test = [x1s_test, x2s_test]

model = torch_train_loop(model, data_train, data_test, target_train, target_test, batch_size=4, num_epochs=60,
                         criterion=nn.MSELoss(),
                         print_every=20, lr=0.001)

torch.save(model, 'model.pt')