from argparse import Namespace
from typing import Tuple, Dict
import os
import random
from tqdm import tqdm
import pickle

import torch
from torch_geometric.data import InMemoryDataset
from torch_geometric.datasets import ZINC as ZINCTorch
from torch.optim import Optimizer

from dataset.constants import root, batch_size
from dataset.base import BaseDataset
from dataset.utils import create_loaders
from model import Model


root = f'{root}/Synthetics'


class Tranform:

    def __init__(self, split, alpha, root):

        fn = self.get_node_pairs_fn(split, alpha, root)
        if not os.path.isfile(fn):
            self.save_node_pairs(split, alpha, root)
        with open(fn, 'rb') as f:
            self.node_pairs = pickle.load(f)

        self.index = 0

    def get_node_pairs_fn(self, split, alpha, root):

        return f'{root}/node-pairs-ct/alpha={alpha}/{split}.pkl'

    def save_node_pairs(self, split, alpha, root):

        from sensitivity.utils import compute_commute_times

        dataset = ZINCTorch(root=root, subset=True, split=split)
        node_pairs = list()

        for molecule in tqdm(dataset):
            commute_times = compute_commute_times(molecule.edge_index)
            quantile = torch.quantile(commute_times.flatten(), alpha, interpolation='nearest')
            choices = torch.where(commute_times == quantile)
            sample = random.randint(0, choices[0].size(0)-1)
            node_pair = list(map(lambda x: x[sample].item(), choices))
            node_pairs.append(node_pair)

        fn = self.get_node_pairs_fn(split, alpha, root)
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, 'wb') as f:
            pickle.dump(node_pairs, f, protocol=pickle.HIGHEST_PROTOCOL)

    def __call__(self, data):

        data.x = torch.zeros_like(data.x, dtype=torch.float)
        node_pair = self.node_pairs[self.index]
        features = torch.rand(len(node_pair))
        data.x[node_pair, :] = features.unsqueeze(1)
        data.y = torch.tanh(features.sum())
        self.index += 1
        
        return data


class CustomDataset(InMemoryDataset):

    def __init__(self, data_list):
        self.data_list = data_list
        super(CustomDataset, self).__init__(root='', transform=None, pre_transform=None)

    def len(self):
        return len(self.data_list)

    def get(self, idx):
        return self.data_list[idx]


class SyntheticZINC_CT(BaseDataset):

    def __init__(self, device: torch.device, others: Namespace, **kwargs):

        zinc_root = f'{root}/ZINC'
        datasets = list()
        for split in ('train', 'val', 'test'):
            dataset = ZINCTorch(root=zinc_root, subset=True, split=split)
            transform = Tranform(split, float(others.alpha), zinc_root)
            data_list = [transform(data) for data in dataset]
            datasets.append(CustomDataset(data_list))   # .to(device)
        train, val, test = datasets
        
        self.train_loader, self.val_loader, self.test_loader = create_loaders(
            (train, val, test),
            batch_size=batch_size,
            shuffle=True
        )

        self.task_name = 'graph-r'
        self.num_features = 1
        self.num_classes = 1
        super(SyntheticZINC_CT, self).__init__(self.task_name)

    def train(self, model: Model, optimizer: Optimizer) -> Dict[str, float]:

        model.train()

        for batch in self.train_loader:
            optimizer.zero_grad()
            out = model(batch.x, batch.edge_index, batch.batch)
            train_loss = self.compute_loss(out, batch.y)
            train_loss.backward()
            optimizer.step()

        train_metrics = self.compute_metrics()
        return train_metrics
    
    @torch.no_grad()
    def eval(self, model: Model) -> Tuple[Dict[str, float], Dict[str, float]]:

        model.eval()
        
        for batch in self.val_loader:
            out = model(batch.x, batch.edge_index, batch.batch)
            self.compute_loss(out, batch.y)
        val_metrics = self.compute_metrics()

        for batch in self.test_loader:
            out = model(batch.x, batch.edge_index, batch.batch)
            self.compute_loss(out, batch.y)
        test_metrics = self.compute_metrics()

        return val_metrics, test_metrics