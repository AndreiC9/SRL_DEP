from __future__ import unicode_literals, print_function, division
# from io import open
# import unicodedata
# import string
# import re
# import random
# from nnet.util import *

import numpy as np
import torch
# import math
import torch.nn as nn
import torch.autograd
from torch.autograd import Variable
# from torch import optim
import torch.nn.functional as F
import torch.nn.utils.rnn as rnn
import torch.nn.init as init
# from numpy import random as nr
# from operator import itemgetter

_BIG_NUMBER = 10. ** 6.

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def cat(l, dimension=-1):
    valid_l = l
    if dimension < 0:
        dimension += len(valid_l[0].size())
    return torch.cat(valid_l, dimension)


'''
--hps "{'id': 1, 'sent_edim': 100, 'sent_hdim': 512,
'frame_edim': 128, 'role_edim': 128, 'pos_edim': 16, 'rec_layers': 1,
'gc_layers': 0, 'pos': True, 'rm':0, 'alpha': 0.25,
'p_lemmas':True}"
'''

# Interpreting the hyperparameters used:
# edim - embedding dimension
# hdim - ???

#


class BiLSTMTagger(nn.Module):

    # def __init__(self, embedding_dim, hidden_dim, vocab_size, tagset_size):
    def __init__(self, hps, *_):  # *_ means no interest in further arguments
        super(BiLSTMTagger, self).__init__()

        batch_size = hps['batch_size']
        lstm_hidden_dim = hps['sent_hdim']

        # DEP  - short for dependency, i.e. the part of the system which
        # extracts syntactic information
        # sent - most likely refers to sentence
        # pos  - part of speech

        # The input of the dependency extractor has 2 word embeddings (one
        # randomly initialized and one pre-trained) and 1 part of speech
        # embedding + region dimension
        # sent_embedding_dim_DEP = 2 * \
        #     hps['sent_edim'] + 1 * hps['pos_edim'] + 16

        # The input of the dependency extractor has 2 word embeddings and 1
        # part of speech embedding + region dimension
        sent_embedding_dim_SRL = 3 * \
            hps['sent_edim'] + 1 * hps['pos_edim'] + 16
        self.SRL_input_dim = sent_embedding_dim_SRL
        # for the region mark

        # Set to 128 dimensions
        # role_embedding_dim = hps['role_edim']

        # frame_embedding_dim = role_embedding_dim

        # Word vocabulary size, based on file size
        vocab_size = hps['vword']

        # Role labels number based on the size of the label file
        self.tagset_size = hps['vbio']

        # Numbers of parts of speech
        self.pos_size = hps['vpos']

        # TODO Is this types of links or labeled links?
        self.dep_size = hps['vdep']

        # Frameset size, refers to the frame that a predicate belongs to
        self.frameset_size = hps['vframe']

        # Number of LSTM layers in the BiLSTM, set to 1 in the hyperparameters
        self.num_layers = hps['rec_layers']
        self.batch_size = batch_size

        # Number of hidden states that are outputed by the LSTM
        self.hidden_dim = lstm_hidden_dim

        self.word_emb_dim = hps['sent_edim']

        # Specific Dependencies are all the labels of the syntactic
        # relationships
        self.specific_dep_size = hps['svdep']

        self.word_embeddings_SRL = nn.Embedding(
            num_embeddings=vocab_size, embedding_dim=hps['sent_edim'])

        # self.word_embeddings_DEP = nn.Embedding(vocab_size,
        #   hps['sent_edim']) # Not used?

        # Part of speech embeddings
        self.pos_embeddings = nn.Embedding(
            num_embeddings=self.pos_size, embedding_dim=hps['pos_edim'])

        # self.pos_embeddings_DEP = nn.Embedding(self.pos_size,
        #   hps['pos_edim']) # Not used?

        # Embeddings for the predicate lemma
        self.p_lemma_embeddings = nn.Embedding(
            num_embeddings=self.frameset_size, embedding_dim=hps['sent_edim'])

        # Embeddings for the dependencies
        self.dep_embeddings = nn.Embedding(
            num_embeddings=self.dep_size, embedding_dim=self.pos_size)

        # TODO What is the region?
        self.region_embeddings = nn.Embedding(2, 16)
        # self.lr_dep_embeddings = nn.Embedding(self.lr_dep_size,
        #     hps[])

        # Pre-trained word embeddings from conll file
        self.word_fixed_embeddings = nn.Embedding(vocab_size, hps['sent_edim'])

        # These pre-trained weitghts come in the
        # word_embeddings_proper.sskip.conll2009.txt file
        self.word_fixed_embeddings.weight.data.copy_(
            torch.from_numpy(hps['word_embeddings']))

        # self.word_fixed_embeddings_DEP = nn.Embedding(
        #     vocab_size, hps['sent_edim'])
        # self.word_fixed_embeddings_DEP.weight.data.copy_(
        #     torch.from_numpy(hps['word_embeddings']))

        # SRL embeddings
        # self.role_embeddings = nn.Embedding(
        #     self.tagset_size, role_embedding_dim)

        # Frame embeddings?? I assumed frame and lemma are the same
        # self.frame_embeddings = nn.Embedding(
        #     self.frameset_size, frame_embedding_dim)

        # This are the NNs used for getting the hidden value from the hidden
        # layers of the BiLSTM, but they are not used
        # self.hidden2tag = nn.Linear(4 * lstm_hidden_dim, 2 * lstm_hidden_dim)
        # self.MLP = nn.Linear(2 * lstm_hidden_dim, self.dep_size)
        # self.tag2hidden = nn.Linear(self.dep_size, self.pos_size)
        # self.hidden2tag_spe = nn.Linear(
        #     2 * lstm_hidden_dim, 2 * lstm_hidden_dim)
        # self.MLP_spe = nn.Linear(2 * lstm_hidden_dim, 4)
        # self.tag2hidden_spe = nn.Linear(4, self.pos_size)
        # # self.elmo_embeddings_0 = nn.Embedding(vocab_size, 1024)
        # # self.elmo_embeddings_0.weight.data.copy_(torch.from_numpy
        #   (hps['elmo_embeddings_0']))

        # # self.elmo_embeddings_1 = nn.Embedding(vocab_size, 1024)
        # # self.elmo_embeddings_1.weight.data.
        #   copy_(torch.from_numpy(hps['elmo_embeddings_1']))

        # self.elmo_emb_size = 200
        # self.elmo_mlp_word = nn.Sequential(
        #     nn.Linear(1024, self.elmo_emb_size), nn.ReLU())
        # self.elmo_word = nn.Parameter(torch.Tensor([0.5, 0.5]))
        # self.elmo_gamma_word = nn.Parameter(torch.ones(1))

        # self.elmo_mlp = nn.Sequential(
        #     nn.Linear(2 * lstm_hidden_dim, self.elmo_emb_size), nn.ReLU())
        # self.elmo_w = nn.Parameter(torch.Tensor([0.5, 0.5]))
        # self.elmo_gamma = nn.Parameter(torch.ones(1))

        self.SRL_input_dropout = nn.Dropout(p=0.3)
        # self.DEP_input_dropout = nn.Dropout(p=0.3)
        self.hidden_state_dropout = nn.Dropout(p=0.3)
        # self.word_dropout = nn.Dropout(p=0.0)
        # self.predicate_dropout = nn.Dropout(p=0.0)
        # self.label_dropout = nn.Dropout(p=0.5)
        # self.link_dropout = nn.Dropout(p=0.5)
        # self.use_dropout = nn.Dropout(p=0.2)

        # The LSTM takes word embeddings as inputs, and outputs hidden states
        # with dimensionality hidden_dim.
        # self.num_layers = 1
        # self.BiLSTM_0 = nn.LSTM(input_size=sent_embedding_dim_DEP,
        #                         hidden_size=lstm_hidden_dim,
        #                         batch_first=True,
        #                         bidirectional=True,
        #                         num_layers=self.num_layers)

        # print("Size of all_weights",
        #   (numpy.ndarray(self.BiLSTM_0.all_weights)).shape)
        # init.orthogonal_(self.BiLSTM_0.all_weights[0][0])
        # init.orthogonal_(self.BiLSTM_0.all_weights[0][1])
        # init.orthogonal_(self.BiLSTM_0.all_weights[1][0])
        # init.orthogonal_(self.BiLSTM_0.all_weights[1][1])

        # self.num_layers = 1
        # self.BiLSTM_1 = nn.LSTM(input_size=lstm_hidden_dim * 2,
        #                         hidden_size=lstm_hidden_dim,
        #                         batch_first=True,
        #                         bidirectional=True,
        #                         num_layers=self.num_layers)

        # init.orthogonal_(self.BiLSTM_1.all_weights[0][0])
        # init.orthogonal_(self.BiLSTM_1.all_weights[0][1])
        # init.orthogonal_(self.BiLSTM_1.all_weights[1][0])
        # init.orthogonal_(self.BiLSTM_1.all_weights[1][1])

        self.num_layers = 3
        self.BiLSTM_SRL = nn.LSTM(input_size=sent_embedding_dim_SRL,
                                  hidden_size=lstm_hidden_dim,
                                  batch_first=True,
                                  bidirectional=True,
                                  num_layers=self.num_layers)

        init.orthogonal_(self.BiLSTM_SRL.all_weights[0][0])
        init.orthogonal_(self.BiLSTM_SRL.all_weights[0][1])
        init.orthogonal_(self.BiLSTM_SRL.all_weights[1][0])
        init.orthogonal_(self.BiLSTM_SRL.all_weights[1][1])

        # non-linear map to role embedding
        # self.role_map = nn.Linear(
        #     in_features=role_embedding_dim * 2,
        #     out_features=self.hidden_dim * 4)

        # Is this the hidden value?
        self.VR_embedding = nn.Parameter(
            torch.from_numpy(np.zeros((1, sent_embedding_dim_SRL),
                                      dtype='float32')))

        self.map_dim = lstm_hidden_dim

        # self.mlp_word = MLP(
        #     in_features=2 * lstm_hidden_dim,
        #     out_features=self.map_dim ,
        #     activation=nn.LeakyReLU(0.1),
        #     dropout=0.33)
        # nn.init.orthogonal(self.mlp_word.weight)
        # self.mlp_predicate = MLP(
        #     in_features=2 * lstm_hidden_dim,
        #     out_features=self.map_dim ,
        #     activation=nn.LeakyReLU(0.1),
        #     dropout=0.33)
        # nn.init.orthogonal(self.mlp_predicate.weight)

        self.Non_Predicate_Proj = nn.Linear(
            2 * lstm_hidden_dim, lstm_hidden_dim)
        self.Predicate_Proj = nn.Linear(2 * lstm_hidden_dim, lstm_hidden_dim)
        self.W_R = nn.Parameter(torch.rand(
            self.map_dim + 1, self.tagset_size * (self.map_dim + 1)))

        # Init hidden state
        # self.hidden = self.init_hidden_spe()
        # self.hidden_2 = self.init_hidden_spe()
        # self.hidden_3 = self.init_hidden_spe()
        self.hidden_4 = self.init_hidden_share()

    def init_hidden_share(self):
        # Before we've done anything, we dont have any hidden state.
        # Refer to the Pytorch documentation to see exactly
        # why they have this dimensionality.
        # The axes semantics are (num_layers, minibatch_size, hidden_dim)
        # return (Variable(torch.zeros(1, self.batch_size, self.hidden_dim)),
        #        Variable(torch.zeros(1, self.batch_size, self.hidden_dim)))
        return (torch.zeros(3 * 2, self.batch_size, self.hidden_dim,
                            requires_grad=False).to(device),
                torch.zeros(3 * 2, self.batch_size, self.hidden_dim,
                            requires_grad=False).to(device))

    def init_hidden_spe(self):
        # Before we've done anything, we dont have any hidden state.
        # Refer to the Pytorch documentation to see exactly
        # why they have this dimensionality.
        # The axes semantics are (num_layers, minibatch_size, hidden_dim)
        # return (Variable(torch.zeros(1, self.batch_size, self.hidden_dim)),
        #        Variable(torch.zeros(1, self.batch_size, self.hidden_dim)))
        return (torch.zeros(1 * 2, self.batch_size, self.hidden_dim,
                            requires_grad=False).to(device),
                torch.zeros(1 * 2, self.batch_size, self.hidden_dim,
                            requires_grad=False).to(device))

    def forward(self, sentence, p_sentence, pos_tags, lengths, target_idx_in,
                region_marks, local_roles_voc, frames, local_roles_mask,
                sent_pred_lemmas_idx, dep_tags, dep_heads, targets,
                specific_dep_tags, specific_dep_relations,
                test=False):
        """

        """

        fixed_embeds = self.word_fixed_embeddings(p_sentence)
        fixed_embeds = fixed_embeds.view(
            self.batch_size, len(sentence[0]), self.word_emb_dim)

        # Create sentence predicate lemma embeddigns
        sent_pred_lemmas_embeds = self.p_lemma_embeddings(sent_pred_lemmas_idx)
        embeds_SRL = self.word_embeddings_SRL(sentence)
        embeds_SRL = embeds_SRL.view(
            self.batch_size, len(sentence[0]), self.word_emb_dim)
        pos_embeds = self.pos_embeddings(pos_tags)
        region_marks = self.region_embeddings(region_marks).view(
            self.batch_size, len(sentence[0]), 16)

        # This seems to be the word representation mentioned in section 2.2
        # x = x_re (embeds_SRL) o x_pe (fixed_embeds) o x_pos(pos_embeds) o
        # o x_le(sent_pred_lemmas_embeds)
        SRL_hidden_states = torch.cat(
            (embeds_SRL, fixed_embeds, sent_pred_lemmas_embeds, pos_embeds,
             region_marks), 2)
        add_zero = torch.zeros(
            (self.batch_size, 1, self.SRL_input_dim)).to(device)
        # Concatenating VR_embedding with x (SRL_hidden_states)
        # TODO Why is zero added?
        SRL_hidden_states_cat = torch.cat(
            (self.VR_embedding + add_zero, SRL_hidden_states), 1)
        # Applying dropout to the tensor
        SRL_hidden_states = self.SRL_input_dropout(SRL_hidden_states_cat)

        # SRL layer
        embeds_sort, lengths_sort, unsort_idx = self.sort_batch(
            SRL_hidden_states, lengths+1)

        # Packing the padded sequence to reduce computation
        embeds_sort = rnn.pack_padded_sequence(
            embeds_sort, lengths_sort.cpu().numpy(), batch_first=True)

        # hidden states [time_steps * batch_size * hidden_units]
        # Run the SRL BiLSTM
        hidden_states, self.hidden_4 = self.BiLSTM_SRL(
            embeds_sort, self.hidden_4)

        # it seems that hidden states is already batch first, we don't need
        # swap the dims
        # hidden_states = hidden_states.permute(1, 2, 0).contiguous().view(
        #   self.batch_size, -1, )

        # Unpacking the hidden_states
        hidden_states, lens = rnn.pad_packed_sequence(
            hidden_states, batch_first=True)

        # hidden_states = hidden_states.transpose(0, 1)

        # Unsort the hidden_states
        hidden_states = hidden_states[unsort_idx]
        hidden_states = self.hidden_state_dropout(hidden_states)

        # B * H
        hidden_states_3 = hidden_states

        # This next block appears only in the _VR file
        target_idx_in = list(target_idx_in)
        for i in range(len(target_idx_in)):
            target_idx_in[i] += 1
        target_idx_in = tuple(target_idx_in)

        predicate_embeds = F.relu(
            self.Predicate_Proj(
                hidden_states_3[np.arange(0,
                                          hidden_states_3.size()[0]),
                                target_idx_in]))

        hidden_states = F.relu(self.Non_Predicate_Proj(hidden_states))

        # T * B * H
        # added_embeds = torch.zeros(hidden_states_3.size()[1],
        #   hidden_states_3.size()[0], hidden_states_3.size()[2]).to(device)
        # predicate_embeds = added_embeds + predicate_embeds
        # B * T * H
        # predicate_embeds = predicate_embeds.transpose(0, 1)
        # print(hidden_states)
        # non-linear map and rectify the roles' embeddings
        # roles = Variable(torch.from_numpy(np.arange(0, self.tagset_size)))

        # B * roles
        # log(local_roles_voc)
        # log(frames)

        bias_one = torch.ones(
            (self.batch_size, len(sentence[0])+1, 1)).to(device)
        hidden_states_word = torch.cat((hidden_states, Variable(bias_one)), 2)

        bias_one = torch.ones((self.batch_size, 1)).to(device)
        hidden_states_predicate = torch.cat(
            (predicate_embeds, Variable(bias_one)), 1)

        left_part = torch.mm(hidden_states_word.view(
            self.batch_size * (len(sentence[0])+1), -1), self.W_R)
        left_part = left_part.view(
            self.batch_size, (len(sentence[0])+1) * self.tagset_size, -1)
        hidden_states_predicate = hidden_states_predicate.view(
            self.batch_size, -1, 1)
        tag_space = torch.bmm(left_part, hidden_states_predicate).view(
            (len(sentence[0])+1) * self.batch_size, -1)

        SRLprobs = F.softmax(tag_space, dim=1)

        # +++++++++++++++++++++++
        wrong_l_nums = 0.0
        all_l_nums = 1.0
        right_noNull_predict = 1.0
        noNull_predict = 1.0
        noNUll_truth = 1.0

        # +++++++++++++++++++++++
        # wrong_l_nums_spe = 0.0
        # all_l_nums_spe = 0.0

        right_noNull_predict_spe = 1.0
        noNull_predict_spe = 1.0
        noNUll_truth_spe = 1.0
        targets = targets.view(-1)
        loss_function = nn.CrossEntropyLoss(ignore_index=0)

        SRLloss = loss_function(tag_space, targets)

        return SRLloss, 0, 0, 0, SRLprobs, wrong_l_nums, all_l_nums,\
            wrong_l_nums, all_l_nums, right_noNull_predict, noNull_predict,\
            noNUll_truth, right_noNull_predict_spe, noNull_predict_spe,\
            noNUll_truth_spe

    @staticmethod
    def sort_batch(tensor, lengths):
        """
        Static method for sorting a batch of tensors based on lenghts

        Returns the sorted tensor, their respective sorted lenghts and a list
        of indexes thst can be used to reverse this sorting
        """

        lengths = torch.from_numpy(np.asarray(lengths))
        lengths_sorted, sorted_idx = lengths.sort(dim=0, descending=True)
        tensor_sorted = tensor[sorted_idx]
        _, unsort_idx = sorted_idx.sort()
        return tensor_sorted, lengths_sorted, unsort_idx
