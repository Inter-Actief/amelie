# Build the amelie docker image based on Debian 11 (Bullseye)
FROM debian:bullseye

# Install required debian packages for amelie
RUN apt-get update -y && apt-get upgrade -y && apt-get install -y apt-utils git net-tools python3 python3-pip mariadb-client libmariadb-dev xmlsec1 libssl-dev libldap-dev libsasl2-dev libjpeg-dev zlib1g-dev gettext

# Enable nl_NL and en_US locales and rebuild locale
RUN apt-get update && \
    apt-get install -y locales && \
    sed -i -e 's/# nl_NL.UTF-8 UTF-8/nl_NL.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales

# Make directories for amelie
RUN mkdir -p /amelie /amelie/static /media /photo_upload /config /var/log /var/run

# Copy amelie sources
COPY . /amelie

# Set /amelie as startup working directory
WORKDIR /amelie

# Switch to root user
USER root

# Install python requirements
RUN pip3 install -r requirements.txt

# Correct permissions on directories
RUN chown -R 1000:1000 /amelie /media /photo_upload /config /var/log

# Switch back to a local user
USER 1000:1000

# Check if Django can run
RUN python3 manage.py check

# Expose volumes
VOLUME ["/amelie/static", "/media", "/photo_upload", "/config"]

# Expose the web port
EXPOSE 80

# Start the website
CMD ["/amelie/scripts/start_web.sh"]
