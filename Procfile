web: gunicorn config.wsgi:application --workers=2 --timeout=120
release: python manage.py migrate
worker: python manage.py rqworker default