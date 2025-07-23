from enum import Enum


class DramatiqQueue(Enum):
    """
    Enum representing different task queues.
    用到了任务队列的枚举类
    """
    # 运行算法评测的任务队列
    CC_TRAINING = "cc_training"
    # 绘图任务队列
    GRAPH = "graph"
    # 时延图svg转png的任务队列
    SVG2PNG = "svg2png"

    def __str__(self):
        return self.value
