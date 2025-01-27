from argparse import Namespace
import os
import random
from tqdm import tqdm
import pickle

import torch
from torch_geometric.datasets import ZINC as ZINCTorch

from dataset.constants import root, batch_size
from dataset.base import Inductive
from dataset.utils import CustomDataset, create_loaders


root = f'{root}/Synthetics'


class Transform_SD:

    def __init__(self, root, distance, split):

        self.node_pairs = self.save_node_pairs(root, distance, split)

    def save_node_pairs(self, root, distance, split):

        fn = f'{root}/node-pairs-sd/distance={distance}/{split}.pkl'
        if os.path.isfile(fn): 
            with open(fn, 'rb') as f:
                node_pairs = pickle.load(f)
            return node_pairs
        
        from sensitivity.utils import compute_shortest_distances

        dataset = ZINCTorch(root=root, subset=True, split=split)
        node_pairs = list()

        # For each molecule, sample a node pair separated by `distance` hops
        for datum in tqdm(dataset):
            shortest_distances = compute_shortest_distances(datum.edge_index)   # Tensor(|E|x|E|)
            choices = torch.where(shortest_distances == distance)               # Tuple[row indices, column indices]
            try:
                sample = random.randint(0, choices[0].size(0)-1)                # Int in range [0, num_mathces-1]
                node_pair = list(map(lambda x: x[sample].item(), choices))      # List[row, column]
            except ValueError:
                node_pair = None                                                # No pair separated by `distance` hops
            node_pairs.append(node_pair)

        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, 'wb') as f:
            pickle.dump(node_pairs, f, protocol=pickle.HIGHEST_PROTOCOL)

        return node_pairs

    def __call__(self, index, datum):

        datum.x = torch.zeros_like(datum.x, dtype=torch.float)  # Set all node features to 0
        node_pair = self.node_pairs[index]                      # Get sampled node pair separated by `distance` hops
        if node_pair is not None:
            features = torch.rand(len(node_pair))               # Sample random features
            datum.x[node_pair, :] = features.unsqueeze(1)       # Set features for the pair of nodes
            datum.y = torch.tanh(features.sum())                # Set graph-level label
            return datum
        else:
            return None


class SyntheticZINC_SD(Inductive):

    def __init__(self, device: torch.device, others: Namespace, **kwargs):

        assert others.pooler == 'max', f"For SyntheticZINC, the `pooler` argument must be 'max'."

        zinc_root = f'{root}/ZINC'
        datasets, sizes = list(), (None, None, None)
        for split, size in zip(('train', 'val', 'test'), sizes):
            # Save node pairs separated by `distance` hops
            transform = Transform_SD(zinc_root, int(others.distance), split)
            dataset = ZINCTorch(root=zinc_root, subset=True, split=split)
            dataset = enumerate(dataset)
            if size is not None:
                random.shuffle(dataset)
                dataset = dataset[:size]
            # Create node-level features, and graph-level labels
            data_list = [transform(index, datum) for index, datum in dataset]
            # Filter out molecules with no two nodes separated by `distance` hops
            data_list = [datum.to(device) for datum in data_list if datum is not None]
            datasets.append(CustomDataset(data_list))
        train, val, test = datasets
        
        self.train_loader, self.val_loader, self.test_loader = create_loaders(
            (train, val, test),
            batch_size=batch_size,
            shuffle=True
        )

        self.task_name = 'graph-r'
        self.num_features = 1
        self.num_classes = 1
        super(SyntheticZINC_SD, self).__init__(self.task_name, device)