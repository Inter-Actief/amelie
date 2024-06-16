#!/bin/bash
set -e
# Script to nicely pull the latest 'main' branch and merge it into the 'production' branch.

# Checks to make sure this isn't run on a dirty repository
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

# Fetch the latest changes on the 'main' branch and show comparisons between 'main' and 'production'.
echo "### Pulling changes"
git pull
changeset=`git rev-parse --short origin/main`
echo "### origin/main changeset to merge is [$changeset]"
echo "### Changes:"
git log --oneline ..origin/main
git diff --stat ...origin/main

# Ask for confirmation
read -p "Are you sure you want to merge and push these changes? (y/n)" -r
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo
    exit 1
fi

# Merge changes into production
git merge -m "Merge [$changeset] to production (ac)" origin/main
git push origin production
echo "### Changes pulled, merged/fast-forwarded and committed"

echo "### Done!"
