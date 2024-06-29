sudo killall flask
flask rq worker >rq_worker.log 2>&1 &
flask rq worker >rq_worker2.log 2>&1 &
flask rq worker >rq_worker3.log 2>&1 &
flask rq worker >rq_worker4.log 2>&1 &
flask rq worker >rq_worker5.log 2>&1 &
flask rq worker >rq_worker6.log 2>&1 &
flask rq worker >rq_worker7.log 2>&1 &
flask rq worker >rq_worker8.log 2>&1 &
nohup flask run -h 0.0.0.0 -p 54321 &
#flask run -h 0.0.0.0 -p 54321 
echo -e "\nService has been restarted.\n"
