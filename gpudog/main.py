import requests
from .gpustat import GPUStatCollection
from apscheduler.schedulers.blocking import BlockingScheduler
import json
import argparse
import os
import re
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="检查GPU是否可用并通过微信通知")
    parser.add_argument(
        "-m",
        "--cuda-memory",
        type=float,
        default=5000,
        help="每个设备所需的CUDA内存（MB）",
    )
    parser.add_argument(
        "-d",
        "--device-list",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3, 4, 5, 6, 7],
        help="要使用的GPU ID列表",
    )
    parser.add_argument(
        "-f",
        "--check-freq",
        type=str,
        default="10m",
        help="检查频率，例如10m（10分钟）",
    )
    parser.add_argument(
        "-r",
        "--reload",
        default=False,
        action="store_true",
        help="重新加载并更新您的appToken和uid",
    )
    parser.add_argument(
        "-c",
        "--continuous",
        default=False,
        action="store_true",
        help="条件满足时继续推送消息",
    )
    parser.add_argument(
        "-flag",
        "--flag-preempt",
        default=False,
        action="store_true",
        help="是否运行GPU抢占程序",
    )
    parser.add_argument("-p", "--process-name", type=str, help="GPU抢占程序名称")
    parser.add_argument(
        "-u",
        "--user-info",
        type=str,
        default="user_info.txt",
        help="用户信息配置文件路径",
    )
    parser.add_argument(
        "-n", "--name-server", type=str, default="server0", help="微信推送的名称"
    )

    return parser.parse_args()


def remove_control_characters(text):
    """
    去除字符串中的控制字符
    """
    control_characters = re.compile(r"\x1b\[[0-9;]*m")
    return control_characters.sub("", text)


def push_to_wechat(gpu_stats, exists_list):
    """
    推送GPU状态到微信
    """
    global appToken, uid, check_count, name_server
    s = f"信息: {name_server}\n第{check_count}次检查：{exists_list} 满足条件\nGPU状态: \n\n"
    for i in gpu_stats.gpus:
        s += remove_control_characters(str(i))
        s += "\n"
    sc_res_raw = requests.post(
        f"http://wxpusher.zjiecode.com/api/send/message",
        json={
            "appToken": appToken,
            "summary": f"{name_server} 第{check_count}次检查：{exists_list} 满足条件",
            "content": f"{s}",
            "contentType": 1,
            "uids": [uid],
        },
    )

    try:
        return_json = json.loads(sc_res_raw.text)
    except:
        raise RuntimeError(
            f"WxPusher 的返回值不能解析为 JSON，可能您的 appToken 或 uid 配置有误"
            f"API 的返回是：\n{sc_res_raw}\n您输入的 appToken 为\n{appToken}\n您输入的 uid 为\n{uid}"
        )
    success = return_json.get("success")

    if success is not True:
        raise RuntimeError(
            f"WxPusher调用失败，可能您的 appToken 或 uid 配置有误。API 的返回是：\n{sc_res_raw}\n"
            f"您输入的 appToken 为\n{appToken}\n您输入的 uid 为\n{uid}"
        )


def run_gpu_preempt(exists_list, process_name):
    """
    运行GPU抢占程序
    """
    logging.info(f"运行GPU抢占程序")
    gpu_str = ",".join([str(i) for i in exists_list])
    gpu_num = len(exists_list)
    run_cmd = f"CUDA_VISIBLE_DEVICES={gpu_str} torchrun --standalone --nproc_per_node={gpu_num} {process_name}"
    logging.info(f"运行命令: {run_cmd}")
    # 判断程序路径是否存在
    process_path = process_name.strip().split()[0]
    if not os.path.exists(process_path):
        logging.error(f"程序路径 {process_path} 不存在")
        return
    else:
        os.system(run_cmd)


def check_gpu(args):
    """
    检查GPU状态并推送消息
    """
    global check_count
    logging.info(f"第{check_count}次检查GPU状态")
    gpu_stats = GPUStatCollection.new_query()
    for i in gpu_stats.gpus:
        logging.info(str(i))

    # 获取满足条件的GPU ID
    empty_card = [
        gpu.index for gpu in gpu_stats.gpus if gpu.memory_free >= args.cuda_memory
    ]

    # 判断gpu_list中是否有满足条件的gpu
    exists_list = [item for item in empty_card if item in args.device_list]

    if len(exists_list):
        logging.info(f"满足条件的GPU ID: {exists_list}")
        push_to_wechat(gpu_stats, exists_list)
    else:
        logging.info(f"没有满足条件的GPU ID")

    check_count += 1
    return exists_list


def initialize_scheduler(args):
    """
    初始化调度器
    """
    empty_card = []
    scheduler = BlockingScheduler()

    # 解析检查频率
    time_parser = []
    time_type = ["d", "h", "m", "s"]
    for type in time_type:
        value = re.findall(r"\d+(?=%s)" % type, args.check_freq)
        value = int(value[0]) if len(value) > 0 else 0
        time_parser.append(value)

    time_str = "-".join(f"{num}{unit}" for num, unit in zip(time_parser, time_type))

    # 定时装饰器，interval表示循环任务
    @scheduler.scheduled_job(
        "interval",
        days=time_parser[0],
        hours=time_parser[1],
        minutes=time_parser[2],
        seconds=time_parser[3],
    )
    def scheduled_job():
        exists_list = check_gpu(args)
        if len(exists_list) and args.flag_preempt:
            run_gpu_preempt(exists_list, args.process_name)
        if len(exists_list) and not args.continuous:
            scheduler.shutdown(wait=False)

    return scheduler, time_str


def main():
    global appToken, uid, check_count, name_server
    args = parse_args()
    name_server = args.name_server
    check_count = 0  # 检查计数次数

    if args.reload or not os.path.exists(args.user_info):
        appToken = input("请输入您的appToken: ")
        uid = input("请输入您的uid: ")
        with open(args.user_info, "w", encoding="utf-8") as f:
            f.write(appToken + "\n" + uid)
    else:
        with open(args.user_info, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            appToken = lines[0]
            uid = lines[1]

    logging.info("#" * 10 + "初始化显卡空闲监控" + "#" * 10)
    scheduler, time_str = initialize_scheduler(args)

    logging.info(f"监控GPU列表: {args.device_list}")
    logging.info(f"触发条件显存空闲大于: {args.cuda_memory} MB")
    logging.info(f"监控刷新频率: {time_str}")
    logging.info(f"是否持续监控: {args.continuous}")
    logging.info("#" * 10 + "开始显卡空闲监控" + "#" * 10)

    # 第一次运行时先检查条件是否满足
    check_gpu(args)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
