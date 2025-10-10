Welcome, and thanks for wanting to contribute to this project!

## How to contribute

### Reporting bugs
Bugs can be reported through our [issues](https://github.com/Inter-Actief/amelie/issues). Please check if an issue already exists for your problem before submitting a new one.

Please write clearly what the problem is, how to reproduce it, and include screenshots if you think this would make the issue clearer. If you received a 500 error from our server, please indicate the time and date as well, so we can re-trace the error.

Please write your issue reports in English.

**Please do not assign labels yourself!**

### Suggesting features or enhancements
Suggestions can be done through our [issues](https://github.com/Inter-Actief/amelie/issues). Please check if a suggestion already exists before submitting it.

Please write clearly what your suggestion or feature is, and what it should do. Include any mockups/design documents you might have as well. Also explain why you think the feature or enhancement should be added.

Please write your suggestions in English.

**Please do not assign labels yourself!**

### Contributing code
If you want to have an easy entrypoint when starting to contribute, you can take a look at our [easy-fix issues](https://github.com/Inter-Actief/amelie/labels/easy-fix). These are issues that are deemed by our experienced developers to be easy to fix for people just starting out.

#### Local development
To develop stuff for the website, you might want to run it locally to check your changes. This is possible. To run Amélie locally, follow these steps:

##### Install required packages
To develop for Amélie, the following packages are needed:

###### Windows
Python 3: https://www.python.org/downloads/

###### Debian/Ubuntu
    sudo apt-get install python3 libjpeg-dev zlib1g-dev xmlsec1 libssl-dev libldap-dev libsasl2-dev

###### Arch linux
    sudo pacman -Syu python libjpeg-turbo zlib xmlsec openssl

##### Clone the website
    git clone https://github.com/Inter-Actief/amelie.git
    cd amelie/

##### Setup a virtualenv
    python3 -m venv venv
    source ./venv/bin/activate
    pip install --upgrade pip setuptools
    pip install .

##### Copy local settings
    cp ./amelie/settings/local.py.localdev ./amelie/settings/local.py

##### Change settings (`MEDIA_ROOT` locations)
Replace the `MEDIA_ROOT` and `DATA_EXPORT_ROOT` settings with proper locations. This location will be used to store uploaded files.

    nano ./amelie/settings/local.py

For example: *(make sure the directory exists!)*

    MEDIA_ROOT = "/tmp/amelie_uploads"

##### Populate the database
    python manage.py migrate
    python manage.py www_generate_dummydata --ok

##### Run the development server
    python manage.py runserver

#### Working on issues
When working on an issue or feature, please work on a feature branch (or a fork). For example:

    git branch feature-new-homepage
    git checkout feature-new-homepage

    git branch issue-830
    git checkout issue-830

### Pull requests
Please fill in the pre-existing [template](.github/PULL_REQUEST_TEMPLATE.md) when submitting a pull request.

After submitting, the build system will check your build. Please make sure that this build is successful. Also, keep an eye on your PR and solve any conflicts that may arise due to merging other PR's before yours.

Main developers or other contributors might comment on your PR or request extra changes, please respond to these before the PR can be merged.
