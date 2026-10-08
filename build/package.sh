#!/bin/sh
# Package the Cowork plugin: dist/stem-tutor.plugin (a zip whose root holds .claude-plugin/, skills/, ...)
set -e
cd "$(dirname "$0")/../plugin/stem-tutor"
mkdir -p ../../dist
rm -f ../../dist/stem-tutor.plugin
zip -qr ../../dist/stem-tutor.plugin . -x '*/__pycache__/*' -x '*.pyc' -x '.DS_Store'
cd ../..
unzip -l dist/stem-tutor.plugin | tail -1
