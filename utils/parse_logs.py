from collections import defaultdict


def parse_configs(fn):

    config, others = dict(), dict()

    with open(fn, 'r') as f:

        line = f.readline().strip()
        while line:
            key, value = line.split(' = ')
            config[key] = value
            line = f.readline().strip()
        
        line = f.readline().strip()
        while line:
            key, value = line.split(' = ')
            others[key] = value
            line = f.readline().strip()

    return config, others


def parse_metrics(fn):

    results = {
        'Training': defaultdict(list),
        'Validation': defaultdict(list),
        'Testing': defaultdict(list),
    }

    with open(fn, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if 'Epoch' in line:
                epoch = int(line.rsplit(' ', maxsplit=1)[1])
            elif any((key in line for key in results.keys())):
                split, metrics = line.split(': ')
                metrics = metrics.strip().split(', ')
                metrics = map(lambda x: x.split(' = '), metrics)
                results[split]['Epoch'].append(epoch)
                for metric, value in metrics:
                    results[split][metric].append(float(value))

    return dict(results['Training']), dict(results['Validation']), dict(results['Testing'])