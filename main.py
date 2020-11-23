import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_squared_log_error
from sklearn.model_selection import train_test_split
from configuration.parser import load_configuration
from core.RNN import SimpleRNN
from datetime import datetime


def create_sequence(data, label, time_window):
    size = int(data.shape[0] / time_window) + data.size % time_window

    X = np.zeros((size, time_window - 1))
    y = np.zeros((size, 1))

    counter = 0
    for i in range(time_window, data.shape[0], time_window):
        X[counter] = (data[label].values[i - time_window: i - 1])
        y[counter] = (data[label].values[i])
        counter += 1

    return X, y


def train_model(model, num_epochs, criterion, optimizer, data):
    X_train = data[0]
    y_train = data[1]

    for epoch in range(num_epochs):
        for i in range(X_train.shape[0]):
            optimizer.zero_grad()

            scores = model(X_train[i].view(seq_length, 1, -1))
            loss = criterion(scores, y_train[i])

            loss.backward()

            optimizer.step()

            print('', end='\r epoch: {:3}/{:3}, loss: {:10.8f}, completed: {:.2f}%'.format(epoch + 1,
                                                                                           num_epochs,
                                                                                           loss.item(),
                                                                                           (i / X_train.shape[
                                                                                               0]) * 100))

        print('\n')

    return model


def to_tensor(a, device):
    return torch.from_numpy(a).to(device)


if __name__ == '__main__':

    print('\n********************************************************')
    print('                         Forexer')
    print('********************************************************\n\n')

    print('GPU is {}available'.format('' if torch.cuda.is_available() else 'not '))
    print('GPU device count: {}'.format(torch.cuda.device_count()))
    torch.set_default_tensor_type('torch.DoubleTensor')

    # load configurations
    config = load_configuration()

    # mapping parameters
    label = config.model.parameters.label
    time_window = config.model.parameters.time_window

    input_size = config.model.parameters.input_size
    seq_length = config.model.parameters.sequence_length
    num_layers = config.model.parameters.num_layers
    hidden_size = config.model.parameters.hidden_szie
    learning_rate = config.model.parameters.lr
    num_epochs = config.model.parameters.num_epochs
    device = torch.device('cuda' if torch.cuda.is_available() and config.model.parameters.device == 'cuda' else 'cpu')

    # creating model
    model = SimpleRNN(input_size, hidden_size, seq_length, num_layers, device).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # loading pre-trained weights
    if config.model.pre_trained != '':
        try:
            model_checkpoints = torch.load(config.model.pre_trained, map_location=device)
            model.load_state_dict(model_checkpoints['model_state_dict'])
            optimizer.load_state_dict(model_checkpoints['optimizer_state_dict'])
            criterion.load_state_dict(model_checkpoints['criterion_state_dict'])
        except Exception as e:
            print('failed to load the model properly. Error: {}'.format(e))

    if config.model.mode == 'train':
        data = pd.read_csv(config.data.train_path)
        print('Loaded {} data with shape of {}'.format(config.data.train_path, data.shape))

        # to sequence
        X, y = create_sequence(data, label, time_window)

        # split to train and dev set
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=config.data.dev_size)

        # train model
        print('Training the model...')
        model = train_model(model, num_epochs, criterion, optimizer,
                            (to_tensor(X_train, device), to_tensor(y_train, device)))

        # evaluating model
        print('Evaluating the model...')
        y_preds = model.predict(to_tensor(X_test, device))
        y_preds = y_preds.cpu().detach().numpy()
        score = r2_score(y_preds, y_test)

        if config.model.save_path != '':
            print('Saving model. path: {}'.format(config.model.save_path))
            now = datetime.now()
            torch.save({
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'criterion_state_dict': criterion.state_dict()
            },
                config.model.save_path +
                str(now.date()) +
                '--' +
                str(now.time())[:5].replace(':', '-') +
                '{:3f}'.format(score) + '.zip')

    else:  # if config.model.mode == 'test':
        data = pd.read_csv(config.data.test_path)
        print('Loaded {} data with shape of {}'.format(config.data.train_path, data.shape))

        # to sequence
        X_test, y_test = create_sequence(data, label, time_window)

        # evaluating model
        print('Evaluating the model...')
        y_preds = model.predict(to_tensor(X_test, device))

        y_preds = y_preds.cpu().detach().numpy()
        score = r2_score(y_preds, y_test)

print('R2 score: {:.3f}\nMSLE: {:.5f}'.format(score, mean_squared_log_error(y_preds, y_test)))
