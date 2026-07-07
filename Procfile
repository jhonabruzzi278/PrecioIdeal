web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn pricewatch.wsgi --bind 0.0.0.0:$PORT --workers 1 --worker-class gthread --threads 4 --timeout 120
