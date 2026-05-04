import subprocess

from django.core.management.utils import get_random_secret_key


REPOSITORY_URL = "https://github.com/Trubl1n/freelens.git"


def run(command):
    subprocess.run(command, check=True)


def main():
    secret_key = get_random_secret_key()

    run(["git", "init"])
    run(["git", "add", "."])
    run(["git", "commit", "-m", "Prepare for Railway"])

    print("\nGenerated SECRET_KEY:")
    print(secret_key)

    print("\nGit push commands:")
    print(f"git remote add origin {REPOSITORY_URL}")
    print("git branch -M main")
    print("git push -u origin main")

    print("\nRailway variables:")
    print(f"SECRET_KEY={secret_key}")
    print("MISTRAL_API_KEY=<your-mistral-api-key>")
    print("DEBUG=False")
    print("ALLOWED_HOSTS=.railway.app,.up.railway.app")
    print("DJANGO_ENV=production")
    print("TIMEZONE=Europe/Moscow")


if __name__ == "__main__":
    main()
