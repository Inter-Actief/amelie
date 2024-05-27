#!/bin/bash

# Start django server (ASGI)
daphne -b 0.0.0.0 -p 8000 amelie.asgi:application
