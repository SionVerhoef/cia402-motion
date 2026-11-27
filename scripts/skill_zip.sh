#!/bin/sh
# Builds the skill-only release zip: what an agent loads, without the evals, tests and CI
# checks that the source archives also carry. It unpacks as cia402-motion/, the folder name
# the skill expects. git archive fails on a path that no longer exists, so a rename breaks
# the build instead of silently shipping a smaller skill.
#
#   sh scripts/skill_zip.sh v0.3.0      ->  cia402-motion-v0.3.0.zip
set -eu
version=${1:?usage: skill_zip.sh <version>}
out="cia402-motion-$version.zip"
git archive --format=zip --prefix=cia402-motion/ -o "$out" HEAD \
  SKILL.md README.md LICENSE ATTRIBUTIONS.md \
  references templates scripts/cia402.py
echo "$out"
