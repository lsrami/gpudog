import os
import argparse
import logging
import torch
import torch.nn as nn
import torch.optim as optim
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torchvision.models import resnet34, resnet50, resnet101, resnet152

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 设置随机种子
torch.manual_seed(0)


# 定义随机数据集
class RandomDataset(torch.utils.data.Dataset):
    def __init__(self, size, length):
        self.len = length
        self.data = torch.randn(length, 3, 224, 224)
        self.labels = torch.randint(0, 1000, (length,))

    def __getitem__(self, index):
        return self.data[index], self.labels[index]

    def __len__(self):
        return self.len


# 设置分布式训练的参数
def setup():
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    rank = int(os.environ.get("RANK", 0))
    world_size = int(os.environ["WORLD_SIZE"])
    torch.cuda.set_device(local_rank)
    dist.init_process_group(backend="nccl")
    return rank, world_size


def cleanup():
    dist.destroy_process_group()


# 训练函数
def train(args):
    rank, world_size = setup()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)

    # 创建数据集和数据加载器
    dataset = RandomDataset(size=3 * 224 * 224, length=args.data_size)
    train_sampler = torch.utils.data.distributed.DistributedSampler(
        dataset, num_replicas=world_size, rank=rank
    )
    train_loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=args.batch_size,
        sampler=train_sampler,
        num_workers=args.num_workers,
    )

    # 选择模型
    if args.model == "resnet34":
        model = resnet34().to(device)
    elif args.model == "resnet50":
        model = resnet50().to(device)
    elif args.model == "resnet101":
        model = resnet101().to(device)
    elif args.model == "resnet152":
        model = resnet152().to(device)
    else:
        raise ValueError(f"Unsupported model: {args.model}")

    ddp_model = DDP(model)
    criterion = nn.CrossEntropyLoss().to(device)
    optimizer = optim.SGD(ddp_model.parameters(), lr=0.01)

    # 训练模型
    ddp_model.train()
    epoch = 0
    while True:
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = ddp_model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
            if batch_idx % 100 == 0 and args.print_log:
                logging.info(
                    f"Rank {rank}, Epoch {epoch}, Batch {batch_idx}, Loss {loss.item()}"
                )
        epoch += 1
        if not args.continuous and epoch >= args.epochs:
            break

    cleanup()


# 主函数
def main():
    parser = argparse.ArgumentParser(
        description="Distributed Data Parallel Training Example"
    )
    parser.add_argument(
        "-b",
        "--batch_size",
        type=int,
        default=32,
        help="input batch size for training (default: 32)",
    )
    parser.add_argument(
        "-d",
        "--data_size",
        type=int,
        default=1000,
        help="size of the dataset (default: 1000)",
    )
    parser.add_argument(
        "-e",
        "--epochs",
        type=int,
        default=100,
        help="number of epochs to train (default: 5)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="resnet101",
        choices=["resnet34", "resnet50", "resnet101", "resnet152"],
        help="model to use for training (default: resnet34)",
    )
    parser.add_argument(
        "-c", "--continuous", action="store_true", help="keep training indefinitely"
    )
    parser.add_argument(
        "-n",
        "--num_workers",
        type=int,
        default=4,
        help="number of worker processes to use for data loading",
    )
    parser.add_argument("-p", "--print_log", action="store_true", help="print log")
    args = parser.parse_args()

    train(args)


if __name__ == "__main__":
    # 使用方式：
    # CUDA_VISIBLE_DEVICES="0" torchrun --standalone --nproc_per_node=1 train_ddp_model.py -c -b 48 -d 10000 -m resnet152
    main()
