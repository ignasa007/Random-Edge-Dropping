from tqdm import tqdm
import warnings; warnings.filterwarnings('ignore')

import torch
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau

from dataset import get_dataset, BaseDataset
from model import Model
from utils.config import parse_arguments
from utils.logger import Logger
from utils.format import format_task_name, FormatEpoch


config, others = parse_arguments(return_others=True)
DEVICE = torch.device(f'cuda:{config.device_index}' if torch.cuda.is_available() and config.device_index is not None else 'cpu')

dataset: BaseDataset = get_dataset(config.dataset, config=config, others=others, device=DEVICE)
others.input_dim = dataset.num_features
others.output_dim = dataset.output_dim
others.task_name = format_task_name.get(dataset.task_name.lower())

model = Model(config, others).to(device=DEVICE)
optimizer = Adam(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
scheduling_metric = 'Accuracy' if others.task_name.endswith('-c') else 'Mean Absolute Error'
scheduler = ReduceLROnPlateau(optimizer, patience=10//config.test_every, mode=('max' if others.task_name.endswith('-c') else 'min'))

logger = Logger(config, others)
format_epoch = FormatEpoch(config.n_epochs)

for epoch in tqdm(range(1, config.n_epochs+1)):

    logger.log(f'Epoch {format_epoch(epoch)}')
    train_metrics = dataset.train(model, optimizer)
    logger.log_metrics(train_metrics, prefix='\tTraining:'.ljust(13), with_time=False, print_text=False)

    if epoch == config.n_epochs or config.test_every > 0 and epoch % config.test_every == 0:
        val_metrics, test_metrics = dataset.eval(model)
        scheduler.step(val_metrics[1][1])   # corresponds to Accuracy for classification and MAE for regression
        logger.log_metrics(val_metrics, prefix='\tValidation:'.ljust(13), with_time=False, print_text=False)
        logger.log_metrics(test_metrics, prefix='\tTesting:'.ljust(13), with_time=False, print_text=False)

    if isinstance(config.save_every, int) and (config.save_every > 0 and epoch % config.save_every == 0 or config.save_every == -1 and epoch == config.n_epochs):
        ckpt_fn = f'{logger.exp_dir}/ckpt-{format_epoch(epoch)}.pt'
        logger.log(f'\tSaving model at {ckpt_fn}.', with_time=False, print_text=True)
        torch.save(model.state_dict(), ckpt_fn) 

    logger.log('', with_time=False, print_text=False)