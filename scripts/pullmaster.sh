#!/bin/bash
set -e
# Script to nicely pull, update, collect the static, etc.

if [[ $(git rev-parse --abbrev-ref HEAD) != "production" ]]
then
    echo "This script should only run in the production branch, which you don't seem to be using!"
    exit 1
fi
if [[ -n $(git status --porcelain) ]]
then
    echo "There are uncommitted local changes. Please commit these changes before updating production."
    exit 1
fi

# Parse command line arguments
REENABLE=0
while test $# -gt  0; do
    case "$1" in
        -r|--reenable)
            echo "Will re-enable the website after the script is done."
            REENABLE=1
            shift
            ;;
        -h|--help)
            echo "$0 - update amelie production website"
            echo " "
            echo "$0 [options]"
            echo " "
            echo "options:"
            echo "-h, --help        Show this help text"
            echo "-r, --reenable    Automatically disable the maintenance page after the update is done."
            exit 0
            ;;
        *)
            echo "Invalid arguments, use -h for help."
            exit 1
            ;;

    esac
done

echo "### Enabling virtual environment"
source /data/environment/amelie/bin/activate

# Check for currently running background tasks before starting deploy
echo "### Current Celery tasks queue status (do not deploy if there are running tasks!)"
celery -A amelie inspect active
read -p "Do you want to continue deployment? (y/n)" -r
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo
    exit 1
fi

# Enable the maintenance landing page
echo "### Enabling maintenance landing page"
sudo a2ensite 000-amelie-maintenance.conf
sudo systemctl reload apache2

# Merge changes into production
echo "### Pulling changes"
git pull
changeset=`git rev-parse --short origin/main`
echo "### origin/main changeset to merge is [$changeset]"
echo "### Changes:"
git log --oneline ..origin/main
git diff --stat ...origin/main

read -p "Are you sure you want to merge and push these changes? (y/n)" -r
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo
    exit 1
fi
git merge -m "Merge [$changeset] to production (ac)" origin/main
git push origin production
echo "### Changes pulled, merged/fast-forward and committed"

echo "### Updating pip packages"
pip install -r /data/applications/amelie/requirements.txt --upgrade
echo "### update completed"

echo "### Collecting static files"
/data/applications/amelie/manage.py collectstatic --noinput
echo "### collectstatic completed"

if ! python manage.py migrate --check; then
    echo "There are migrations that still need to be performed. Please migrate before restarting the server."
    exit 1
fi

echo "### Restarting webserver and celery..."
sudo systemctl restart apache2
sudo systemctl restart celery-amelie
sleep 3
sudo systemctl restart flower-amelie

if [[ ${REENABLE} -eq 1 ]]
then
    echo "### Disabling maintenance page..."
    sudo a2dissite 000-amelie-maintenance.conf
    sudo systemctl reload apache2
    echo "### Done!"
else
    echo "### Done! Please check the website by visiting https://backdoor.ia.utwente.nl/"
    echo "### and disable the maintenance mode by running:"
    echo "### sudo a2dissite 000-amelie-maintenance.conf && sudo systemctl reload apache2"
fi
