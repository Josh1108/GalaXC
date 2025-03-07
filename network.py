import nmslib
from typing import Callable
import logging
import torch
import numpy as np
import math
from scipy.sparse import csr_matrix, lil_matrix

import torch.nn as nn
from torch.nn.parameter import Parameter
import torch.nn.functional as F
import torch.utils.data
import logging

class MeanAggregator(nn.Module):
    """Aggregates a node's embeddings using mean of neighbors' embeddings."""

    def __init__(self, features: Callable[[torch.Tensor], torch.Tensor]):
        super(MeanAggregator, self).__init__()
        self.features = features

    def forward(self, neighs: torch.Tensor, node_count: int, device):
        neigh_feats = self.features(neighs).to(device)

        nb_count = int(neigh_feats.shape[0] / node_count)
        fv_by_node = neigh_feats.view(
            node_count, nb_count, neigh_feats.shape[-1])
        return fv_by_node.mean(1)


class SumAggregator(nn.Module):
    """Aggregates a node's embeddings using mean of neighbors' embeddings."""

    def __init__(self, features: Callable[[torch.Tensor], torch.Tensor]):
        super(SumAggregator, self).__init__()
        self.features = features

    def forward(self, neighs: torch.Tensor, node_count: int, device):
        neigh_feats = self.features(neighs).to(device)

        nb_count = int(neigh_feats.shape[0] / node_count)
        fv_by_node = neigh_feats.view(
            node_count, nb_count, neigh_feats.shape[-1])
        return fv_by_node.sum(1)


class SaintEncoder(nn.Module):
    """Encode a node's using 'convolutional' GraphSaint approach."""

    def __init__(
        self,
        features,
        query_func,
        device_name,
        feature_dim: int,
        aggregator: nn.Module,
        num_sample: int,
        intermediate_dim: int,
        embed_dim: int = 300,
        activation_fn: callable = F.relu,
        base_model=None,
    ):
        super(SaintEncoder, self).__init__()

        self.device_name = device_name
        if base_model:
            self.base_model = base_model
        self.features = features
        if query_func is None:
            self.query_func = self.query_feature
        else:
            self.query_func = query_func
        self.aggregator = aggregator
        self.num_sample = num_sample
        self.activation_fn = activation_fn
        self.weight_1 = nn.Parameter(
            torch.FloatTensor(
                embed_dim // 2,
                intermediate_dim))
        self.weight_2 = nn.Parameter(
            torch.FloatTensor(
                embed_dim // 2,
                intermediate_dim))
        nn.init.xavier_uniform_(self.weight_1)
        nn.init.xavier_uniform_(self.weight_2)

    def query(
        self,
        nodes: np.array,
        graph
    ):
        context = {}
        neigh_nodes = graph.sample_neighbors(nodes, self.num_sample)[
            0
        ].flatten()

        context["node_feats"] = self.query_func(
            nodes, graph
        )

        context["neighbor_feats"] = self.query_func(
            neigh_nodes, graph
        )
        context["node_count"] = len(nodes)
        return context

    def query_feature(
        self,
        nodes: np.array,
        graph
    ):
        features = graph.node_features(nodes)
        return features

    def forward(self, context: dict):
        """Generate embeddings for a batch of nodes."""
        neigh_feats = self.aggregator.forward(
            context["neighbor_feats"], context["node_count"], self.device_name
        )
        self_feats = self.features(context["node_feats"]).to(self.device_name)

        # print (neigh_feats.shape, self_feats.shape)
        combined = torch.cat(
            [self.weight_1.mm(self_feats.t()), self.weight_2.mm(neigh_feats.t())], dim=0)
        combined = self.activation_fn(combined)

        return combined


class SageEncoder(nn.Module):
    """Encode a node's using 'convolutional' GraphSage approach."""

    def __init__(
        self,
        features,
        query_func,
        device_name,
        feature_dim: int,
        aggregator: nn.Module,
        num_sample: int,
        intermediate_dim: int,
        embed_dim: int = 300,
        activation_fn: callable = F.relu,
        base_model=None,
    ):
        super(SageEncoder, self).__init__()

        self.device_name = device_name
        if base_model:
            self.base_model = base_model
        self.features = features
        if query_func is None:
            self.query_func = self.query_feature
        else:
            self.query_func = query_func
        self.aggregator = aggregator
        self.num_sample = num_sample
        self.activation_fn = activation_fn
        self.weight = nn.Parameter(
            torch.FloatTensor(
                embed_dim,
                2 * intermediate_dim))
        nn.init.xavier_uniform_(self.weight)

    def query(
        self,
        nodes: np.array,
        graph,
    ):
        context = {}
        print("number of nodes",nodes)
        print("num of samples",self.num_sample)
        neigh_nodes = graph.sample_neighbors(nodes, self.num_sample)[
            0
        ].flatten()
        print("neighboring nodes",neigh_nodes)
        context["node_feats"] = self.query_func(
            nodes, graph
        )

        context["neighbor_feats"] = self.query_func(
            neigh_nodes, graph
        )
        context["node_count"] = len(nodes)
        return context

    def query_feature(
        self,
        nodes: np.array,
        graph,
    ):
        features = graph.node_features(
            nodes
        )
        return features

    def forward(self, context: dict):
        """Generate embeddings for a batch of nodes."""
        neigh_feats = self.aggregator.forward(
            context["neighbor_feats"], context["node_count"], self.device_name
        )
        self_feats = self.features(context["node_feats"]).to(self.device_name)
        combined = torch.cat([self_feats, neigh_feats], dim=1)
        combined = self.activation_fn(self.weight.mm(combined.t()))

        return combined


class GINEncoder(nn.Module):
    """Encode a node's using 'convolutional' GIN approach."""

    def __init__(
        self,
        features,
        query_func,
        device_name,
        feature_dim: int,
        aggregator: nn.Module,
        num_sample: int,
        intermediate_dim: int,
        embed_dim: int = 300,
        activation_fn: callable = F.relu,
        base_model=None,
    ):
        super(GINEncoder, self).__init__()

        self.device_name = device_name
        if base_model:
            self.base_model = base_model
        self.features = features
        if query_func is None:
            self.query_func = self.query_feature
        else:
            self.query_func = query_func
        self.aggregator = aggregator
        self.num_sample = num_sample
        self.activation_fn = activation_fn
        self.eps = nn.Parameter(torch.rand(1))

    def query(
        self,
        nodes: np.array,
        graph
    ):
        context = {}
        neigh_nodes = graph.sample_neighbors(nodes, self.num_sample)[
            0
        ].flatten() # We get sampled nodes. Repeat nodes if number of nodes<sample

        context["node_feats"] = self.query_func(
            nodes, graph
        )

        context["neighbor_feats"] = self.query_func(
            neigh_nodes, graph
        )

        context["node_count"] = len(nodes)
        return context

    def query_feature(
        self,
        nodes: np.array,
        graph,
    ):
        features = graph.node_features(
            nodes
        )
        return features

    def forward(self, context: dict):
        """Generate embeddings for a batch of nodes."""

        neigh_feats = self.aggregator.forward(
            context["neighbor_feats"], context["node_count"], self.device_name
        )
        self_feats = self.features(context["node_feats"]).to(self.device_name)

        combined = torch.add(neigh_feats, (1.0 + self.eps) * self_feats)
        return combined.t()


class LinearChunk(nn.Module):
    """One part for distributed fully connected layer"""

    def __init__(self, input_size, output_size, device_embeddings, bias=True):
        super(LinearChunk, self).__init__()
        self.device_embeddings = device_embeddings
        self.input_size = input_size
        self.output_size = output_size
        self.weight = Parameter(
            torch.Tensor(
                self.output_size,
                self.input_size))
        if bias:
            self.bias = Parameter(torch.Tensor(self.output_size, ))
        else:
            self.register_parameter('bias', None)
        self.attention_weights = Parameter(torch.Tensor(self.output_size, 3))

        self.sparse = False
        self.reset_parameters()
        self.act = torch.nn.Softmax(dim=1)

    def forward(self, input):
        if(input[1] is None):
            w = self.weight.unsqueeze(
                1) * (self.act(self.attention_weights).unsqueeze(2))
            x = input[0].mm(w.view((-1, input[0].shape[-1])).t()
                            ) + self.bias.view(-1)
            return x
        else:
            if len(input[1].shape) == 1:
                # 350K X 1 X 300                                  350K X 3 X 1
                # .permute(0, 2, 1).reshape(-1, 900)
                w = (self.weight[input[1]].unsqueeze(
                    1)) * (self.act(self.attention_weights[input[1]])).unsqueeze(2)
                x = input[0].mm(w.view((-1, input[0].shape[-1])).t()
                                ) + self.bias[input[1]].view(-1)
                return x
            elif len(input[1].shape) == 2:
                short_weights = F.embedding(input[1].to(self.device_embeddings),
                                            self.weight,
                                            sparse=self.sparse).view(input[1].shape[0] * input[1].shape[1], -1)

                short_bias = F.embedding(input[1].to(self.device_embeddings),
                                         self.bias.view(-1, 1),
                                         sparse=self.sparse)

                short_att = F.embedding(input[1].to(self.device_embeddings),
                                        self.attention_weights,
                                        sparse=self.sparse).view(input[1].shape[0] * input[1].shape[1], -1)

                w = short_weights.unsqueeze(
                    1) * (self.act(short_att).unsqueeze(2))
                x = input[0].unsqueeze(1).repeat(1,
                                                 input[1].shape[1],
                                                 1) * w.view((input[1].shape[0],
                                                              input[1].shape[1],
                                                              input[0].shape[-1]))

                x = x.sum(axis=2) + short_bias.squeeze()
                return x

    def move_to_devices(self):
        super().to(self.device_embeddings)

    def reset_parameters(self):
        nn.init.normal_(self.attention_weights)
        stdv = 1. / math.sqrt(self.weight.size(1))
        self.weight.data.uniform_(-stdv, stdv)
        if self.bias is not None:
            self.bias.data.uniform_(-stdv, stdv)


class LinearDistributed(nn.Module):
    """Distributed fully connected layer"""

    def __init__(self, input_size, output_size, device_embeddings):
        super(LinearDistributed, self).__init__()
        self.num_partitions = len(device_embeddings)
        self.device_embeddings = device_embeddings
        self.input_size = input_size
        self.output_size = output_size

        self.partition_size = math.ceil(output_size / self.num_partitions)
        self.partition_indices = []
        for i in range(self.num_partitions):
            _start = i * self.partition_size
            _end = min(_start + self.partition_size, output_size)
            self.partition_indices.append((_start, _end))

        print(self.partition_indices)

        self.classifiers = nn.ModuleList()
        for i in range(len(self.device_embeddings)):
            output_size = self.partition_indices[i][1] - \
                self.partition_indices[i][0]
            self.classifiers.append(
                LinearChunk(
                    input_size,
                    output_size,
                    self.device_embeddings[i]))

        self.reset_parameters()

    def forward(self, input):
        if(input[1] is None):
            total_x = []
            for i in range(len(self.device_embeddings)):
                embed = input[0].to(self.device_embeddings[i])
                x = self.classifiers[i]((embed, None))
                total_x.append(x.to(self.device_embeddings[0]))
            total_x = torch.cat(total_x, dim=1)
            return total_x
        else:
            if len(input[1].shape) == 1:
                total_x = []
                for i in range(len(self.device_embeddings)):
                    _start = self.partition_indices[i][0]
                    _end = self.partition_indices[i][1]
                    embed = input[0].to(self.device_embeddings[i])
                    indices = input[1][_start: _end]

                    x = self.classifiers[i]((embed, indices))
                    total_x.append(x.to(self.device_embeddings[0]))
                total_x = torch.cat(total_x, dim=1)
                return total_x
            elif len(input[1].shape) == 2:
                partition_length = input[1].shape[1] // len(
                    self.partition_indices)
                total_x = []
                for i in range(len(self.device_embeddings)):
                    embed = input[0].to(self.device_embeddings[i])
                    short = input[1][:, i *
                                     partition_length: (i + 1) * partition_length]
                    x = self.classifiers[i]((embed, short))
                    total_x.append(x.to(self.device_embeddings[0]))
                total_x = torch.cat(total_x, dim=1)
                return total_x

    def move_to_devices(self):
        print("Moving to different devices...")
        for i in range(len(self.device_embeddings)):
            self.classifiers[i].move_to_devices()

    def reset_parameters(self):
        for i in range(len(self.device_embeddings)):
            self.classifiers[i].reset_parameters()


class Residual(nn.Module):
    """Residual layer implementation"""

    def __init__(self, input_size, output_size, dropout, init='eye'):
        super(Residual, self).__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.init = init
        self.dropout = dropout
        self.padding_size = self.output_size - self.input_size
        self.hidden_layer = nn.Sequential(nn.Linear(self.input_size,
                                          self.output_size),
                                          nn.BatchNorm1d(self.output_size),
                                          nn.ReLU(),
                                          nn.Dropout(self.dropout))
        self.initialize(self.init)

    def forward(self, embed):
        temp = F.pad(embed, (0, self.padding_size), 'constant', 0)
        embed = self.hidden_layer(embed) + temp
        return embed

    def initialize(self, init_type):
        if init_type == 'random':
            nn.init.xavier_uniform_(
                self.hidden_layer[0].weight,
                gain=nn.init.calculate_gain('relu'))
            nn.init.constant_(self.hidden_layer[0].bias, 0.0)
        else:
            print("Using eye to initialize!")
            nn.init.eye_(self.hidden_layer[0].weight)
            nn.init.constant_(self.hidden_layer[0].bias, 0.0)


class GalaXCBase(nn.Module):
    """Base class for GalaXC"""

    def __init__(self, num_labels, hidden_dims, device_names,
                 feature_dim: int,
                 fanouts: list,
                 graph,
                 embed_dim: int,
                 dropout=0.5, num_clf_partitions=1, padding_idx=0):
        super(GalaXCBase, self).__init__()

        # only 1 or 2 hops are allowed.
        assert len(fanouts) in [1, 2, 3]

        self.graph = graph
        self.fanouts = fanouts
        self.num_labels = num_labels
        self.feature_dim = feature_dim
        self.hidden_dims = hidden_dims
        self.embed_dim = embed_dim
        self.device_names = device_names
        self.device_name = self.device_names[0]
        self.device_embeddings = torch.device(self.device_name)

        self.dropout = dropout
        self.padding_idx = padding_idx
        self.num_clf_partitions = num_clf_partitions

        self._construct_embeddings()
        self.transform1 = self._construct_transform()
        self.transform2 = self._construct_transform()
        self.transform3 = self._construct_transform()
        self.classifier = self._construct_classifier()

    def query(self, context: dict):
        context["encoder"] = self.third_layer_enc.query(
            context["inputs"],
            self.graph
        )

    def _construct_transform(self):
        return nn.Sequential(nn.ReLU(), nn.Dropout(self.dropout), Residual(
            self.embed_dim, self.hidden_dims, self.dropout))

    def _construct_classifier(self):
        return LinearDistributed(
            self.hidden_dims, self.num_labels, self.device_names)

    def _construct_embeddings(self):
        """
        Some calculation is repeated. Optimizing doesn't help much, keeping for simplicity.
        """
        def feature_func(features): return features.squeeze(0)

        self.first_layer_enc = GINEncoder(
            features=feature_func,
            query_func=None,
            feature_dim=self.feature_dim,
            intermediate_dim=self.feature_dim,
            aggregator=SumAggregator(feature_func),
            embed_dim=self.embed_dim,
            num_sample=self.fanouts[0],
            device_name=self.device_name
        )

        self.second_layer_enc = GINEncoder(
            features=lambda context: self.first_layer_enc(context).t(),
            query_func=self.first_layer_enc.query,
            feature_dim=self.feature_dim,
            intermediate_dim=self.embed_dim,
            aggregator=SumAggregator(
                lambda context: self.first_layer_enc(context).t()
            ),
            embed_dim=self.embed_dim,
            num_sample=self.fanouts[1],
            base_model=self.first_layer_enc,
            device_name=self.device_name
        )

        self.third_layer_enc = GINEncoder(
            features=lambda context: self.second_layer_enc(context).t(),
            query_func=self.second_layer_enc.query,
            feature_dim=self.feature_dim,
            intermediate_dim=self.embed_dim,
            aggregator=SumAggregator(
                lambda context: self.second_layer_enc(context).t()
            ),
            embed_dim=self.embed_dim,
            num_sample=self.fanouts[2],
            base_model=self.second_layer_enc,
            device_name=self.device_name
        )

    def encode(self, context):
        embed3 = self.third_layer_enc(context["encoder"])
        embed2 = self.second_layer_enc(context["encoder"]["node_feats"])
        embed1 = self.first_layer_enc(
            context["encoder"]["node_feats"]["node_feats"])

        embed = torch.cat(
            (self.transform1(
                embed1.t()), self.transform2(
                embed2.t()), self.transform3(
                embed3.t())), dim=1)
        return embed

    def encode_graph_embedding(self, context):
        embed = self.embeddings(context["encoder"], self.device_embeddings)
        return embed.t()

    def forward(self, batch_data, only_head=True):
        encoded = self.encode(batch_data)

        return self.classifier((encoded, batch_data["label_ids"]))

    def initialize_embeddings(self, word_embeddings):
        self.embeddings.weight.data.copy_(torch.from_numpy(word_embeddings))

    def initialize_classifier(self, clf_weights):
        self.classifier.weight.data.copy_(torch.from_numpy(clf_weights[:, -1]))
        self.classifier.bias.data.copy_(
            torch.from_numpy(clf_weights[:, -1]).view(-1, 1))

    def get_clf_weights(self):
        return self.classifier.get_weights()

    def move_to_devices(self):
        self.third_layer_enc.to(self.device_embeddings)
        self.transform1.to(self.device_embeddings)
        self.transform2.to(self.device_embeddings)
        self.transform3.to(self.device_embeddings)
        self.classifier.move_to_devices()

    @property
    def num_trainable_params(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    @property
    def model_size(self):
        return self.num_trainable_params * 4 / math.pow(2, 20)


class HNSW(object):
    """HNSW ANNS implementation"""

    def __init__(self, M, efC, efS, num_threads):
        self.index = nmslib.init(method='hnsw', space='cosinesimil')
        self.M = M
        self.num_threads = num_threads
        self.efC = efC
        self.efS = efS

    def fit(self, data, print_progress=True):
        self.index.addDataPointBatch(data)
        self.index.createIndex(
            {'M': self.M,
             'indexThreadQty': self.num_threads,
             'efConstruction': self.efC},
            print_progress=print_progress
        )

    def _filter(self, output, num_search):
        indices = np.zeros((len(output), num_search), dtype=np.int32)
        distances = np.zeros((len(output), num_search), dtype=np.float32)
        for idx, item in enumerate(output):
            indices[idx] = item[0]
            distances[idx] = item[1]
        return indices, distances

    def predict(self, data, num_search):
        self.index.setQueryTimeParams({'efSearch': self.efS})
        output = self.index.knnQueryBatch(
            data, k=num_search, num_threads=self.num_threads
        )
        indices, distances = self._filter(output, num_search)
        return indices, distances

    def save(self, fname):
        nmslib.saveIndex(self.index, fname)
