import logging

from app_backend import get_default_config
from app_backend.analysis.tunnel_parse import TunnelParse
from app_backend.model.task_model import TaskModel

logger = logging.getLogger(__name__)
config = get_default_config()


def evaluate_score(task: TaskModel, log_file):
    # 评分
    tunnel_graph = TunnelParse(tunnel_log=log_file, ms_per_bin=500)
    tunnel_results = tunnel_graph.parse()
    throughput = tunnel_results['throughput']
    queueing_delay = tunnel_results['delay']
    loss_rate = tunnel_results['loss'] - task.loss_rate
    if loss_rate < 0:
        logger.error(f"[task: {task.task_id}] Loss rate({loss_rate}) is negative, is this expected?")
    capacity = tunnel_results['capacity']
    # 1. 吞吐量效率评分 (0-100分)
    # 基于理论吞吐量的利用率
    efficiency = 0
    if capacity > 0:
        efficiency = throughput / capacity
    if efficiency >= 1.0:  # 100%以上利用率满分
        throughput_score = 100
    elif efficiency >= 0:
        throughput_score = 100 * efficiency
    else:
        throughput_score = 0

    # 2. 丢包控制评分 (0-100分)
    if loss_rate <= 0.000001:
        loss_score = 100
    elif loss_rate >= 1:
        loss_score = 0
    else:
        loss_score = 100 * (1.0 - loss_rate)

    # 3. 延迟控制评分 (0-100分)
    # 基于RTT膨胀程度
    # queueing_delay是排队时延，delay是单向延迟
    # 换算成往返时延（RTT）
    rtt_inflation = 2.0
    rtt_conf = task.delay * 2
    real_rtt = queueing_delay + rtt_conf
    if task.delay > 0:
        rtt_inflation = real_rtt / rtt_conf
    if rtt_inflation <= 10:
        # rtt_inflation at least 1, use (11 - rtt_inflation)
        latency_score = 30 + 70 * (11 - rtt_inflation) / 10
    else:
        latency_score = 100 * 3 / rtt_inflation

    # 计算总分
    trace_conf = config.get_course_trace_config(task.cname, task.trace_name)
    score = trace_conf['score_weights']['throughput'] * throughput_score + trace_conf['score_weights'][
        'loss'] * loss_score + trace_conf['score_weights']['delay'] * latency_score
    logger.info(
        f"[task: {task.task_id}] Calculated score: {score} (throughput_score: {throughput_score}, delay_score: {latency_score}, loss_score: {loss_score})" +
        f"by efficiency: {efficiency}(throughput({throughput})/capacity({capacity})), "
        f"rtt_inflation: {rtt_inflation}(real_rtt({real_rtt})/rtt_conf({rtt_conf})), "
        f"loss_rate: {loss_rate}(tunnel_loss({tunnel_results['loss']})-loss_conf({task.loss_rate}))")
    # 更新任务的分数
    task.update(task_score=score, loss_score=loss_score, delay_score=latency_score, throughput_score=throughput_score)

    return score
