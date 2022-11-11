#!/bin/bash

# Delete the old file
/bin/rm amelie/style/static/css/compiled.css

# Compile new version
lessc amelie/style/static/less/style.less > amelie/style/static/css/compiled.css
