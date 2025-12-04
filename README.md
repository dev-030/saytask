celery -A core worker -l info

celery -A core worker -B -l info     #For running celery worker and beat both together


pm2 start "celery -A core worker -B -l info" --name taskly-celery

pm2 start "python manage.py runserver 0.0.0.0:8004" --name taskly-api