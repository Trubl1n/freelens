# Freelens

Django project prepared for deployment on Railway with PostgreSQL, Gunicorn, and WhiteNoise.

## Railway deployment

1. Push the repository to GitHub:

```powershell
git remote add origin https://github.com/Trubl1n/freelens.git
git branch -M main
git push -u origin main
```

2. Create a Railway service from the GitHub repository.

3. Add Railway variables:

```env
SECRET_KEY=<generated-secret-key>
MISTRAL_API_KEY=<your-mistral-api-key>
DEBUG=False
ALLOWED_HOSTS=.railway.app,.up.railway.app
DJANGO_ENV=production
TIMEZONE=Europe/Moscow
```

4. Run in the Railway console:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Railway will start the app with:

```bash
gunicorn freelancer_tracker.wsgi:application --log-file -
```
