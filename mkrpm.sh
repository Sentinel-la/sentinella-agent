#!/bin/sh
rm -f dist/*.rpm
rpmvenv --verbose redhat/sentinella-rpm.json --verbose --destination dist --source .
