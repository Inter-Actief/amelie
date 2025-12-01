# Build the amelie docker image based on Debian 11 (Bullseye)
FROM debian:bullseye

# Load some build variables from the pipeline
ARG BUILD_BRANCH=unknown
ARG BUILD_COMMIT=unknown
ARG BUILD_DATE=unknown

# Copy amelie sources
COPY . /amelie

# Set /amelie as startup working directory
WORKDIR /amelie

# Install required packages for amelie and prepare the system to run Amelie
RUN echo "Updating repostitories..." && \
    apt-get update -y && \
    echo "Upgrading base debian system..." && \
    apt-get upgrade -y && \
    echo "Installing Amelie required packages..." && \
    apt-get install -y apt-utils git net-tools python3 python3-pip pkg-config default-libmysqlclient-dev mariadb-client libmariadb-dev xmlsec1 libssl-dev libldap-dev libsasl2-dev libjpeg-dev zlib1g-dev gettext locales acl && \
    echo "Enabling 'nl_NL' and 'en_US' locales..." && \
    sed -i -e 's/# nl_NL.UTF-8 UTF-8/nl_NL.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    echo "Rebuilding locales..." && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    echo "Creating directories for amelie..." && \
    mkdir -p /amelie /config /static /media /photo_upload /data_exports /homedir_exports /var/log /var/run && \
    echo "Installing python requirements..." && \
    pip3 install . && \
    echo "Adding build variable files..." && \
    echo "${BUILD_BRANCH}" > /amelie/BUILD_BRANCH && \
    echo "${BUILD_COMMIT}" > /amelie/BUILD_COMMIT && \
    echo "${BUILD_DATE}" > /amelie/BUILD_DATE && \
    echo "Correcting permissions on directories..." && \
    chown -R 1000:1000 /amelie /config /static /media /photo_upload /data_exports /homedir_exports /var/log

# Switch back to a local user
USER 1000:1000

# Check if Django can run
RUN python3 manage.py check

# Expose volumes
VOLUME ["/config", "/static", "/media", "/photo_upload", "/data_exports", "/homedir_exports"]

# Expose the web port
EXPOSE 8000

# Start the website
CMD ["/amelie/scripts/start_web_asgi.sh"]
