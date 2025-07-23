import time

import cairosvg
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import TimeLimitExceeded

from app_backend import setup_logger, get_app
from app_backend.analysis.tunnel_parse import TunnelParse
from app_backend.jobs.dramatiq_queue import DramatiqQueue
from app_backend.model.graph_model import GraphModel, GraphType
from app_backend.model.task_model import TaskModel, TaskStatus
from app_backend.model.user_model import *

setup_logger()
logger = logging.getLogger(__name__)
config = get_default_config()
redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
dramatiq.set_broker(redis_broker)


# 实测高并发时，画图操作cpu占用高导致cpu99%，解耦画图和转png任务作为单独的任务队列启动进程处理
# 转png用于压缩delay图，减少存储空间占用，此操作可能耗时较长，作为后台任务处理，不应对其完成时间有预期

# 10分钟超时（毫秒），此时间应大于cmd子进程的超时时间
@dramatiq.actor(time_limit=600000, max_retries=0, queue_name=DramatiqQueue.GRAPH.value)
def run_graph_task(task_id, result_path):
    app = get_app()
    with (app.app_context()):
        try:
            db.session.expire_all()  # 刷新会话
            task = TaskModel.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"[task: {task_id}] Task not found")
                return

            logger.info(f"[task: {task_id}] Start graph task")
            assert task.task_status == TaskStatus.FINISHED, "Task status must be FINISHED to run graph task"
            _graph(task, result_path)

        except TimeLimitExceeded as e:
            # 处理 Dramatiq 的超时异常，此异常不在Exception中，需单独处理
            logger.error(f"[task: {task_id}] Graph task timed out due to Dramatiq TimeLimit middleware")
            err_msg = f"{type(e).__name__}\n{str(e)}\nGraph task timed out after 10 minutes, this problem shouldn't happen, please contact admin."

            if 'task' in locals():
                _handle_exception(task_id, err_msg, task)

        except Exception as e:
            # 理论上除了编译失败外，不应出现其他异常，如果出现，需要修复代码相关逻辑
            err_msg = f"{type(e).__name__}\n{str(e)}"
            if 'task' in locals():
                _handle_exception(task_id, err_msg, task)
        finally:
            try:
                db.session.remove()
            except TimeLimitExceeded as e:
                logger.error(f"[task: {task_id}] Graph task error when finally cleanup: Dramatiq TimeLimitExceeded",
                             exc_info=True)
            except Exception as e:
                logger.error(f"[task: {task_id}] Graph task error when finally cleanup: {str(e)}", exc_info=True)


# 30分钟超时（毫秒），此时间应大于cmd子进程的超时时间
@dramatiq.actor(time_limit=1800000, max_retries=0, queue_name=DramatiqQueue.SVG2PNG.value)
def run_svg2png_task(task_id, graph_id):
    app = get_app()
    with (app.app_context()):
        try:
            db.session.expire_all()  # 刷新会话
            task = TaskModel.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"[task: {task_id}] Task not found")
                return

            logger.info(f"[task: {task_id}] Start svg2png task")
            assert task.task_status == TaskStatus.FINISHED, "Task status must be FINISHED to run graph task"
            _svg2png(task, graph_id)

        except TimeLimitExceeded as e:
            # 处理 Dramatiq 的超时异常，此异常不在Exception中，需单独处理
            logger.error(f"[task: {task_id}] Svg2png task timed out due to Dramatiq TimeLimit middleware")
            err_msg = f"{type(e).__name__}\n{str(e)}\nSvg2png task timed out after 10 minutes, this problem shouldn't happen, please contact admin."

            if 'task' in locals():
                _handle_exception(task_id, err_msg, task)

        except Exception as e:
            # 理论上除了编译失败外，不应出现其他异常，如果出现，需要修复代码相关逻辑
            err_msg = f"{type(e).__name__}\n{str(e)}"
            if 'task' in locals():
                _handle_exception(task_id, err_msg, task)
        finally:
            try:
                db.session.remove()
            except TimeLimitExceeded as e:
                logger.error(f"[task: {task_id}] Svg2png task error when finally cleanup: Dramatiq TimeLimitExceeded",
                             exc_info=True)
            except Exception as e:
                logger.error(f"[task: {task_id}] Svg2png task error when finally cleanup: {str(e)}", exc_info=True)


def _graph(task, result_path):
    """
    画图
    :return: None
    """
    from app_backend.jobs.cctraining_job import run_cmd
    task_id = task.task_id
    task.update_task_log("开始生成性能图，请稍候...")

    throughput_graph_svg = os.path.join(task.task_dir, f"{task.trace_name}.throughput.svg")
    # delay_graph_svg = os.path.join(task.task_dir, f"{task.trace_name}.delay.svg")
    delay_graph_png = os.path.join(task.task_dir, f"{task.trace_name}.delay.png")

    logger.info(f"[task: {task_id}] is generating graphs")
    graph_start_time = time.time()
    run_cmd(f'mm-throughput-graph 500 {result_path} > {throughput_graph_svg}', task_id)
    # run_cmd(f'mm-delay-graph {result_path} > {delay_graph_svg}', task_id)
    # 另一个画图逻辑
    tunnel_graph = TunnelParse(
        tunnel_log=result_path,
        throughput_graph=None,
        delay_graph=delay_graph_png,
        ms_per_bin=500)
    tunnel_graph.graph()
    graph_end_time = time.time()
    logger.info(
        f"[task: {task_id}] Graphs generated successfully after {graph_end_time - graph_start_time:.2f} seconds: "
        f"{throughput_graph_svg}, {delay_graph_png}")
    throughput_graph = GraphModel(task_id=task_id, graph_type=GraphType.THROUGHPUT,
                                  graph_path=throughput_graph_svg)
    throughput_graph.insert()
    delay_graph = GraphModel(task_id=task_id, graph_type=GraphType.DELAY,
                             graph_path=delay_graph_png)
    delay_graph.insert()
    os.remove(result_path)
    logger.info(f"[task: {task_id}] Removed result file: {result_path}")
    task.update_task_log(f"性能图生成成功，耗时 {graph_end_time - graph_start_time:.2f} 秒。")
    task.update()  # 写入日志

    logger.info(
        f"[task: {task_id}] Graph task completed successfully, inserted graphs into database")
    # 将delay图转换为PNG任务发送到队列
    # message = run_svg2png_task.send(task_id=task_id, graph_id=delay_graph.graph_id)
    # if not message:
    #     logger.error(f"[task: {task_id}] Failed to send svg2png task to queue")
    # else:
    #     logger.info(f"[task: {task_id}] Sent svg2png task to queue successfully, message ID: {message.message_id}")


def _svg2png(task, graph_id):
    """
    将svg转换为png以压缩存储空间
    """
    task_id = task.task_id

    graph = GraphModel.query.filter_by(graph_id=graph_id).first()
    if not graph:
        logger.error(f"[task: {task_id}] Graph not found for graph_id: {graph_id}")
        return
    svg_path = graph.graph_path
    # 确保后缀为svg
    assert svg_path.endswith('.svg'), f"Graph file {svg_path} must end with .svg"
    graph_type = graph.graph_type
    task.update_task_log(f"开始压缩{graph_type.value}性能图，请稍候...")
    graph_png_name = f"{task.trace_name}.{graph_type.value}.png"
    graph_png_path = os.path.join(task.task_dir, graph_png_name)
    # 由于delay svg图太大，将svg转换为png以压缩
    logger.info(f"[task: {task_id}] Converting {graph_type.value} graph SVG to PNG")
    convert_start_time = time.time()
    cairosvg.svg2png(url=svg_path, write_to=graph_png_path)
    graph.update(graph_path=graph_png_path)
    os.remove(svg_path)
    convert_end_time = time.time()
    logger.info(
        f"[task: {task_id}] Converted delay graph SVG to PNG, svg removed, took {convert_end_time - convert_start_time:.2f} seconds.")
    task.update_task_log(
        f"{graph_type.value}性能图压缩成功，耗时 {convert_end_time - convert_start_time:.2f} 秒。")
    task.update()  # 写入日志

    logger.info(
        f"[task: {task_id}] Graph converted successfully to PNG, graph_type: {graph_type.value}, path: {graph_png_path}")


def _handle_exception(task_id, err_msg, task=None):
    """
    处理异常，更新任务状态和错误日志
    :param task: TaskModel对象
    :param task_id: 任务ID
    :param err_msg: 错误信息
    """
    task_error_log_content = f"发生意外错误，请稍后再试。若问题仍存在可将此信息反馈给管理员协助排查。\n[task_id: {task_id}]\nException occurred during graph:\n{err_msg}\n"
    logger.error(f"[task: {task_id}] Graph task error: {task_error_log_content}", exc_info=True)
    if task:
        task.update_task_log(task_error_log_content)
        task.update()
