#!/bin/sh
rm -f dist/*.rpm
rpmvenv --spec --verbose redhat/sentinella-rpm.json --destination dist --source .
