from app_backend.model.Task_model import Task_model


def query_rank_list(Sclass=None):
    # sql = "select * from(select @rn:= CASE when @user_id = user_id then @rn + 1 else 1 end as rn, @user_id:=
    # user_id as user_id, task_score, task_status, created_time  from (select * from task where task_score is not
    # null order by user_id, created_time desc) a, (select @rn=0, @user_id=0) b) c where rn <= 1;"

    if Sclass:
        # sql = "select task_id,task.user_id,student.username,cca_name, task_score,created_time, score_without_loss, score_with_loss from student,task,(select max(task_score) as mscore ,
        # task.user_id as uid from task where task.task_score is not null group by task.user_id) as temp where task.user_id = uid and task.
        # task_score = mscore and task.user_id = student.user_id and student.Sclass = '%s' order by task_score desc;" % str(
        #     Sclass)
        result = Task_model.query.filter(Task_model.task_score.isnot(None)).order_by(Task_model.user_id, Task_model.created_time.desc()).all()
        return result
    # sql = "select task_id,task.user_id,student.username,cca_name, task_score,created_time, score_without_loss, score_with_loss from student,task,(select max(created_time) as ctime , task.user_id as uid from task where task.task_score is not null group by task.user_id, task.cca_name) as temp where task.user_id = uid and task.created_time = ctime and task.user_id = student.user_id and student.Sclass = '%s' order by task_score desc, created_time asc;"  % str(Sclass)
    else:
        pass
    return None



def query_history_records(user_id):
    result = Task_model.query.filter_by(user_id=user_id).all()
    return result


