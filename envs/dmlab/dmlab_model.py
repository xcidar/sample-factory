import torch

from torch import nn

from algorithms.appo.model_utils import ENCODER_REGISTRY, create_standard_encoder
from envs.dmlab.dmlab30 import DMLAB_VOCABULARY_SIZE, DMLAB_INSTRUCTIONS
from utils.utils import log


class DmlabEncoder(nn.Module):
    def __init__(self, cfg, obs_space):
        super().__init__()

        self.basic_encoder = create_standard_encoder(cfg, obs_space)
        self.encoder_out_size = self.basic_encoder.encoder_out_size

        # same as IMPALA paper
        self.embedding_size = 20
        self.instructions_lstm_units = 64
        self.instructions_lstm_layers = 1

        padding_idx = 0
        self.word_embedding = nn.Embedding(
            num_embeddings=DMLAB_VOCABULARY_SIZE,
            embedding_dim=self.embedding_size,
            padding_idx=padding_idx
        )

        self.instructions_lstm = nn.LSTM(
            input_size=self.embedding_size,
            hidden_size=self.instructions_lstm_units,
            num_layers=self.instructions_lstm_layers,
            batch_first=True,
        )

        # learnable initial state?
        # initial_hidden_values = torch.normal(0, 1, size=(self.instructions_lstm_units, ))
        # self.lstm_h0 = nn.Parameter(initial_hidden_values, requires_grad=True)
        # self.lstm_c0 = nn.Parameter(initial_hidden_values, requires_grad=True)

        self.encoder_out_size += self.instructions_lstm_units
        log.debug('Policy head output size: %r', self.encoder_out_size)

    def forward(self, obs_dict):
        x = self.basic_encoder(obs_dict)

        with torch.no_grad():
            instr = obs_dict[DMLAB_INSTRUCTIONS].type(torch.int64)
            instr_lengths = (instr != 0).sum(axis=1)
            instr_lengths = torch.clamp(instr_lengths, min=1)
            max_instr_len = max(instr_lengths).item()
            instr = instr[:, :max_instr_len]

        instr_embed = self.word_embedding(instr)

        instr_packed = torch.nn.utils.rnn.pack_padded_sequence(
            instr_embed, instr_lengths, batch_first=True, enforce_sorted=False,
        )

        rnn_output, _ = self.instructions_lstm(instr_packed)

        rnn_outputs, sequence_lengths = torch.nn.utils.rnn.pad_packed_sequence(rnn_output, batch_first=True)

        first_dim_idx = torch.arange(rnn_outputs.shape[0])
        last_output_idx = sequence_lengths - 1
        last_outputs = rnn_outputs[first_dim_idx, last_output_idx]

        x = torch.cat((x, last_outputs), dim=1)
        return x


def dmlab_register_models():
    log.info('Adding model class %r to registry', DmlabEncoder)
    ENCODER_REGISTRY['dmlab_instructions'] = DmlabEncoder
