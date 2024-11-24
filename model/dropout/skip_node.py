import torch
from model.dropout.base import BaseDropout


class SkipNode(BaseDropout):

    def __init__(self, dropout_prob=0.5):

        super(SkipNode, self).__init__(dropout_prob)
    
    def apply_feature_mat(self, x, training=True):

        if not training or self.dropout_prob == 0.0:
            return x

        new_x = x.clone()
        if hasattr(self, 'old_x') and new_x.size(1) == self.old_x.size(1):
            node_mask = torch.rand(x.size(0)) < self.dropout_prob
            new_x[node_mask] = self.old_x[node_mask]
        self.old_x = new_x

        return new_x

    def apply_adj_mat(self, edge_index, edge_attr=None, training=True):
        
        return super(SkipNode, self).apply_adj_mat(edge_index, edge_attr, training)
    
    def apply_message_mat(self, messages, training=True):

        return super(SkipNode, self).apply_message_mat(messages, training)